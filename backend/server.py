from fastapi import FastAPI, APIRouter, HTTPException, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import random
from openai import AsyncOpenAI
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# Emergent LLM Key
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    otp: str

class UserProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone_number: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    personality_data: Optional[Dict[str, Any]] = {}
    preferences: Optional[Dict[str, Any]] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PersonalityQuestionnaire(BaseModel):
    user_id: str
    personality_type: str  # adventurous, romantic, chill, foodie, etc.
    interests: List[str]
    budget_range: str  # low, medium, high
    indoor_outdoor_preference: str  # indoor, outdoor, both
    favorite_activities: List[str]
    relationship_status: str  # dating, married, engaged

class DateIdea(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    category: str
    budget_estimate: str
    duration: str
    location_type: str
    image_url: Optional[str] = None
    is_trending: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WishlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    date_idea_id: str
    date_idea: Dict[str, Any]
    added_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    is_favorite: bool = False

class Connection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    connected_user_id: str
    connection_type: str  # partner, friend, family
    status: str  # pending, accepted
    invite_code: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Occasion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    person_name: str
    occasion_type: str  # birthday, anniversary, valentine, etc.
    date: datetime
    reminder_days_before: int = 7
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserBehavior(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    date_idea_id: str
    action: str  # liked, disliked, viewed, saved
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AIGenerationRequest(BaseModel):
    user_id: str
    count: int = 5
    occasion_type: Optional[str] = None

# ==================== HELPER FUNCTIONS ====================

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_otp():
    return str(random.randint(100000, 999999))

def generate_invite_code():
    return str(uuid.uuid4())[:8].upper()

async def generate_date_ideas_with_ai(user_profile: dict, personality: dict, count: int = 5) -> List[Dict[str, Any]]:
    """Generate personalized date ideas using AI"""
    try:
        # Build context from user profile and personality
        interests = personality.get('interests', [])
        budget = personality.get('budget_range', 'medium')
        indoor_outdoor = personality.get('indoor_outdoor_preference', 'both')
        personality_type = personality.get('personality_type', 'romantic')
        favorite_activities = personality.get('favorite_activities', [])
        
        prompt = f"""
You are a creative date planner for the USA market. Generate {count} unique and exciting date ideas based on this profile:

Personality Type: {personality_type}
Interests: {', '.join(interests)}
Budget Range: {budget}
Preference: {indoor_outdoor}
Favorite Activities: {', '.join(favorite_activities)}

For each date idea, provide:
1. A catchy title
2. Detailed description (2-3 sentences)
3. Category (romantic, adventure, foodie, cultural, relaxing, fun, etc.)
4. Budget estimate ($ for low, $$ for medium, $$$ for high)
5. Duration estimate (1-2 hours, half day, full day)
6. Location type (indoor, outdoor, both)

Make ideas creative, practical, and suitable for current trends. Format as JSON array with fields: title, description, category, budget_estimate, duration, location_type

IMPORTANT: Return ONLY valid JSON array, no additional text.
"""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"date-ideas-{user_profile.get('id', 'unknown')}",
            system_message="You are a creative date planning assistant. Always respond with valid JSON only."
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse response
        import json
        response_text = response.strip()
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        
        ideas = json.loads(response_text)
        
        # Add metadata
        for idea in ideas:
            idea['id'] = str(uuid.uuid4())
            idea['is_trending'] = False
            idea['created_at'] = datetime.utcnow().isoformat()
            idea['image_url'] = None
        
        return ideas
    
    except Exception as e:
        logger.error(f"Error generating date ideas with AI: {str(e)}")
        # Return fallback ideas
        return [
            {
                "id": str(uuid.uuid4()),
                "title": "Sunset Picnic",
                "description": "Pack a basket with your favorite snacks and find a beautiful spot to watch the sunset together.",
                "category": "romantic",
                "budget_estimate": "$",
                "duration": "2-3 hours",
                "location_type": "outdoor",
                "is_trending": False,
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Cooking Class Date",
                "description": "Take a cooking class together and learn to make a new cuisine. It's fun, interactive, and you get to eat your creation!",
                "category": "foodie",
                "budget_estimate": "$$",
                "duration": "3-4 hours",
                "location_type": "indoor",
                "is_trending": True,
                "created_at": datetime.utcnow().isoformat()
            }
        ]

async def generate_trending_ideas(count: int = 10) -> List[Dict[str, Any]]:
    """Generate trending date ideas based on season and current trends"""
    try:
        current_month = datetime.now().strftime("%B")
        current_season = "summer" if datetime.now().month in [6, 7, 8] else "spring" if datetime.now().month in [3, 4, 5] else "fall" if datetime.now().month in [9, 10, 11] else "winter"
        
        prompt = f"""
Generate {count} trending date ideas for the USA market in {current_month} ({current_season} season).

These should be:
- Currently popular and trendy
- Season-appropriate
- Instagram-worthy
- Fun and engaging
- Suitable for various budgets

For each idea provide:
1. Catchy title
2. Engaging description (2-3 sentences)
3. Category
4. Budget estimate ($ / $$ / $$$)
5. Duration
6. Location type

Format as JSON array with fields: title, description, category, budget_estimate, duration, location_type

IMPORTANT: Return ONLY valid JSON array, no additional text.
"""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"trending-{datetime.now().strftime('%Y-%m-%d')}",
            system_message="You are a trend-aware date planning assistant. Always respond with valid JSON only."
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        import json
        response_text = response.strip()
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        
        ideas = json.loads(response_text)
        
        for idea in ideas:
            idea['id'] = str(uuid.uuid4())
            idea['is_trending'] = True
            idea['created_at'] = datetime.utcnow().isoformat()
            idea['image_url'] = None
        
        return ideas
    
    except Exception as e:
        logger.error(f"Error generating trending ideas: {str(e)}")
        return []

async def generate_gift_suggestions(occasion_type: str, person_name: str, budget: str = "medium") -> List[str]:
    """Generate gift suggestions for special occasions"""
    try:
        prompt = f"""
Suggest 5 thoughtful gift ideas for a {occasion_type} for {person_name}.

Budget: {budget}

Provide creative, personal, and meaningful gift suggestions suitable for the USA market.
Format as simple list of gift ideas.
"""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"gifts-{occasion_type}",
            system_message="You are a thoughtful gift suggestion assistant."
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse response into list
        suggestions = [line.strip('- ').strip() for line in response.split('\n') if line.strip() and not line.strip().startswith('#')]
        return suggestions[:5]
    
    except Exception as e:
        logger.error(f"Error generating gift suggestions: {str(e)}")
        return ["Personalized photo album", "Custom jewelry", "Experience gift card", "Handwritten letter collection", "Memory scrapbook"]

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/send-otp")
async def send_otp(request: OTPRequest):
    """Send OTP to phone number (simulated for MVP)"""
    try:
        phone_number = request.phone_number
        otp = generate_otp()
        
        # Store OTP in database with expiry
        otp_doc = {
            "phone_number": phone_number,
            "otp": otp,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=10)
        }
        
        await db.otps.delete_many({"phone_number": phone_number})
        await db.otps.insert_one(otp_doc)
        
        logger.info(f"OTP for {phone_number}: {otp}")
        
        return {"success": True, "message": "OTP sent successfully", "otp": otp}  # In production, don't return OTP
    
    except Exception as e:
        logger.error(f"Error sending OTP: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/auth/verify-otp")
async def verify_otp(request: OTPVerify):
    """Verify OTP and create/login user"""
    try:
        phone_number = request.phone_number
        otp = request.otp
        
        # Check OTP
        otp_doc = await db.otps.find_one({
            "phone_number": phone_number,
            "otp": otp,
            "expires_at": {"$gte": datetime.utcnow()}
        })
        
        if not otp_doc:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
        # Check if user exists
        user = await db.users.find_one({"phone_number": phone_number})
        
        if not user:
            # Create new user
            user_profile = UserProfile(phone_number=phone_number)
            user_dict = user_profile.dict()
            await db.users.insert_one(user_dict)
            user = user_dict
            is_new_user = True
        else:
            is_new_user = False
        
        # Generate token
        token = create_access_token({"user_id": user["id"], "phone_number": phone_number})
        
        # Delete used OTP
        await db.otps.delete_one({"_id": otp_doc["_id"]})
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": user["id"],
                "phone_number": user["phone_number"],
                "name": user.get("name"),
                "email": user.get("email")
            },
            "is_new_user": is_new_user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying OTP: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== USER ROUTES ====================

