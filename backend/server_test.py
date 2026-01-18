"""
Simple test backend for bllue app - No database required
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import random
from datetime import datetime, timedelta
import uuid

app = FastAPI(title="bllue API - Test Mode")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for testing
users_db = {}
otp_codes = {}
wishlists = {}

# Sample date ideas
DATE_IDEAS = [
    {
        "id": "1",
        "title": "Sunset Picnic",
        "description": "Pack a basket with your favorite snacks and find a scenic spot to watch the sunset together.",
        "category": "outdoor",
        "budget": "low",
        "duration": "2-3 hours",
        "image_url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800",
        "tags": ["romantic", "outdoor", "budget-friendly"]
    },
    {
        "id": "2", 
        "title": "Cooking Class",
        "description": "Learn to make a new cuisine together. Try Italian pasta, sushi, or Thai food!",
        "category": "indoor",
        "budget": "medium",
        "duration": "3 hours",
        "image_url": "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=800",
        "tags": ["foodie", "hands-on", "learning"]
    },
    {
        "id": "3",
        "title": "Stargazing Night",
        "description": "Drive to a dark sky location, bring blankets and hot cocoa, and count shooting stars.",
        "category": "outdoor",
        "budget": "low",
        "duration": "3-4 hours",
        "image_url": "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=800",
        "tags": ["romantic", "adventure", "nature"]
    },
    {
        "id": "4",
        "title": "Wine & Paint Night",
        "description": "Sip wine while painting together. Many studios offer couples sessions.",
        "category": "indoor",
        "budget": "medium",
        "duration": "2-3 hours",
        "image_url": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=800",
        "tags": ["creative", "relaxing", "fun"]
    },
    {
        "id": "5",
        "title": "Farmers Market Brunch",
        "description": "Explore a local farmers market, pick fresh ingredients, and cook brunch together at home.",
        "category": "outdoor",
        "budget": "low",
        "duration": "3-4 hours",
        "image_url": "https://images.unsplash.com/photo-1488459716781-31db52582fe9?w=800",
        "tags": ["foodie", "local", "morning"]
    },
    {
        "id": "6",
        "title": "Escape Room Challenge",
        "description": "Test your teamwork and problem-solving skills in an immersive escape room experience.",
        "category": "indoor",
        "budget": "medium",
        "duration": "1-2 hours",
        "image_url": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800",
        "tags": ["adventure", "teamwork", "exciting"]
    },
    {
        "id": "7",
        "title": "Beach Day",
        "description": "Pack sunscreen, build sandcastles, swim, and enjoy a beachside lunch together.",
        "category": "outdoor",
        "budget": "low",
        "duration": "full day",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800",
        "tags": ["relaxing", "summer", "outdoor"]
    },
    {
        "id": "8",
        "title": "Comedy Show",
        "description": "Laugh together at a local comedy club. Laughter is the best medicine for any relationship!",
        "category": "indoor",
        "budget": "medium",
        "duration": "2-3 hours",
        "image_url": "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?w=800",
        "tags": ["fun", "entertainment", "nightlife"]
    },
    {
        "id": "9",
        "title": "Hiking Adventure",
        "description": "Find a scenic trail, pack snacks and water, and enjoy nature together.",
        "category": "outdoor",
        "budget": "low",
        "duration": "3-5 hours",
        "image_url": "https://images.unsplash.com/photo-1551632811-561732d1e306?w=800",
        "tags": ["adventure", "fitness", "nature"]
    },
    {
        "id": "10",
        "title": "Spa Day at Home",
        "description": "Create a relaxing spa experience at home with face masks, massages, and aromatherapy.",
        "category": "indoor",
        "budget": "low",
        "duration": "2-3 hours",
        "image_url": "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800",
        "tags": ["relaxing", "romantic", "self-care"]
    },
    {
        "id": "11",
        "title": "Game Night",
        "description": "Break out the board games, card games, or video games for a fun competitive evening.",
        "category": "indoor",
        "budget": "low",
        "duration": "2-4 hours",
        "image_url": "https://images.unsplash.com/photo-1611371805429-8b5c1b2c34ba?w=800",
        "tags": ["fun", "competitive", "cozy"]
    },
    {
        "id": "12",
        "title": "Fine Dining Experience",
        "description": "Dress up and treat yourselves to a fancy dinner at an upscale restaurant.",
        "category": "indoor",
        "budget": "high",
        "duration": "2-3 hours",
        "image_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800",
        "tags": ["romantic", "luxurious", "special"]
    }
]

# Models
class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    otp: str

class QuestionnaireData(BaseModel):
    personality_type: str
    interests: List[str]
    budget_range: str
    indoor_outdoor_preference: str

# Routes
@app.get("/")
async def root():
    return {"message": "bllue API - Test Mode", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "mode": "test"}

@app.post("/api/auth/send-otp")
async def send_otp(request: OTPRequest):
    """Send OTP (in test mode, always returns 123456)"""
    otp = "123456"  # Fixed OTP for testing
    otp_codes[request.phone_number] = {
        "otp": otp,
        "expires": datetime.now() + timedelta(minutes=5)
    }
    return {"success": True, "message": f"OTP sent to {request.phone_number}", "test_otp": otp}

@app.post("/api/auth/verify-otp")
async def verify_otp(request: OTPVerify):
    """Verify OTP and return token"""
    stored = otp_codes.get(request.phone_number)
    
    # For testing, accept 123456
    if request.otp == "123456" or (stored and stored["otp"] == request.otp):
        user_id = str(uuid.uuid4())
        is_new_user = request.phone_number not in users_db
        
        if is_new_user:
            users_db[request.phone_number] = {
                "id": user_id,
                "phone_number": request.phone_number,
                "created_at": datetime.now().isoformat()
            }
        else:
            user_id = users_db[request.phone_number]["id"]
        
        return {
            "success": True,
            "token": f"test_token_{user_id}",
            "user_id": user_id,
            "is_new_user": is_new_user
        }
    
    raise HTTPException(status_code=400, detail="Invalid OTP")

@app.post("/api/questionnaire")
async def save_questionnaire(data: QuestionnaireData):
    """Save user questionnaire"""
    return {"success": True, "message": "Questionnaire saved"}

@app.get("/api/date-ideas")
async def get_date_ideas(category: Optional[str] = None, budget: Optional[str] = None):
    """Get date ideas with optional filters"""
    ideas = DATE_IDEAS.copy()
    
    if category:
        ideas = [i for i in ideas if i["category"] == category]
    if budget:
        ideas = [i for i in ideas if i["budget"] == budget]
    
    return {"ideas": ideas, "total": len(ideas)}

@app.get("/api/date-ideas/discover")
async def discover_date_ideas():
    """Get shuffled date ideas for discover page"""
    ideas = DATE_IDEAS.copy()
    random.shuffle(ideas)
    return {"ideas": ideas[:6]}

@app.get("/api/date-ideas/{idea_id}")
async def get_date_idea(idea_id: str):
    """Get specific date idea"""
    for idea in DATE_IDEAS:
        if idea["id"] == idea_id:
            return idea
    raise HTTPException(status_code=404, detail="Date idea not found")

@app.post("/api/wishlist/{idea_id}")
async def add_to_wishlist(idea_id: str, user_id: str = "test_user"):
    """Add idea to wishlist"""
    if user_id not in wishlists:
        wishlists[user_id] = []
    
    if idea_id not in wishlists[user_id]:
        wishlists[user_id].append(idea_id)
    
    return {"success": True, "message": "Added to wishlist"}

@app.delete("/api/wishlist/{idea_id}")
async def remove_from_wishlist(idea_id: str, user_id: str = "test_user"):
    """Remove idea from wishlist"""
    if user_id in wishlists and idea_id in wishlists[user_id]:
        wishlists[user_id].remove(idea_id)
    
    return {"success": True, "message": "Removed from wishlist"}

@app.get("/api/wishlist")
async def get_wishlist(user_id: str = "test_user"):
    """Get user's wishlist"""
    user_wishlist = wishlists.get(user_id, [])
    ideas = [i for i in DATE_IDEAS if i["id"] in user_wishlist]
    return {"ideas": ideas, "total": len(ideas)}

@app.get("/api/calendar")
async def get_calendar():
    """Get planned dates"""
    return {"events": [], "upcoming": []}

@app.get("/api/profile")
async def get_profile(user_id: str = "test_user"):
    """Get user profile"""
    return {
        "id": user_id,
        "name": "Test User",
        "phone_number": "+1234567890",
        "completed_dates": 5,
        "wishlist_count": len(wishlists.get(user_id, [])),
        "member_since": "January 2026"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
