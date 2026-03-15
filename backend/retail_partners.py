"""
Arrow Retail Partner System

Revenue-generating partner network for local businesses:
- Retailer onboarding with business profiles
- Tier system: Free, Premium ($), Elite ($$) — paid partners get idea boosting
- Venue-linked date ideas with real business info (no stock images)
- Priority placement in recommendations based on tier
- Analytics dashboard for partners (views, clicks, bookings)
- Admin dashboard for managing partner network

Nashville-first launch with scalable city expansion.
"""

from fastapi import APIRouter, HTTPException, Query, Header, Depends
from fastapi.responses import HTMLResponse
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid
import json
import logging

logger = logging.getLogger(__name__)

db_pool: Optional[asyncpg.Pool] = None
router = APIRouter()


def set_db_pool(pool: asyncpg.Pool):
    global db_pool
    db_pool = pool


# ==================== MODELS ====================

class RetailerOnboard(BaseModel):
    """Onboard a new retail partner"""
    business_name: str = Field(..., min_length=2, max_length=255)
    business_type: str  # restaurant, bar, spa, activity_center, venue, shop, experience, other
    description: str
    address: str
    city: str = "Nashville"
    state: str = "TN"
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    contact_name: str
    contact_email: str
    tier: str = "free"  # free, premium, elite
    categories: List[str] = []  # romantic, foodie, adventure, etc.
    price_range: str = "medium"  # low, medium, high
    photos: List[str] = []  # Business-provided photo URLs (NO stock images)
    operating_hours: Optional[str] = None
    special_offers: Optional[str] = None  # "10% off for Arrow users"


class RetailerUpdate(BaseModel):
    business_name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    tier: Optional[str] = None
    categories: Optional[List[str]] = None
    price_range: Optional[str] = None
    photos: Optional[List[str]] = None
    operating_hours: Optional[str] = None
    special_offers: Optional[str] = None
    is_active: Optional[bool] = None


class RetailerIdeaCreate(BaseModel):
    """Create a date idea linked to a retail partner"""
    retailer_id: str
    title: str
    description: str
    category: str = "fun"
    budget: str = "medium"
    duration: Optional[str] = None
    location_type: str = "indoor"
    tags: List[str] = []
    photos: List[str] = []  # Must be real photos, not stock
    special_offer: Optional[str] = None  # "Free dessert for Arrow couples"
    booking_url: Optional[str] = None
    valid_until: Optional[str] = None  # Expiry for time-limited offers


# ==================== TIER SYSTEM ====================

TIER_CONFIG = {
    "free": {
        "name": "Free Partner",
        "monthly_cost": 0,
        "boost_multiplier": 1.0,    # No boost
        "max_ideas": 3,              # Can list 3 date ideas
        "featured_slots": 0,         # No featured placement
        "analytics": "basic",        # Views only
        "badge": None,
        "priority_in_search": 0,
    },
    "premium": {
        "name": "Premium Partner",
        "monthly_cost": 99,
        "boost_multiplier": 2.0,     # 2x more likely to appear
        "max_ideas": 10,
        "featured_slots": 2,          # 2 featured slots per month
        "analytics": "standard",      # Views + clicks + demographics
        "badge": "premium",
        "priority_in_search": 10,
    },
    "elite": {
        "name": "Elite Partner",
        "monthly_cost": 249,
        "boost_multiplier": 4.0,     # 4x more likely to appear
        "max_ideas": 25,
        "featured_slots": 8,          # 8 featured slots per month
        "analytics": "full",          # Views + clicks + demographics + conversion + heatmaps
        "badge": "elite",
        "priority_in_search": 25,
    },
}


# ==================== TABLE INIT ====================