@api_router.get("/user/profile/{user_id}")
async def get_user_profile(user_id: str):
    """Get user profile"""
    try:
        user = await db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.pop("_id", None)
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/user/profile/{user_id}")
async def update_user_profile(user_id: str, updates: Dict[str, Any]):
    """Update user profile"""
    try:
        updates["updated_at"] = datetime.utcnow()
        
        result = await db.users.update_one(
            {"id": user_id},
            {"$set": updates}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = await db.users.find_one({"id": user_id})
        user.pop("_id", None)
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PERSONALITY ROUTES ====================

@api_router.post("/personality/submit")
async def submit_personality_questionnaire(questionnaire: PersonalityQuestionnaire):
    """Submit personality questionnaire"""
    try:
        user_id = questionnaire.user_id
        
        # Update user profile with personality data
        personality_data = questionnaire.dict()
        personality_data.pop("user_id")
        
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "personality_data": personality_data,
                "updated_at": datetime.utcnow()
            }}
        )
        
        return {"success": True, "message": "Personality data saved"}
    
    except Exception as e:
        logger.error(f"Error saving personality data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== DATE IDEAS ROUTES ====================

@api_router.post("/date-ideas/generate")
async def generate_personalized_date_ideas(request: AIGenerationRequest):
    """Generate personalized date ideas using AI"""
    try:
        user = await db.users.find_one({"id": request.user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        personality = user.get("personality_data", {})
        
        if not personality:
            # Return generic trending ideas if no personality data
            ideas = await generate_trending_ideas(request.count)
        else:
            ideas = await generate_date_ideas_with_ai(user, personality, request.count)
        
        return {"success": True, "date_ideas": ideas}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating date ideas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/date-ideas/trending")
async def get_trending_date_ideas(count: int = 10):
    """Get trending date ideas"""
    try:
        ideas = await generate_trending_ideas(count)
        return {"success": True, "date_ideas": ideas}
    
    except Exception as e:
        logger.error(f"Error getting trending ideas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== WISHLIST ROUTES ====================

@api_router.post("/wishlist/add")
async def add_to_wishlist(item: WishlistItem):
    """Add date idea to wishlist"""
    try:
        # Check if already in wishlist
        existing = await db.wishlist.find_one({
            "user_id": item.user_id,
            "date_idea_id": item.date_idea_id
        })
        
        if existing:
            return {"success": True, "message": "Already in wishlist", "item_id": existing["id"]}
        
        item_dict = item.dict()
        await db.wishlist.insert_one(item_dict)
        
        # Track behavior
        behavior = UserBehavior(
            user_id=item.user_id,
            date_idea_id=item.date_idea_id,
            action="saved"
        )
        await db.user_behavior.insert_one(behavior.dict())
        
        return {"success": True, "message": "Added to wishlist", "item_id": item.id}
    
    except Exception as e:
        logger.error(f"Error adding to wishlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/wishlist/{user_id}")
async def get_user_wishlist(user_id: str):
    """Get user's wishlist"""
    try:
        items = await db.wishlist.find({"user_id": user_id}).sort("added_at", -1).to_list(1000)
        
        for item in items:
            item.pop("_id", None)
        
        return {"success": True, "wishlist": items}
    
    except Exception as e:
        logger.error(f"Error getting wishlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/wishlist/{item_id}")
async def remove_from_wishlist(item_id: str, user_id: str):
    """Remove item from wishlist"""
    try:
        result = await db.wishlist.delete_one({"id": item_id, "user_id": user_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        
        return {"success": True, "message": "Removed from wishlist"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from wishlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CONNECTIONS ROUTES ====================

@api_router.post("/connections/create-invite")
async def create_connection_invite(user_id: str, connection_type: str = "partner"):
    """Create an invite code for connection"""
    try:
        invite_code = generate_invite_code()
        
        connection = Connection(
            user_id=user_id,
            connected_user_id="",
            connection_type=connection_type,
            status="pending",
            invite_code=invite_code
        )
        
        await db.connections.insert_one(connection.dict())
        
        return {"success": True, "invite_code": invite_code}
    
    except Exception as e:
        logger.error(f"Error creating invite: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/connections/accept-invite")
async def accept_connection_invite(invite_code: str, user_id: str):
    """Accept connection invite"""
    try:
        connection = await db.connections.find_one({"invite_code": invite_code, "status": "pending"})
        
        if not connection:
            raise HTTPException(status_code=404, detail="Invalid invite code")
        
        # Update connection
        await db.connections.update_one(
            {"id": connection["id"]},
            {"$set": {"connected_user_id": user_id, "status": "accepted"}}
        )
        
        # Create reverse connection
        reverse_connection = Connection(
            user_id=user_id,
            connected_user_id=connection["user_id"],
            connection_type=connection["connection_type"],
            status="accepted"
        )
        await db.connections.insert_one(reverse_connection.dict())
        
        return {"success": True, "message": "Connection accepted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invite: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/connections/{user_id}")
async def get_user_connections(user_id: str):
    """Get user's connections"""
    try:
        connections = await db.connections.find({
            "user_id": user_id,
            "status": "accepted"
        }).to_list(1000)
        
        # Get connected users' info
        result = []
        for conn in connections:
            connected_user = await db.users.find_one({"id": conn["connected_user_id"]})
            if connected_user:
                result.append({
                    "id": conn["id"],
                    "connection_type": conn["connection_type"],
                    "user": {
                        "id": connected_user["id"],
                        "name": connected_user.get("name", "Unknown"),
                        "phone_number": connected_user["phone_number"]
                    }
                })
        
        return {"success": True, "connections": result}
    
    except Exception as e:
        logger.error(f"Error getting connections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/connections/partner-wishlist/{user_id}")
async def get_partner_wishlist(user_id: str):
    """Get partner's wishlist (visible to user)"""
    try:
        # Get user's partner connections
        connections = await db.connections.find({
            "user_id": user_id,
            "connection_type": "partner",
            "status": "accepted"
        }).to_list(1000)
        
        all_wishlists = []
        for conn in connections:
            partner_id = conn["connected_user_id"]
            partner = await db.users.find_one({"id": partner_id})
            
            if partner:
                wishlist_items = await db.wishlist.find({"user_id": partner_id}).to_list(1000)
                
                for item in wishlist_items:
                    item.pop("_id", None)
                
                all_wishlists.append({
                    "partner_name": partner.get("name", "Your Partner"),
                    "partner_id": partner_id,
                    "wishlist": wishlist_items
                })
        
        return {"success": True, "partner_wishlists": all_wishlists}
    
    except Exception as e:
        logger.error(f"Error getting partner wishlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== OCCASIONS ROUTES ====================

@api_router.post("/occasions/add")
async def add_occasion(occasion: Occasion):
    """Add special occasion"""
    try:
        occasion_dict = occasion.dict()
        await db.occasions.insert_one(occasion_dict)
        
        return {"success": True, "message": "Occasion added", "occasion_id": occasion.id}
    
    except Exception as e:
        logger.error(f"Error adding occasion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/occasions/{user_id}")
async def get_user_occasions(user_id: str):
    """Get user's occasions"""
    try:
        occasions = await db.occasions.find({"user_id": user_id}).sort("date", 1).to_list(1000)
        
        for occasion in occasions:
            occasion.pop("_id", None)
        
        return {"success": True, "occasions": occasions}
    
    except Exception as e:
        logger.error(f"Error getting occasions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/occasions/upcoming/{user_id}")
async def get_upcoming_occasions(user_id: str, days: int = 30):
    """Get upcoming occasions in next N days"""
    try:
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days)
        
        occasions = await db.occasions.find({
            "user_id": user_id,
            "date": {"$gte": start_date, "$lte": end_date}
        }).sort("date", 1).to_list(1000)
        
        for occasion in occasions:
            occasion.pop("_id", None)
        
        return {"success": True, "upcoming_occasions": occasions}
    
    except Exception as e:
        logger.error(f"Error getting upcoming occasions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/occasions/{occasion_id}")
async def delete_occasion(occasion_id: str, user_id: str):
    """Delete occasion"""
    try:
        result = await db.occasions.delete_one({"id": occasion_id, "user_id": user_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Occasion not found")
        
        return {"success": True, "message": "Occasion deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting occasion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== GIFT SUGGESTIONS ====================

@api_router.post("/gifts/suggestions")
async def get_gift_suggestions(occasion_type: str, person_name: str, budget: str = "medium"):
    """Get AI-generated gift suggestions"""
    try:
        suggestions = await generate_gift_suggestions(occasion_type, person_name, budget)
        return {"success": True, "suggestions": suggestions}
    
    except Exception as e:
        logger.error(f"Error getting gift suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== USER BEHAVIOR ====================

@api_router.post("/behavior/track")
async def track_user_behavior(behavior: UserBehavior):
    """Track user behavior for learning"""
    try:
        await db.user_behavior.insert_one(behavior.dict())
        return {"success": True}
    
    except Exception as e:
        logger.error(f"Error tracking behavior: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()