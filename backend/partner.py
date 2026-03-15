"""
Arrow Partner Pairing System
Couples connection, shared wishlist, and compatibility matching
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from jose import JWTError, jwt
from pydantic import BaseModel
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import random
import string
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "arrow_jwt_secret_key_2026_production_v1")
ALGORITHM = "HS256"

# Global db_pool reference (injected from main.py)
db_pool: Optional[asyncpg.Pool] = None

def set_db_pool(pool: asyncpg.Pool):
    """Set the database pool (called from main.py on startup)"""
    global db_pool
    db_pool = pool


# ==================== MODELS ====================

class TokenData(BaseModel):
    """Authentication token payload"""
    user_id: str
    phone_number: str


# ==================== DATABASE INITIALIZATION ====================

async def init_partner_tables():
    """Create partner-related tables if they don't exist"""
    if not db_pool:
        logger.error("Database pool not initialized")
        return

    async with db_pool.acquire() as conn:
        # Partner connections table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS partner_connections (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                partner_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                invite_code VARCHAR(8) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                accepted_at TIMESTAMP,
                UNIQUE(user_id, partner_user_id)
            );
        ''')

        # Create index on invite_code for faster lookups
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_partner_connections_invite_code
            ON partner_connections(invite_code);
        ''')

        # Create index on status for faster filtering
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_partner_connections_status
            ON partner_connections(status);
        ''')

        # Shared wishlist table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS shared_wishlist (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                connection_id UUID REFERENCES partner_connections(id) ON DELETE CASCADE,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                date_idea_id UUID REFERENCES date_ideas(id) ON DELETE CASCADE,
                notes TEXT,
                shared_at TIMESTAMP DEFAULT NOW()
            );
        ''')

        # Create index on connection_id for faster lookups
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_shared_wishlist_connection_id
            ON shared_wishlist(connection_id);
        ''')

        logger.info("Partner tables initialized successfully")


# ==================== HELPERS ====================

def generate_invite_code() -> str:
    """Generate a unique 6-character alphanumeric invite code (e.g., 'ARW-X4K')"""
    # Use uppercase letters and digits, exclude similar-looking chars (I, l, O, 0)
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = ''.join(random.choice(chars) for _ in range(6))
    # Format as: XXX-XXX (like: ARW-X4K)
    return f"{code[:3]}-{code[3:]}"


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user details by ID"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, name, phone_number, interests, budget_preference, personality_type FROM users WHERE id = $1",
            user_id
        )
        return dict(user) if user else None


async def get_active_partnership(user_id: str) -> Optional[Dict[str, Any]]:
    """Get the active partnership for a user (if any)"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        # Look for accepted partnership where user is either initiator or acceptor
        connection = await conn.fetchrow('''
            SELECT * FROM partner_connections
            WHERE (user_id = $1 OR partner_user_id = $1)
            AND status = 'accepted'
            LIMIT 1
        ''', user_id)
        return dict(connection) if connection else None


async def get_partner_user_id(user_id: str) -> Optional[str]:
    """Get the partner's user_id if a partnership exists"""
    partnership = await get_active_partnership(user_id)
    if not partnership:
        return None

    # Return the other user in the partnership
    if partnership['user_id'] == user_id:
        return partnership['partner_user_id']
    else:
        return partnership['user_id']


async def get_user_idea_interactions(user_id: str) -> Dict[str, Any]:
    """Get user's idea interaction history for compatibility calculation"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        # Get accepted ideas
        accepted = await conn.fetch('''
            SELECT ii.date_idea_id, di.category, di.budget_estimate
            FROM idea_interactions ii
            JOIN date_ideas di ON ii.date_idea_id = di.id
            WHERE ii.user_id = $1 AND ii.action = 'accepted'
        ''', user_id)

        # Get rejected ideas
        rejected = await conn.fetch('''
            SELECT ii.date_idea_id, di.category, di.budget_estimate
            FROM idea_interactions ii
            JOIN date_ideas di ON ii.date_idea_id = di.id
            WHERE ii.user_id = $1 AND ii.action = 'rejected'
        ''', user_id)

        return {
            "accepted": [dict(row) for row in accepted],
            "rejected": [dict(row) for row in rejected]
        }


def calculate_compatibility(user1_interactions: Dict, user2_interactions: Dict) -> Dict[str, Any]:
    """Calculate compatibility between two users based on their idea interactions"""

    # Extract category preferences
    user1_accepted_categories = set()
    user1_accepted_budgets = set()
    user1_rejected_categories = set()

    user2_accepted_categories = set()
    user2_accepted_budgets = set()
    user2_rejected_categories = set()

    for idea in user1_interactions["accepted"]:
        if idea.get("category"):
            user1_accepted_categories.add(idea["category"])
        if idea.get("budget_estimate"):
            user1_accepted_budgets.add(idea["budget_estimate"])

    for idea in user1_interactions["rejected"]:
        if idea.get("category"):
            user1_rejected_categories.add(idea["category"])

    for idea in user2_interactions["accepted"]:
        if idea.get("category"):
            user2_accepted_categories.add(idea["category"])
        if idea.get("budget_estimate"):
            user2_accepted_budgets.add(idea["budget_estimate"])

    for idea in user2_interactions["rejected"]:
        if idea.get("category"):
            user2_rejected_categories.add(idea["category"])

    # Calculate metrics
    shared_accepted = user1_accepted_categories & user2_accepted_categories
    total_accepted = user1_accepted_categories | user2_accepted_categories

    category_overlap = len(shared_accepted) / len(total_accepted) if total_accepted else 0

    # Budget compatibility
    shared_budgets = user1_accepted_budgets & user2_accepted_budgets
    budget_compatibility = len(shared_budgets) > 0

    # Conflict detection (if one rejects what the other loves)
    category_conflicts = user1_rejected_categories & user2_accepted_categories
    category_conflicts.update(user2_rejected_categories & user1_accepted_categories)

    compatibility_score = min(100, int(category_overlap * 100))

    return {
        "compatibility_score": compatibility_score,
        "shared_interests": list(shared_accepted),
        "category_overlap_percentage": round(category_overlap * 100, 1),
        "budget_compatible": budget_compatibility,
        "shared_budgets": list(shared_budgets),
        "category_conflicts": list(category_conflicts) if category_conflicts else [],
        "suggested_date_types": list(shared_accepted) if shared_accepted else ["adventure", "food", "culture"]
    }


# ==================== AUTHENTICATION ====================

def verify_token(token: str) -> TokenData:
    """Verify JWT token and return token data"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return TokenData(user_id=payload["user_id"], phone_number=payload["phone_number"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(authorization: str = Header(None)) -> TokenData:
    """Extract and verify current user from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "")
    return verify_token(token)


# ==================== FASTAPI ROUTER ====================

router = APIRouter(prefix="/api/partner", tags=["partner"])


@router.post("/invite", response_model=Dict[str, str])
async def create_invite(user: TokenData = Depends(get_current_user)):
    """
    Generate a unique invite code for the current user.
    Store in partner_connections with status='pending'.
    Returns the invite code.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if user already has a pending or active partnership
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow('''
            SELECT * FROM partner_connections
            WHERE (user_id = $1 OR partner_user_id = $1)
            AND status IN ('pending', 'accepted')
        ''', user.user_id)

        if existing:
            raise HTTPException(
                status_code=400,
                detail="You already have a pending invitation or active partnership"
            )

        # Generate unique invite code
        max_attempts = 10
        for _ in range(max_attempts):
            invite_code = generate_invite_code()

            existing_code = await conn.fetchrow(
                "SELECT id FROM partner_connections WHERE invite_code = $1",
                invite_code
            )

            if not existing_code:
                break
        else:
            raise HTTPException(status_code=500, detail="Failed to generate unique invite code")

        # Create connection record
        connection_id = str(uuid.uuid4())
        await conn.execute('''
            INSERT INTO partner_connections (id, user_id, invite_code, status)
            VALUES ($1, $2, $3, $4)
        ''', connection_id, user.user_id, invite_code, 'pending')

        logger.info(f"Invite code created for user {user.user_id}: {invite_code}")

        return {"invite_code": invite_code}


@router.post("/accept", response_model=Dict[str, Any])
async def accept_invite(body: Dict[str, str], user: TokenData = Depends(get_current_user)):
    """
    Accept an invite code.
    Body: {invite_code: "ABC-XYZ"}

    Looks up the connection, sets partner_user_id to current user,
    status='accepted', accepted_at=now().
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    invite_code = body.get("invite_code", "").strip().upper()

    if not invite_code:
        raise HTTPException(status_code=400, detail="invite_code is required")

    async with db_pool.acquire() as conn:
        # Find the connection by invite code
        connection = await conn.fetchrow('''
            SELECT * FROM partner_connections WHERE invite_code = $1
        ''', invite_code)

        if not connection:
            raise HTTPException(status_code=404, detail="Invite code not found")

        if connection['status'] != 'pending':
            raise HTTPException(
                status_code=400,
                detail=f"This invite code has already been {connection['status']}"
            )

        # Validate: can't pair with yourself
        if connection['user_id'] == user.user_id:
            raise HTTPException(status_code=400, detail="You cannot pair with yourself")

        # Check if user already has an active partnership
        existing = await conn.fetchrow('''
            SELECT * FROM partner_connections
            WHERE (user_id = $1 OR partner_user_id = $1)
            AND status = 'accepted'
        ''', user.user_id)

        if existing:
            raise HTTPException(
                status_code=400,
                detail="You already have an active partnership. Disconnect first."
            )

        # Accept the invitation
        now = datetime.utcnow()
        await conn.execute('''
            UPDATE partner_connections
            SET partner_user_id = $1, status = $2, accepted_at = $3
            WHERE id = $4
        ''', user.user_id, 'accepted', now, connection['id'])

        logger.info(f"Partnership accepted: {connection['user_id']} + {user.user_id}")

        # Get partner user info
        partner_user = await get_user_by_id(connection['user_id'])

        return {
            "status": "accepted",
            "connection_id": connection['id'],
            "partner": {
                "id": partner_user['id'],
                "name": partner_user['name'],
                "phone_number": partner_user['phone_number']
            },
            "accepted_at": now.isoformat()
        }


@router.get("/status", response_model=Dict[str, Any])
async def get_partnership_status(user: TokenData = Depends(get_current_user)):
    """
    Get current partnership status.
    Returns: partner info (name, id), connection status,
    or "not_connected" if no partner.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    partnership = await get_active_partnership(user.user_id)

    if not partnership:
        return {
            "status": "not_connected",
            "partner": None,
            "connection_status": "none"
        }

    # Determine which user is the partner
    if partnership['user_id'] == user.user_id:
        partner_id = partnership['partner_user_id']
    else:
        partner_id = partnership['user_id']

    partner_user = await get_user_by_id(partner_id)

    return {
        "status": "connected",
        "connection_status": partnership['status'],
        "connection_id": partnership['id'],
        "partner": {
            "id": partner_user['id'],
            "name": partner_user['name'],
            "phone_number": partner_user['phone_number']
        },
        "connected_since": partnership['accepted_at'].isoformat() if partnership['accepted_at'] else None
    }


@router.delete("/disconnect", response_model=Dict[str, str])
async def disconnect_partnership(user: TokenData = Depends(get_current_user)):
    """
    End the partnership. Deletes the connection and shared wishlist.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    partnership = await get_active_partnership(user.user_id)

    if not partnership:
        raise HTTPException(status_code=404, detail="No active partnership found")

    async with db_pool.acquire() as conn:
        # Delete shared wishlist items first (due to foreign key)
        await conn.execute(
            "DELETE FROM shared_wishlist WHERE connection_id = $1",
            partnership['id']
        )

        # Delete the partnership
        await conn.execute(
            "DELETE FROM partner_connections WHERE id = $1",
            partnership['id']
        )

        logger.info(f"Partnership disconnected: {partnership['id']}")

    return {"status": "disconnected", "message": "Partnership ended successfully"}


@router.post("/wishlist/share", response_model=Dict[str, Any])
async def share_wishlist_item(
    body: Dict[str, Any],
    user: TokenData = Depends(get_current_user)
):
    """
    Share a date idea with partner.
    Body: {date_idea_id: "...", notes: "Let's do this!"}
    Inserts into shared_wishlist.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    date_idea_id = body.get("date_idea_id")
    notes = body.get("notes", "")

    if not date_idea_id:
        raise HTTPException(status_code=400, detail="date_idea_id is required")

    partnership = await get_active_partnership(user.user_id)

    if not partnership:
        raise HTTPException(status_code=400, detail="You must be connected with a partner first")

    async with db_pool.acquire() as conn:
        # Verify the date idea exists
        idea = await conn.fetchrow(
            "SELECT id, title FROM date_ideas WHERE id = $1",
            date_idea_id
        )

        if not idea:
            raise HTTPException(status_code=404, detail="Date idea not found")

        # Add to shared wishlist
        share_id = str(uuid.uuid4())
        now = datetime.utcnow()

        await conn.execute('''
            INSERT INTO shared_wishlist (id, connection_id, user_id, date_idea_id, notes, shared_at)
            VALUES ($1, $2, $3, $4, $5, $6)
        ''', share_id, partnership['id'], user.user_id, date_idea_id, notes, now)

        logger.info(f"Wishlist item shared: {date_idea_id} by user {user.user_id}")

        return {
            "status": "shared",
            "share_id": share_id,
            "idea": {
                "id": idea['id'],
                "title": idea['title']
            },
            "notes": notes,
            "shared_at": now.isoformat()
        }


@router.get("/wishlist", response_model=Dict[str, Any])
async def get_shared_wishlist(user: TokenData = Depends(get_current_user)):
    """
    Get shared wishlist between partners.
    Returns ideas with who shared them.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    partnership = await get_active_partnership(user.user_id)

    if not partnership:
        return {
            "status": "no_partnership",
            "items": [],
            "shared_by_me": [],
            "shared_by_partner": []
        }

    # Determine partner_id
    partner_id = partnership['partner_user_id'] if partnership['user_id'] == user.user_id else partnership['user_id']

    async with db_pool.acquire() as conn:
        # Get all shared items
        items = await conn.fetch('''
            SELECT sw.id, sw.user_id, sw.date_idea_id, sw.notes, sw.shared_at,
                   di.title, di.description, di.category, di.budget_estimate,
                   di.duration, di.image_url
            FROM shared_wishlist sw
            JOIN date_ideas di ON sw.date_idea_id = di.id
            WHERE sw.connection_id = $1
            ORDER BY sw.shared_at DESC
        ''', partnership['id'])

        # Get user info for each sharer
        user_info = {}
        for item in items:
            if item['user_id'] not in user_info:
                user_data = await get_user_by_id(item['user_id'])
                user_info[item['user_id']] = user_data

        # Structure response
        shared_by_me = []
        shared_by_partner = []

        for item in items:
            item_dict = dict(item)
            shared_item = {
                "id": item_dict['id'],
                "date_idea": {
                    "id": item_dict['date_idea_id'],
                    "title": item_dict['title'],
                    "description": item_dict['description'],
                    "category": item_dict['category'],
                    "budget_estimate": item_dict['budget_estimate'],
                    "duration": item_dict['duration'],
                    "image_url": item_dict['image_url']
                },
                "notes": item_dict['notes'],
                "shared_at": item_dict['shared_at'].isoformat(),
                "shared_by": user_info[item_dict['user_id']]['name']
            }

            if item_dict['user_id'] == user.user_id:
                shared_by_me.append(shared_item)
            else:
                shared_by_partner.append(shared_item)

        return {
            "status": "success",
            "total_items": len(items),
            "items": [dict(item) for item in items],
            "shared_by_me": shared_by_me,
            "shared_by_partner": shared_by_partner
        }


@router.get("/preferences", response_model=Dict[str, Any])
async def get_combined_preferences(user: TokenData = Depends(get_current_user)):
    """
    Get combined preference profile of both partners.
    Merged interests, overlapping categories from accept/reject history,
    budget compatibility.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    partnership = await get_active_partnership(user.user_id)

    if not partnership:
        raise HTTPException(status_code=400, detail="You must be connected with a partner")

    partner_id = partnership['partner_user_id'] if partnership['user_id'] == user.user_id else partnership['user_id']

    async with db_pool.acquire() as conn:
        # Get both users' profiles
        user_profile = await conn.fetchrow(
            "SELECT personality_type, interests, budget_preference FROM users WHERE id = $1",
            user.user_id
        )

        partner_profile = await conn.fetchrow(
            "SELECT personality_type, interests, budget_preference FROM users WHERE id = $1",
            partner_id
        )

    # Get interaction history
    user_interactions = await get_user_idea_interactions(user.user_id)
    partner_interactions = await get_user_idea_interactions(partner_id)

    # Calculate compatibility
    compatibility = calculate_compatibility(user_interactions, partner_interactions)

    # Merge interests
    user_interests = set(user_profile['interests'] or []) if user_profile else set()
    partner_interests = set(partner_profile['interests'] or []) if partner_profile else set()

    shared_interests = list(user_interests & partner_interests)
    all_interests = list(user_interests | partner_interests)

    return {
        "status": "success",
        "user": {
            "personality_type": user_profile['personality_type'] if user_profile else None,
            "interests": list(user_interests),
            "budget_preference": user_profile['budget_preference'] if user_profile else None
        },
        "partner": {
            "personality_type": partner_profile['personality_type'] if partner_profile else None,
            "interests": list(partner_interests),
            "budget_preference": partner_profile['budget_preference'] if partner_profile else None
        },
        "combined": {
            "shared_interests": shared_interests,
            "all_interests": all_interests,
            "budget_compatibility": compatibility['budget_compatible'],
            "shared_budgets": compatibility['shared_budgets']
        },
        "compatibility": compatibility
    }


@router.get("/compatibility", response_model=Dict[str, Any])
async def get_compatibility_report(user: TokenData = Depends(get_current_user)):
    """
    Get compatibility report: shared interests, category overlap,
    budget alignment, suggested date types.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    partnership = await get_active_partnership(user.user_id)

    if not partnership:
        raise HTTPException(status_code=400, detail="You must be connected with a partner")

    partner_id = partnership['partner_user_id'] if partnership['user_id'] == user.user_id else partnership['user_id']

    # Get interaction history
    user_interactions = await get_user_idea_interactions(user.user_id)
    partner_interactions = await get_user_idea_interactions(partner_id)

    # Calculate compatibility
    compatibility = calculate_compatibility(user_interactions, partner_interactions)

    # Get user names for the report
    user_data = await get_user_by_id(user.user_id)
    partner_data = await get_user_by_id(partner_id)

    return {
        "status": "success",
        "you": user_data['name'],
        "partner": partner_data['name'],
        "compatibility_score": compatibility['compatibility_score'],
        "compatibility_level": (
            "perfect_match" if compatibility['compatibility_score'] >= 80
            else "great_match" if compatibility['compatibility_score'] >= 60
            else "good_match" if compatibility['compatibility_score'] >= 40
            else "potential_match"
        ),
        "shared_interests": compatibility['shared_interests'],
        "category_overlap_percentage": compatibility['category_overlap_percentage'],
        "budget_compatible": compatibility['budget_compatible'],
        "shared_budgets": compatibility['shared_budgets'],
        "category_conflicts": compatibility['category_conflicts'],
        "suggested_date_types": compatibility['suggested_date_types'],
        "recommendations": generate_compatibility_recommendations(compatibility)
    }


def generate_compatibility_recommendations(compatibility: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on compatibility data"""
    recommendations = []

    # High compatibility
    if compatibility['compatibility_score'] >= 80:
        recommendations.append("You two have excellent compatibility! Plan your date night!")

    # Budget alignment
    if compatibility['budget_compatible']:
        recommendations.append(
            f"You share budget preferences: {', '.join(compatibility['shared_budgets']) or 'flexible budgets'}"
        )
    else:
        recommendations.append("Consider mixing different budget ranges to explore new experiences together")

    # Shared interests
    if compatibility['shared_interests']:
        recommendations.append(
            f"Your shared interests: {', '.join(compatibility['shared_interests'][:3])}"
        )
    else:
        recommendations.append("Try exploring each other's interests to discover new date experiences")

    # Conflicts
    if compatibility['category_conflicts']:
        recommendations.append(
            f"Avoid: {', '.join(compatibility['category_conflicts'][:2])} (mismatched interests)"
        )

    # Suggested types
    if compatibility['suggested_date_types']:
        recommendations.append(
            f"Try these date types: {', '.join(compatibility['suggested_date_types'][:3])}"
        )

    return recommendations