async def init_retail_tables():
    """Initialize retail partner tables."""
    async with db_pool.acquire() as conn:
        # Retail partners table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS retail_partners (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                business_name VARCHAR(255) NOT NULL,
                business_type VARCHAR(50) NOT NULL,
                description TEXT,
                address TEXT,
                city VARCHAR(100) DEFAULT 'Nashville',
                state VARCHAR(10) DEFAULT 'TN',
                zip_code VARCHAR(20),
                phone VARCHAR(30),
                website TEXT,
                instagram VARCHAR(100),
                contact_name VARCHAR(255),
                contact_email VARCHAR(255),
                tier VARCHAR(20) DEFAULT 'free',
                categories TEXT[],
                price_range VARCHAR(20) DEFAULT 'medium',
                photos TEXT[],
                operating_hours TEXT,
                special_offers TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                total_views INTEGER DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                total_bookings INTEGER DEFAULT 0,
                rating NUMERIC(3,2) DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Retailer-linked date ideas
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS retailer_ideas (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                retailer_id UUID REFERENCES retail_partners(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                budget VARCHAR(20),
                duration VARCHAR(50),
                location_type VARCHAR(50),
                tags TEXT[],
                photos TEXT[],
                special_offer TEXT,
                booking_url TEXT,
                valid_until TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                image_status VARCHAR(20) DEFAULT 'pending',
                views INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Analytics events
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS retail_analytics (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                retailer_id UUID REFERENCES retail_partners(id) ON DELETE CASCADE,
                idea_id UUID,
                event_type VARCHAR(30) NOT NULL,
                user_id UUID,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

    logger.info("Retail partner tables initialized")


# ==================== PARTNER ONBOARDING ====================

@router.post("/api/retail/onboard")
async def onboard_retailer(data: RetailerOnboard):
    """Onboard a new retail partner."""
    # Validate tier
    if data.tier not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Choose: {', '.join(TIER_CONFIG.keys())}")

    async with db_pool.acquire() as conn:
        # Check duplicate
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM retail_partners WHERE LOWER(business_name) = LOWER($1) AND city = $2",
            data.business_name, data.city
        )
        if existing > 0:
            raise HTTPException(status_code=409, detail="Business already registered in this city")

        partner_id = uuid.uuid4()
        await conn.execute('''
            INSERT INTO retail_partners
            (id, business_name, business_type, description, address, city, state, zip_code,
             phone, website, instagram, contact_name, contact_email, tier, categories,
             price_range, photos, operating_hours, special_offers)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
        ''', partner_id, data.business_name, data.business_type, data.description,
            data.address, data.city, data.state, data.zip_code,
            data.phone, data.website, data.instagram, data.contact_name,
            data.contact_email, data.tier, data.categories,
            data.price_range, data.photos, data.operating_hours, data.special_offers)

    tier_info = TIER_CONFIG[data.tier]
    return {
        "success": True,
        "partner_id": str(partner_id),
        "tier": data.tier,
        "tier_name": tier_info["name"],
        "max_ideas": tier_info["max_ideas"],
        "boost_multiplier": tier_info["boost_multiplier"],
        "message": f"Welcome to Arrow! {data.business_name} onboarded as {tier_info['name']}."
    }


@router.get("/api/retail/partners")
async def list_partners(
    city: str = "Nashville",
    tier: Optional[str] = None,
    business_type: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50
):
    """List retail partners with filters."""
    query = "SELECT * FROM retail_partners WHERE city = $1"
    params: list = [city]
    idx = 1

    if active_only:
        query += " AND is_active = TRUE"

    if tier:
        idx += 1
        query += f" AND tier = ${idx}"
        params.append(tier)

    if business_type:
        idx += 1
        query += f" AND business_type = ${idx}"
        params.append(business_type)

    if category:
        idx += 1
        query += f" AND $${idx} = ANY(categories)"
        # Fix: use proper array containment
        query = query.replace(f"$${idx} = ANY(categories)", f"${idx} = ANY(categories)")
        params.append(category)

    # Paid partners first, then by rating
    query += " ORDER BY CASE tier WHEN 'elite' THEN 0 WHEN 'premium' THEN 1 ELSE 2 END, rating DESC"
    idx += 1
    query += f" LIMIT ${idx}"
    params.append(limit)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    partners = []
    for row in rows:
        p = dict(row)
        p['id'] = str(p['id'])
        p['tier_info'] = TIER_CONFIG.get(p.get('tier', 'free'))
        partners.append(p)

    return {"partners": partners, "total": len(partners), "city": city}


@router.get("/api/retail/partner/{partner_id}")
async def get_partner(partner_id: str):
    """Get a single retail partner with their linked ideas."""
    async with db_pool.acquire() as conn:
        partner = await conn.fetchrow(
            "SELECT * FROM retail_partners WHERE id = $1", uuid.UUID(partner_id)
        )
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")

        ideas = await conn.fetch(
            "SELECT * FROM retailer_ideas WHERE retailer_id = $1 AND is_active = TRUE ORDER BY created_at DESC",
            uuid.UUID(partner_id)
        )

        # Record view
        await conn.execute(
            "UPDATE retail_partners SET total_views = total_views + 1 WHERE id = $1",
            uuid.UUID(partner_id)
        )
        await conn.execute('''
            INSERT INTO retail_analytics (retailer_id, event_type)
            VALUES ($1, 'profile_view')
        ''', uuid.UUID(partner_id))

    p = dict(partner)
    p['id'] = str(p['id'])
    p['tier_info'] = TIER_CONFIG.get(p.get('tier', 'free'))
    p['ideas'] = []
    for idea in ideas:
        i = dict(idea)
        i['id'] = str(i['id'])
        i['retailer_id'] = str(i['retailer_id'])
        p['ideas'].append(i)

    return p


@router.put("/api/retail/partner/{partner_id}")
async def update_partner(partner_id: str, data: RetailerUpdate):
    """Update retail partner info."""
    updates = []
    params = []
    idx = 0

    for field in ['business_name', 'description', 'address', 'phone', 'website',
                   'instagram', 'tier', 'price_range', 'operating_hours', 'special_offers']:
        val = getattr(data, field, None)
        if val is not None:
            idx += 1
            updates.append(f"{field} = ${idx}")
            params.append(val)

    if data.categories is not None:
        idx += 1
        updates.append(f"categories = ${idx}")
        params.append(data.categories)

    if data.photos is not None:
        idx += 1
        updates.append(f"photos = ${idx}")
        params.append(data.photos)

    if data.is_active is not None:
        idx += 1
        updates.append(f"is_active = ${idx}")
        params.append(data.is_active)

    if not updates:
        return {"success": True, "message": "No changes"}

    updates.append("updated_at = NOW()")
    idx += 1
    params.append(uuid.UUID(partner_id))

    query = f"UPDATE retail_partners SET {', '.join(updates)} WHERE id = ${idx}"

    async with db_pool.acquire() as conn:
        await conn.execute(query, *params)

    return {"success": True, "message": "Partner updated"}


@router.delete("/api/retail/partner/{partner_id}")
async def deactivate_partner(partner_id: str):
    """Deactivate (soft-delete) a retail partner."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE retail_partners SET is_active = FALSE, updated_at = NOW() WHERE id = $1",
            uuid.UUID(partner_id)
        )
    return {"success": True, "message": "Partner deactivated"}


# ==================== RETAILER IDEAS ====================

@router.post("/api/retail/idea")
async def create_retailer_idea(data: RetailerIdeaCreate):
    """Create a date idea linked to a retail partner."""
    retailer_uuid = uuid.UUID(data.retailer_id)

    async with db_pool.acquire() as conn:
        # Verify retailer exists
        partner = await conn.fetchrow(
            "SELECT tier, is_active FROM retail_partners WHERE id = $1", retailer_uuid
        )
        if not partner:
            raise HTTPException(status_code=404, detail="Retailer not found")
        if not partner['is_active']:
            raise HTTPException(status_code=400, detail="Retailer is inactive")

        # Check idea limit for tier
        tier = partner['tier']
        max_ideas = TIER_CONFIG.get(tier, {}).get('max_ideas', 3)
        current_count = await conn.fetchval(
            "SELECT COUNT(*) FROM retailer_ideas WHERE retailer_id = $1 AND is_active = TRUE",
            retailer_uuid
        )
        if current_count >= max_ideas:
            raise HTTPException(
                status_code=403,
                detail=f"{tier.title()} tier allows max {max_ideas} ideas. Upgrade tier for more."
            )

        # Determine image status — if photos look like stock, flag for review
        image_status = "approved"
        if not data.photos:
            image_status = "needs_image"
        else:
            for photo in data.photos:
                if _is_likely_stock_image(photo):
                    image_status = "pending_review"
                    break

        valid_until = None
        if data.valid_until:
            try:
                valid_until = datetime.strptime(data.valid_until, "%Y-%m-%d")
            except ValueError:
                pass

        idea_id = uuid.uuid4()
        await conn.execute('''
            INSERT INTO retailer_ideas
            (id, retailer_id, title, description, category, budget, duration,
             location_type, tags, photos, special_offer, booking_url, valid_until, image_status)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        ''', idea_id, retailer_uuid, data.title, data.description,
            data.category, data.budget, data.duration, data.location_type,
            data.tags, data.photos, data.special_offer, data.booking_url,
            valid_until, image_status)

        # Also insert into main date_ideas table for discoverability
        # (only if images are approved)
        if image_status == "approved":
            await _sync_idea_to_main_table(conn, idea_id, data, retailer_uuid)

    return {
        "success": True,
        "idea_id": str(idea_id),
        "image_status": image_status,
        "message": "Idea created" + (" — images flagged for admin review" if image_status == "pending_review" else "")
    }


async def _sync_idea_to_main_table(conn, idea_id, data, retailer_uuid):
    """Push a retailer idea into the main date_ideas table."""
    await conn.execute('''
        INSERT INTO date_ideas
        (title, description, category, budget, duration, location_type,
         image_url, tags, is_trending, source, updated_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9, $10)
    ''', data.title, data.description, data.category, data.budget,
        data.duration, data.location_type,
        data.photos[0] if data.photos else '',
        data.tags, f'retailer:{str(retailer_uuid)}',
        f'retailer:{str(retailer_uuid)}')


def _is_likely_stock_image(url: str) -> bool:
    """Detect if a URL is likely from a stock image site."""
    stock_domains = [
        'unsplash.com', 'pexels.com', 'pixabay.com', 'shutterstock.com',
        'istockphoto.com', 'gettyimages.com', 'stock.adobe.com', 'dreamstime.com',
        'depositphotos.com', '123rf.com', 'freepik.com', 'stocksy.com',
        'alamy.com', 'bigstockphoto.com', 'canstockphoto.com',
    ]
    url_lower = url.lower()
    return any(domain in url_lower for domain in stock_domains)


@router.get("/api/retail/ideas")
async def list_retailer_ideas(
    city: str = "Nashville",
    category: Optional[str] = None,
    budget: Optional[str] = None,
    include_offers: bool = False,
    limit: int = 20
):
    """Get date ideas from retail partners — paid partners boosted."""
    query = """
        SELECT ri.*, rp.business_name, rp.address, rp.tier, rp.city,
               rp.rating, rp.photos as business_photos, rp.special_offers as business_offer
        FROM retailer_ideas ri
        JOIN retail_partners rp ON ri.retailer_id = rp.id
        WHERE rp.city = $1 AND ri.is_active = TRUE AND rp.is_active = TRUE
          AND ri.image_status = 'approved'
    """
    params: list = [city]
    idx = 1

    if category:
        idx += 1
        query += f" AND ri.category = ${idx}"
        params.append(category)

    if budget:
        idx += 1
        query += f" AND ri.budget = ${idx}"
        params.append(budget)

    if include_offers:
        query += " AND ri.special_offer IS NOT NULL"

    # BOOST: paid partners appear first, weighted by tier
    query += """
        ORDER BY
            CASE rp.tier WHEN 'elite' THEN 0 WHEN 'premium' THEN 1 ELSE 2 END,
            rp.rating DESC,
            ri.created_at DESC
    """
    idx += 1
    query += f" LIMIT ${idx}"
    params.append(limit)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    ideas = []
    for row in rows:
        i = dict(row)
        i['id'] = str(i['id'])
        i['retailer_id'] = str(i['retailer_id'])
        i['is_boosted'] = i.get('tier') in ('premium', 'elite')
        i['boost_tier'] = i.get('tier')
        ideas.append(i)

    return {"ideas": ideas, "total": len(ideas), "city": city}


# ==================== IMAGE APPROVAL PIPELINE ====================

@router.get("/admin/retail/image-review")
async def get_pending_images(limit: int = 50):
    """Get retailer ideas with images pending admin review."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT ri.*, rp.business_name, rp.tier
            FROM retailer_ideas ri
            JOIN retail_partners rp ON ri.retailer_id = rp.id
            WHERE ri.image_status IN ('pending_review', 'needs_image')
            ORDER BY ri.created_at ASC
            LIMIT $1
        """, limit)

    items = []
    for row in rows:
        i = dict(row)
        i['id'] = str(i['id'])
        i['retailer_id'] = str(i['retailer_id'])
        items.append(i)

    return {"pending": items, "total": len(items)}


@router.post("/admin/retail/image-review/{idea_id}/approve")
async def approve_idea_images(idea_id: str):
    """Approve an idea's images and push to main database."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM retailer_ideas WHERE id = $1", uuid.UUID(idea_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")

        await conn.execute(
            "UPDATE retailer_ideas SET image_status = 'approved', updated_at = NOW() WHERE id = $1",
            uuid.UUID(idea_id)
        )

        # Sync to main date_ideas
        await conn.execute('''
            INSERT INTO date_ideas
            (title, description, category, budget, duration, location_type,
             image_url, tags, is_trending, source, updated_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9, 'admin_approved')
        ''', row['title'], row['description'], row['category'], row['budget'],
            row['duration'], row['location_type'],
            row['photos'][0] if row['photos'] else '',
            row['tags'], f"retailer:{str(row['retailer_id'])}")

    return {"success": True, "message": "Images approved and idea published"}


@router.post("/admin/retail/image-review/{idea_id}/reject")
async def reject_idea_images(idea_id: str, reason: str = "Stock images not allowed"):
    """Reject an idea's images — partner must re-upload."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE retailer_ideas SET image_status = 'rejected', updated_at = NOW() WHERE id = $1",
            uuid.UUID(idea_id)
        )
    return {"success": True, "message": f"Rejected: {reason}"}


@router.post("/admin/retail/image-review/{idea_id}/update-image")
async def admin_update_image(idea_id: str, new_photo_url: str):
    """Admin replaces stock image with a real photo, then auto-approves."""
    if _is_likely_stock_image(new_photo_url):
        raise HTTPException(status_code=400, detail="New URL also looks like a stock image")

    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE retailer_ideas
            SET photos = ARRAY[$1], image_status = 'approved', updated_at = NOW()
            WHERE id = $2
        """, new_photo_url, uuid.UUID(idea_id))

        # Sync to main table
        row = await conn.fetchrow("SELECT * FROM retailer_ideas WHERE id = $1", uuid.UUID(idea_id))
        if row:
            await conn.execute('''
                INSERT INTO date_ideas
                (title, description, category, budget, duration, location_type,
                 image_url, tags, source, updated_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'admin_updated')
            ''', row['title'], row['description'], row['category'], row['budget'],
                row['duration'], row['location_type'], new_photo_url,
                row['tags'], f"retailer:{str(row['retailer_id'])}")

    return {"success": True, "message": "Image updated and idea published"}


# ==================== ANALYTICS ====================

@router.post("/api/retail/analytics/track")
async def track_event(
    retailer_id: str,
    event_type: str,  # view, click, bookmark, booking
    idea_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """Track an analytics event for a retail partner."""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO retail_analytics (retailer_id, idea_id, event_type, user_id)
            VALUES ($1, $2, $3, $4)
        ''', uuid.UUID(retailer_id),
            uuid.UUID(idea_id) if idea_id else None,
            event_type,
            uuid.UUID(user_id) if user_id else None)

        # Update counters
        if event_type == 'view':
            await conn.execute("UPDATE retail_partners SET total_views = total_views + 1 WHERE id = $1", uuid.UUID(retailer_id))
        elif event_type == 'click':
            await conn.execute("UPDATE retail_partners SET total_clicks = total_clicks + 1 WHERE id = $1", uuid.UUID(retailer_id))
            if idea_id:
                await conn.execute("UPDATE retailer_ideas SET clicks = clicks + 1 WHERE id = $1", uuid.UUID(idea_id))
        elif event_type == 'booking':
            await conn.execute("UPDATE retail_partners SET total_bookings = total_bookings + 1 WHERE id = $1", uuid.UUID(retailer_id))

    return {"success": True, "tracked": event_type}


@router.get("/api/retail/analytics/{partner_id}")
async def get_partner_analytics(partner_id: str, days: int = 30):
    """Get analytics for a retail partner."""
    since = datetime.utcnow() - timedelta(days=days)

    async with db_pool.acquire() as conn:
        partner = await conn.fetchrow(
            "SELECT business_name, tier, total_views, total_clicks, total_bookings, rating FROM retail_partners WHERE id = $1",
            uuid.UUID(partner_id)
        )
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")

        # Event breakdown
        events = await conn.fetch("""
            SELECT event_type, COUNT(*) as count
            FROM retail_analytics
            WHERE retailer_id = $1 AND created_at >= $2
            GROUP BY event_type
        """, uuid.UUID(partner_id), since)

        # Daily trend
        daily = await conn.fetch("""
            SELECT DATE(created_at) as day, event_type, COUNT(*) as count
            FROM retail_analytics
            WHERE retailer_id = $1 AND created_at >= $2
            GROUP BY DATE(created_at), event_type
            ORDER BY day DESC
        """, uuid.UUID(partner_id), since)

        # Top performing ideas
        top_ideas = await conn.fetch("""
            SELECT id, title, views, clicks
            FROM retailer_ideas
            WHERE retailer_id = $1 AND is_active = TRUE
            ORDER BY clicks DESC
            LIMIT 5
        """, uuid.UUID(partner_id))

    tier = partner['tier']
    tier_info = TIER_CONFIG.get(tier, {})

    # Restrict analytics based on tier
    analytics_level = tier_info.get('analytics', 'basic')

    result = {
        "business_name": partner['business_name'],
        "tier": tier,
        "period_days": days,
        "total_views": partner['total_views'],
        "total_clicks": partner['total_clicks'],
        "total_bookings": partner['total_bookings'],
        "click_through_rate": round(partner['total_clicks'] / max(partner['total_views'], 1) * 100, 1),
        "events": {row['event_type']: row['count'] for row in events},
    }

    if analytics_level in ('standard', 'full'):
        result["daily_trend"] = [
            {"day": str(row['day']), "event": row['event_type'], "count": row['count']}
            for row in daily
        ]
        result["top_ideas"] = [
            {"id": str(row['id']), "title": row['title'], "views": row['views'], "clicks": row['clicks']}
            for row in top_ideas
        ]

    if analytics_level == 'full':
        result["conversion_rate"] = round(
            partner['total_bookings'] / max(partner['total_clicks'], 1) * 100, 1
        )

    return result


# ==================== TIER MANAGEMENT ====================

@router.get("/api/retail/tiers")
async def get_tier_info():
    """Get tier pricing and features."""
    return {"tiers": TIER_CONFIG}


@router.post("/api/retail/partner/{partner_id}/upgrade")
async def upgrade_tier(partner_id: str, new_tier: str):
    """Upgrade a partner's tier."""
    if new_tier not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {new_tier}")

    async with db_pool.acquire() as conn:
        current = await conn.fetchval(
            "SELECT tier FROM retail_partners WHERE id = $1", uuid.UUID(partner_id)
        )
        if not current:
            raise HTTPException(status_code=404, detail="Partner not found")

        tier_order = {"free": 0, "premium": 1, "elite": 2}
        if tier_order.get(new_tier, 0) <= tier_order.get(current, 0):
            raise HTTPException(status_code=400, detail=f"Cannot downgrade from {current} to {new_tier} via upgrade endpoint")

        await conn.execute(
            "UPDATE retail_partners SET tier = $1, updated_at = NOW() WHERE id = $2",
            new_tier, uuid.UUID(partner_id)
        )

    return {
        "success": True,
        "previous_tier": current,
        "new_tier": new_tier,
        "tier_info": TIER_CONFIG[new_tier]
    }


# ==================== BOOSTED RECOMMENDATIONS ====================

async def get_boosted_ideas_for_prompt(city: str = "Nashville", limit: int = 3) -> List[Dict[str, Any]]:
    """
    Get paid partner ideas to inject into AI recommendations.
    Elite partners get more spots. Used by smart_algorithm prompt builder.
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT ri.title, ri.description, ri.category, ri.budget, ri.tags,
                   ri.special_offer, rp.business_name, rp.address, rp.tier
            FROM retailer_ideas ri
            JOIN retail_partners rp ON ri.retailer_id = rp.id
            WHERE rp.city = $1
              AND rp.is_active = TRUE
              AND ri.is_active = TRUE
              AND ri.image_status = 'approved'
              AND rp.tier IN ('premium', 'elite')
            ORDER BY
                CASE rp.tier WHEN 'elite' THEN 0 ELSE 1 END,
                RANDOM()
            LIMIT $2
        """, city, limit)

    return [dict(row) for row in rows]


# ==================== ADMIN DASHBOARD ====================

@router.get("/admin/retail", response_class=HTMLResponse)
async def retail_admin_dashboard():
    """Retail partner admin dashboard."""
    async with db_pool.acquire() as conn:
        total_partners = await conn.fetchval("SELECT COUNT(*) FROM retail_partners WHERE is_active = TRUE")
        premium_count = await conn.fetchval("SELECT COUNT(*) FROM retail_partners WHERE tier = 'premium' AND is_active = TRUE")
        elite_count = await conn.fetchval("SELECT COUNT(*) FROM retail_partners WHERE tier = 'elite' AND is_active = TRUE")
        pending_images = await conn.fetchval("SELECT COUNT(*) FROM retailer_ideas WHERE image_status IN ('pending_review', 'needs_image')")
        total_ideas = await conn.fetchval("SELECT COUNT(*) FROM retailer_ideas WHERE is_active = TRUE")
        total_revenue = premium_count * 99 + elite_count * 249

        # Top partners
        top = await conn.fetch("""
            SELECT business_name, tier, total_views, total_clicks, total_bookings, rating
            FROM retail_partners WHERE is_active = TRUE
            ORDER BY total_clicks DESC LIMIT 10
        """)

    top_rows = ""
    for r in top:
        tier_badge = f"<span class='tier-{r['tier']}'>{r['tier'].upper()}</span>"
        top_rows += f"""<tr>
            <td>{r['business_name']}</td><td>{tier_badge}</td>
            <td>{r['total_views']}</td><td>{r['total_clicks']}</td>
            <td>{r['total_bookings']}</td><td>{r['rating'] or '—'}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Arrow — Retail Partners</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Inter',sans-serif; background:#0f0f13; color:#e0e0e0; padding:24px; }}
  h1 {{ font-size:28px; color:#fff; margin-bottom:4px; }}
  h2 {{ font-size:16px; color:#888; margin-bottom:24px; font-weight:400; }}
  h3 {{ font-size:14px; color:#E83858; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px; }}

  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:16px; margin-bottom:32px; }}
  .stat {{ background:#1a1a22; border-radius:12px; padding:20px; text-align:center; }}
  .stat .num {{ font-size:32px; font-weight:700; color:#E83858; }}
  .stat .label {{ font-size:11px; color:#888; margin-top:4px; text-transform:uppercase; letter-spacing:1px; }}
  .stat.revenue .num {{ color:#4CAF50; }}

  .section {{ background:#1a1a22; border-radius:12px; padding:24px; margin-bottom:24px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:1px; padding:8px; border-bottom:1px solid #2a2a35; }}
  td {{ padding:8px; font-size:13px; border-bottom:1px solid #1f1f28; }}

  .tier-free {{ color:#888; }}
  .tier-premium {{ color:#FFD700; font-weight:600; }}
  .tier-elite {{ color:#E83858; font-weight:700; }}

  .btn {{ background:#E83858; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-size:13px; font-weight:600; }}
  .btn:hover {{ background:#d02e4c; }}
  .alert {{ background:#3a1a22; border:1px solid #E83858; border-radius:8px; padding:12px; margin-bottom:16px; font-size:13px; }}
</style>
</head><body>
<h1>Retail Partner Network</h1>
<h2>Nashville — Partner Management & Revenue Dashboard</h2>

<div class="stats">
  <div class="stat"><div class="num">{total_partners}</div><div class="label">Active Partners</div></div>
  <div class="stat"><div class="num">{premium_count}</div><div class="label">Premium ($99/mo)</div></div>
  <div class="stat"><div class="num">{elite_count}</div><div class="label">Elite ($249/mo)</div></div>
  <div class="stat revenue"><div class="num">${total_revenue:,}</div><div class="label">Monthly Revenue</div></div>
  <div class="stat"><div class="num">{total_ideas}</div><div class="label">Partner Ideas</div></div>
  <div class="stat" style="{'background:#3a1a22' if pending_images > 0 else ''}"><div class="num">{pending_images}</div><div class="label">Pending Images</div></div>
</div>

{"<div class='alert'>⚠ " + str(pending_images) + " ideas have stock images or missing images awaiting review. <a href='/admin/retail/image-review' style='color:#E83858'>Review now →</a></div>" if pending_images > 0 else ""}

<div class="section">
  <h3>Top Partners by Clicks</h3>
  <table>
    <tr><th>Business</th><th>Tier</th><th>Views</th><th>Clicks</th><th>Bookings</th><th>Rating</th></tr>
    {top_rows}
  </table>
</div>

</body></html>"""

    return HTMLResponse(content=html)
