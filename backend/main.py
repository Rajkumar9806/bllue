"""
bllue API - Production Backend with Neon PostgreSQL
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import asyncpg
import os
import uuid
import random
import logging
import httpx
import json
import re
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configuration - Use PROD_DATABASE_URL for production, DATABASE_URL for dev (Neon)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
if ENVIRONMENT == "production":
    DATABASE_URL = os.getenv("PROD_DATABASE_URL", os.getenv("DATABASE_URL"))
else:
    DATABASE_URL = os.getenv("DATABASE_URL")  # Neon for dev

JWT_SECRET = os.getenv("JWT_SECRET", "bllue_jwt_secret_key_2026_production_v1")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Social Media API Keys (for trending content)
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
TIKTOK_API_KEY = os.getenv("TIKTOK_API_KEY", "")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI app
app = FastAPI(
    title="bllue API",
    description="Date night idea provider API",
    version="1.0.0"
)

# CORS - Allow all origins for mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None

# ==================== MODELS ====================

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
    favorite_activities: Optional[List[str]] = []

class WishlistAdd(BaseModel):
    date_idea_id: str

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

class PersonalitySubmit(BaseModel):
    user_id: Optional[str] = None
    name: str
    personality_type: str
    interests: List[str]
    budget_range: str
    special_occasions: List[str]
    partner_name: Optional[str] = None
    partner_dob: Optional[str] = None
    anniversary_date: Optional[str] = None

class TokenData(BaseModel):
    user_id: str
    phone_number: str

# ==================== DATABASE ====================

async def get_db():
    """Get database connection from pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return db_pool

async def init_database():
    """Initialize database tables"""
    pool = await get_db()
    async with pool.acquire() as conn:
        # Users table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                phone_number VARCHAR(20) UNIQUE NOT NULL,
                name VARCHAR(255),
                email VARCHAR(255),
                personality_type VARCHAR(50),
                interests TEXT[],
                budget_range VARCHAR(20),
                indoor_outdoor_preference VARCHAR(20),
                favorite_activities TEXT[],
                partner_name VARCHAR(255),
                partner_dob VARCHAR(20),
                anniversary_date VARCHAR(20),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Add columns if they don't exist (for existing tables)
        for column in ['partner_name VARCHAR(255)', 'partner_dob VARCHAR(20)', 'anniversary_date VARCHAR(20)']:
            col_name = column.split()[0]
            try:
                await conn.execute(f'ALTER TABLE users ADD COLUMN IF NOT EXISTS {column}')
            except Exception:
                pass  # Column might already exist
        
        # OTP codes table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS otp_codes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                phone_number VARCHAR(20) NOT NULL,
                otp_code VARCHAR(6) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Date ideas table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS date_ideas (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                budget VARCHAR(20),
                duration VARCHAR(50),
                location_type VARCHAR(50),
                image_url TEXT,
                tags TEXT[],
                is_trending BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Wishlist table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS wishlist (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                date_idea_id UUID REFERENCES date_ideas(id) ON DELETE CASCADE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, date_idea_id)
            )
        ''')
        
        # Planned dates table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS planned_dates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                date_idea_id UUID REFERENCES date_ideas(id),
                title VARCHAR(255) NOT NULL,
                scheduled_date TIMESTAMP,
                notes TEXT,
                status VARCHAR(20) DEFAULT 'planned',
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        logger.info("Database tables initialized")

async def seed_date_ideas():
    """Seed initial date ideas"""
    pool = await get_db()
    async with pool.acquire() as conn:
        # Check if we already have ideas
        count = await conn.fetchval("SELECT COUNT(*) FROM date_ideas")
        if count > 0:
            logger.info(f"Database already has {count} date ideas")
            return
        
        ideas = [
            ("Sunset Picnic", "Pack a basket with your favorite snacks and find a scenic spot to watch the sunset together.", "romantic", "low", "2-3 hours", "outdoor", "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800", ["romantic", "outdoor", "budget-friendly"]),
            ("Cooking Class", "Learn to make a new cuisine together. Try Italian pasta, sushi, or Thai food!", "foodie", "medium", "3 hours", "indoor", "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=800", ["foodie", "hands-on", "learning"]),
            ("Stargazing Night", "Drive to a dark sky location, bring blankets and hot cocoa, and count shooting stars.", "romantic", "low", "3-4 hours", "outdoor", "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=800", ["romantic", "adventure", "nature"]),
            ("Wine & Paint Night", "Sip wine while painting together. Many studios offer couples sessions.", "creative", "medium", "2-3 hours", "indoor", "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=800", ["creative", "relaxing", "fun"]),
            ("Farmers Market Brunch", "Explore a local farmers market, pick fresh ingredients, and cook brunch together at home.", "foodie", "low", "3-4 hours", "outdoor", "https://images.unsplash.com/photo-1488459716781-31db52582fe9?w=800", ["foodie", "local", "morning"]),
            ("Escape Room Challenge", "Test your teamwork and problem-solving skills in an immersive escape room experience.", "adventure", "medium", "1-2 hours", "indoor", "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800", ["adventure", "teamwork", "exciting"]),
            ("Beach Day", "Pack sunscreen, build sandcastles, swim, and enjoy a beachside lunch together.", "relaxing", "low", "full day", "outdoor", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800", ["relaxing", "summer", "outdoor"]),
            ("Comedy Show", "Laugh together at a local comedy club. Laughter is the best medicine for any relationship!", "entertainment", "medium", "2-3 hours", "indoor", "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?w=800", ["fun", "entertainment", "nightlife"]),
            ("Hiking Adventure", "Find a scenic trail, pack snacks and water, and enjoy nature together.", "adventure", "low", "3-5 hours", "outdoor", "https://images.unsplash.com/photo-1551632811-561732d1e306?w=800", ["adventure", "fitness", "nature"]),
            ("Spa Day at Home", "Create a relaxing spa experience at home with face masks, massages, and aromatherapy.", "relaxing", "low", "2-3 hours", "indoor", "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800", ["relaxing", "romantic", "self-care"]),
            ("Game Night", "Break out the board games, card games, or video games for a fun competitive evening.", "fun", "low", "2-4 hours", "indoor", "https://images.unsplash.com/photo-1611371805429-8b5c1b2c34ba?w=800", ["fun", "competitive", "cozy"]),
            ("Fine Dining Experience", "Dress up and treat yourselves to a fancy dinner at an upscale restaurant.", "romantic", "high", "2-3 hours", "indoor", "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800", ["romantic", "luxurious", "special"]),
            ("Kayaking or Paddle Boarding", "Rent kayaks or paddle boards and explore a local lake or river together.", "adventure", "medium", "2-3 hours", "outdoor", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800", ["adventure", "active", "water"]),
            ("Movie Marathon", "Pick a movie series, make popcorn, build a blanket fort, and binge watch together.", "relaxing", "low", "full day", "indoor", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800", ["relaxing", "cozy", "entertainment"]),
            ("Art Museum Visit", "Explore a local art museum and discuss your favorite pieces over coffee after.", "cultural", "low", "2-3 hours", "indoor", "https://images.unsplash.com/photo-1518998053901-5348d3961a04?w=800", ["cultural", "intellectual", "arts"]),
            ("Rooftop Bar Hopping", "Dress up and visit a few rooftop bars with great views of the city.", "nightlife", "medium", "3-4 hours", "outdoor", "https://images.unsplash.com/photo-1470337458703-46ad1756a187?w=800", ["nightlife", "urban", "drinks"]),
            ("Pottery Class", "Get your hands dirty and create something together at a pottery studio.", "creative", "medium", "2 hours", "indoor", "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=800", ["creative", "hands-on", "unique"]),
            ("Food Truck Tour", "Find the best food trucks in your city and sample dishes from each one.", "foodie", "medium", "3-4 hours", "outdoor", "https://images.unsplash.com/photo-1565123409695-7b5ef63a2efb?w=800", ["foodie", "casual", "adventure"]),
            ("Botanical Garden Walk", "Stroll through a beautiful botanical garden and enjoy the flowers and nature.", "relaxing", "low", "2-3 hours", "outdoor", "https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=800", ["relaxing", "nature", "peaceful"]),
            ("Live Music Concert", "See a live band or musician perform at a local venue.", "entertainment", "medium", "3-4 hours", "indoor", "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800", ["entertainment", "music", "nightlife"]),
            ("Ice Skating", "Hit the ice rink together - it's romantic whether you're good at it or not!", "fun", "low", "2 hours", "indoor", "https://images.unsplash.com/photo-1551632811-561732d1e306?w=800", ["fun", "active", "winter"]),
            ("Breakfast in Bed", "Surprise your partner with a homemade breakfast in bed - pancakes, eggs, and fresh juice.", "romantic", "low", "1-2 hours", "indoor", "https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?w=800", ["romantic", "morning", "homemade"]),
            ("Bike Ride", "Rent bikes and explore your city or a scenic trail together.", "adventure", "low", "2-3 hours", "outdoor", "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800", ["adventure", "active", "outdoor"]),
            ("Wine Tasting", "Visit a local winery or wine bar and sample different wines together.", "romantic", "medium", "2-3 hours", "indoor", "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=800", ["romantic", "sophisticated", "drinks"]),
            ("Volunteer Together", "Find a local charity and volunteer together - it's rewarding and bonding.", "meaningful", "low", "3-4 hours", "outdoor", "https://images.unsplash.com/photo-1559027615-cd4628902d4a?w=800", ["meaningful", "giving-back", "bonding"]),
            ("Hot Air Balloon Ride", "Take to the skies for a breathtaking hot air balloon experience at sunrise.", "adventure", "high", "3-4 hours", "outdoor", "https://images.unsplash.com/photo-1507608616759-54f48f0af0ee?w=800", ["adventure", "romantic", "bucket-list"]),
            ("Trivia Night", "Find a local bar hosting trivia night and test your knowledge as a team.", "fun", "low", "2-3 hours", "indoor", "https://images.unsplash.com/photo-1543269865-cbf427effbad?w=800", ["fun", "social", "competitive"]),
            ("Couples Massage", "Relax and unwind together with a professional couples massage.", "relaxing", "high", "1-2 hours", "indoor", "https://images.unsplash.com/photo-1600334129128-685c5582fd35?w=800", ["relaxing", "spa", "romantic"]),
            ("Zoo or Aquarium Visit", "Spend the day exploring the zoo or aquarium and see amazing animals.", "fun", "medium", "3-4 hours", "outdoor", "https://images.unsplash.com/photo-1534567153574-2b12153a87f0?w=800", ["fun", "animals", "educational"]),
            ("Sunset Cruise", "Book a sunset cruise and enjoy the views from the water.", "romantic", "high", "2-3 hours", "outdoor", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800", ["romantic", "water", "views"]),
        ]
        
        for title, desc, cat, budget, duration, loc_type, img_url, tags in ideas:
            await conn.execute('''
                INSERT INTO date_ideas (title, description, category, budget, duration, location_type, image_url, tags, is_trending)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''', title, desc, cat, budget, duration, loc_type, img_url, tags, random.random() > 0.7)
        
        logger.info(f"Seeded {len(ideas)} date ideas")

# ==================== STARTUP ====================

@app.on_event("startup")
async def startup():
    logger.info("Starting bllue API...")
    await init_database()
    await seed_date_ideas()
    logger.info("bllue API started successfully!")

@app.on_event("shutdown")
async def shutdown():
    global db_pool
    if db_pool:
        await db_pool.close()

# ==================== HELPERS ====================

def create_access_token(user_id: str, phone_number: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "user_id": user_id,
        "phone_number": phone_number,
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return TokenData(user_id=payload["user_id"], phone_number=payload["phone_number"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "")
    return verify_token(token)

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

# ==================== GEMINI AI ====================

async def generate_ai_date_ideas(personality: Dict[str, Any], count: int = 5) -> List[Dict[str, Any]]:
    """Generate personalized date ideas using Gemini AI"""
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not configured, returning empty list")
        return []
    
    prompt = f"""You are a creative date night planner. Based on the user's personality profile, generate {count} unique and personalized date night ideas.

User Profile:
- Personality Type: {personality.get('personality_type') or 'romantic'}
- Interests: {', '.join(personality.get('interests') or ['adventure', 'food'])}
- Budget Preference: {personality.get('budget_range') or 'moderate'}
- Location Preference: {personality.get('indoor_outdoor_preference') or 'both'}
- Favorite Activities: {', '.join(personality.get('favorite_activities') or [])}

Generate {count} creative, unique date ideas that match their personality. Include trendy ideas from social media like Instagram, TikTok, and Facebook dating trends.

Return ONLY a valid JSON array with this exact structure (no markdown, no explanation):
[
  {{
    "title": "Date idea title",
    "description": "Detailed 2-3 sentence description",
    "category": "romantic|adventure|foodie|creative|relaxing|fun|cultural|active",
    "budget": "low|medium|high",
    "duration": "duration estimate",
    "location_type": "indoor|outdoor|both",
    "tags": ["tag1", "tag2", "tag3"],
    "source": "ai-generated",
    "trending_on": ["instagram", "tiktok"] or []
  }}
]"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.9,
                        "topP": 0.95,
                        "maxOutputTokens": 2048
                    }
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "[]")
            
            # Clean up the response - remove markdown code blocks if present
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            ideas = json.loads(text)
            
            # Add UUIDs and timestamps
            for idea in ideas:
                idea["id"] = str(uuid.uuid4())
                idea["image_url"] = get_image_for_category(idea.get("category", "romantic"))
                idea["is_trending"] = bool(idea.get("trending_on"))
                idea["created_at"] = datetime.utcnow().isoformat()
            
            return ideas
            
    except Exception as e:
        logger.error(f"Error generating AI date ideas: {e}")
        return []

def get_image_for_category(category: str) -> str:
    """Get Unsplash image URL for category"""
    images = {
        "romantic": "https://images.unsplash.com/photo-1529636798458-92182e662485?w=800",
        "adventure": "https://images.unsplash.com/photo-1551632811-561732d1e306?w=800",
        "foodie": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800",
        "creative": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=800",
        "relaxing": "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800",
        "fun": "https://images.unsplash.com/photo-1611371805429-8b5c1b2c34ba?w=800",
        "cultural": "https://images.unsplash.com/photo-1518998053901-5348d3961a04?w=800",
        "active": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800",
    }
    return images.get(category, "https://images.unsplash.com/photo-1529636798458-92182e662485?w=800")

async def fetch_trending_date_ideas() -> List[Dict[str, Any]]:
    """Fetch trending date ideas from social media (simulated with AI)"""
    if not GEMINI_API_KEY:
        return []
    
    prompt = """Generate 5 trending date night ideas that are currently popular on Instagram, TikTok, and Facebook in 2026. Focus on viral date ideas and relationship trends.

Return ONLY a valid JSON array with this structure (no markdown):
[
  {
    "title": "Trending date idea",
    "description": "Why it's trending and how to do it",
    "category": "romantic|adventure|foodie|creative|relaxing|fun",
    "budget": "low|medium|high",
    "duration": "duration",
    "location_type": "indoor|outdoor|both",
    "tags": ["trending", "viral", "tiktok"],
    "source": "social-media",
    "trending_on": ["instagram", "tiktok", "facebook"],
    "trend_score": 95
  }
]"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.95,
                        "topP": 0.95,
                        "maxOutputTokens": 2048
                    }
                }
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "[]")
            
            # Clean markdown
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            ideas = json.loads(text)
            
            for idea in ideas:
                idea["id"] = str(uuid.uuid4())
                idea["image_url"] = get_image_for_category(idea.get("category", "fun"))
                idea["is_trending"] = True
                idea["created_at"] = datetime.utcnow().isoformat()
            
            return ideas
            
    except Exception as e:
        logger.error(f"Error fetching trending ideas: {e}")
        return []

# ==================== ROUTES ====================

@app.get("/")
async def root():
    return {"message": "bllue API", "version": "1.0.0", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "database": "connected"}

# ==================== AUTH ====================

@app.post("/api/auth/send-otp")
async def send_otp(request: OTPRequest):
    """Send OTP to phone number"""
    pool = await get_db()
    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    async with pool.acquire() as conn:
        # Delete old OTPs for this number
        await conn.execute("DELETE FROM otp_codes WHERE phone_number = $1", request.phone_number)
        
        # Store new OTP
        await conn.execute('''
            INSERT INTO otp_codes (phone_number, otp_code, expires_at)
            VALUES ($1, $2, $3)
        ''', request.phone_number, otp, expires_at)
    
    # In production, send SMS via Twilio
    # For now, log the OTP (and return it for testing)
    logger.info(f"OTP for {request.phone_number}: {otp}")
    
    return {
        "success": True,
        "message": f"OTP sent to {request.phone_number}",
        "test_otp": otp  # Remove this in production!
    }

@app.post("/api/auth/verify-otp")
async def verify_otp(request: OTPVerify):
    """Verify OTP and return access token"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        # Check OTP
        otp_record = await conn.fetchrow('''
            SELECT * FROM otp_codes 
            WHERE phone_number = $1 AND otp_code = $2 AND expires_at > NOW() AND used = FALSE
        ''', request.phone_number, request.otp)
        
        # Allow test OTP 123456 for development
        if not otp_record and request.otp != "123456":
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
        # Mark OTP as used
        if otp_record:
            await conn.execute("UPDATE otp_codes SET used = TRUE WHERE id = $1", otp_record['id'])
        
        # Check if user exists
        user = await conn.fetchrow("SELECT * FROM users WHERE phone_number = $1", request.phone_number)
        is_new_user = user is None
        
        if is_new_user:
            # Create new user
            user_id = str(uuid.uuid4())
            await conn.execute('''
                INSERT INTO users (id, phone_number) VALUES ($1, $2)
            ''', uuid.UUID(user_id), request.phone_number)
        else:
            user_id = str(user['id'])
        
        # Get user data for response
        user_data = await conn.fetchrow("SELECT * FROM users WHERE id = $1", uuid.UUID(user_id))
        
        # Generate token
        token = create_access_token(user_id, request.phone_number)
        
        return {
            "success": True,
            "token": token,
            "user_id": user_id,
            "user": {
                "id": user_id,
                "phone_number": request.phone_number,
                "name": user_data['name'] if user_data else None,
                "email": user_data['email'] if user_data else None
            },
            "is_new_user": is_new_user
        }

# ==================== QUESTIONNAIRE ====================

@app.post("/api/questionnaire")
async def save_questionnaire(data: QuestionnaireData, user: TokenData = Depends(get_current_user)):
    """Save user questionnaire answers"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE users SET 
                personality_type = $1,
                interests = $2,
                budget_range = $3,
                indoor_outdoor_preference = $4,
                favorite_activities = $5,
                updated_at = NOW()
            WHERE id = $6
        ''', data.personality_type, data.interests, data.budget_range, 
           data.indoor_outdoor_preference, data.favorite_activities or [], 
           uuid.UUID(user.user_id))
    
    return {"success": True, "message": "Questionnaire saved"}

@app.post("/api/personality/submit")
async def submit_personality(data: PersonalitySubmit, authorization: str = Header(None)):
    """Save user personality and preferences from onboarding"""
    pool = await get_db()
    
    # Get user_id from auth header if not provided in body
    user_id = data.user_id
    if not user_id and authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.replace("Bearer ", "")
            token_data = verify_token(token)
            user_id = token_data.user_id
        except:
            pass
    
    async with pool.acquire() as conn:
        # Check if user_id was provided
        if user_id:
            try:
                user_uuid = uuid.UUID(user_id)
                # Update existing user
                await conn.execute('''
                    UPDATE users SET 
                        name = $1,
                        personality_type = $2,
                        interests = $3,
                        budget_range = $4,
                        favorite_activities = $5,
                        partner_name = $6,
                        partner_dob = $7,
                        anniversary_date = $8,
                        updated_at = NOW()
                    WHERE id = $9
                ''', data.name, data.personality_type, data.interests, 
                   data.budget_range, data.special_occasions,
                   data.partner_name, data.partner_dob, data.anniversary_date,
                   user_uuid)
                
                return {"success": True, "message": "Preferences saved successfully"}
            except Exception as e:
                logger.error(f"Error updating user: {e}")
                raise HTTPException(status_code=400, detail=str(e))
        else:
            # No user_id, just return success (guest mode)
            return {"success": True, "message": "Preferences saved"}

# ==================== DATE IDEAS ====================

@app.get("/api/date-ideas")
async def get_date_ideas(
    category: Optional[str] = None,
    budget: Optional[str] = None,
    location_type: Optional[str] = None,
    limit: int = 20
):
    """Get date ideas with optional filters"""
    pool = await get_db()
    
    query = "SELECT * FROM date_ideas WHERE 1=1"
    params = []
    param_count = 0
    
    if category:
        param_count += 1
        query += f" AND category = ${param_count}"
        params.append(category)
    
    if budget:
        param_count += 1
        query += f" AND budget = ${param_count}"
        params.append(budget)
    
    if location_type:
        param_count += 1
        query += f" AND location_type = ${param_count}"
        params.append(location_type)
    
    param_count += 1
    query += f" ORDER BY RANDOM() LIMIT ${param_count}"
    params.append(limit)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        ideas = [dict(row) for row in rows]
        # Convert UUID to string
        for idea in ideas:
            idea['id'] = str(idea['id'])
    
    return {"ideas": ideas, "total": len(ideas)}

@app.get("/api/date-ideas/discover")
async def discover_date_ideas(authorization: str = Header(None)):
    """Get AI-powered personalized date ideas for discover page"""
    pool = await get_db()
    
    # Get user personality if authenticated
    personality = {}
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.replace("Bearer ", "")
            user_data = verify_token(token)
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT personality_type, interests, budget_range, indoor_outdoor_preference, favorite_activities FROM users WHERE id = $1",
                    uuid.UUID(user_data.user_id)
                )
                if row:
                    personality = dict(row)
        except:
            pass
    
    # Get AI-generated personalized ideas if we have personality data and API key
    ai_ideas = []
    if personality and GEMINI_API_KEY:
        ai_ideas = await generate_ai_date_ideas(personality, count=5)
    
    # Get database ideas
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT * FROM date_ideas 
            ORDER BY RANDOM() 
            LIMIT 10
        ''')
        db_ideas = [dict(row) for row in rows]
        for idea in db_ideas:
            idea['id'] = str(idea['id'])
            idea['source'] = 'curated'
    
    # Combine AI ideas with database ideas
    all_ideas = ai_ideas + db_ideas
    random.shuffle(all_ideas)
    
    return {"ideas": all_ideas[:15], "ai_powered": len(ai_ideas) > 0}

@app.get("/api/date-ideas/ai-personalized")
async def get_ai_personalized_ideas(user: TokenData = Depends(get_current_user)):
    """Get AI-generated personalized date ideas based on user personality"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT personality_type, interests, budget_range, indoor_outdoor_preference, favorite_activities FROM users WHERE id = $1",
            uuid.UUID(user.user_id)
        )
        
        if not row or not row['personality_type']:
            # Return fallback ideas if no personality data
            rows = await conn.fetch("SELECT * FROM date_ideas ORDER BY RANDOM() LIMIT 10")
            ideas = [dict(r) for r in rows]
            for idea in ideas:
                idea['id'] = str(idea['id'])
                idea['source'] = 'curated'
            return {"ideas": ideas, "personalized": False, "ai_powered": False, "message": "Complete your profile for personalized AI recommendations"}
        
        personality = dict(row)
    
    # Generate AI ideas
    ideas = await generate_ai_date_ideas(personality, count=10)
    
    if not ideas:
        # Fallback to database ideas if AI fails
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM date_ideas ORDER BY RANDOM() LIMIT 10")
            ideas = [dict(row) for row in rows]
            for idea in ideas:
                idea['id'] = str(idea['id'])
    
    return {"ideas": ideas, "personalized": True, "ai_powered": len(ideas) > 0}

@app.get("/api/date-ideas/social-trending")
async def get_social_trending_ideas():
    """Get trending date ideas from social media (Instagram, TikTok, Facebook)"""
    # Get AI-generated trending ideas
    trending = await fetch_trending_date_ideas()
    
    if not trending:
        # Fallback to database trending
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM date_ideas 
                WHERE is_trending = TRUE 
                ORDER BY RANDOM() 
                LIMIT 5
            ''')
            trending = [dict(row) for row in rows]
            for idea in trending:
                idea['id'] = str(idea['id'])
                idea['source'] = 'curated'
    
    return {
        "ideas": trending,
        "sources": ["instagram", "tiktok", "facebook"],
        "last_updated": datetime.utcnow().isoformat()
    }

@app.get("/api/date-ideas/trending")
async def get_trending_ideas():
    """Get trending date ideas"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT * FROM date_ideas 
            WHERE is_trending = TRUE 
            ORDER BY RANDOM() 
            LIMIT 10
        ''')
        ideas = [dict(row) for row in rows]
        for idea in ideas:
            idea['id'] = str(idea['id'])
    
    return {"ideas": ideas}

@app.get("/api/date-ideas/{idea_id}")
async def get_date_idea(idea_id: str):
    """Get specific date idea"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM date_ideas WHERE id = $1", uuid.UUID(idea_id))
        if not row:
            raise HTTPException(status_code=404, detail="Date idea not found")
        idea = dict(row)
        idea['id'] = str(idea['id'])
    
    return idea

# ==================== WISHLIST ====================

@app.get("/api/wishlist")
async def get_wishlist(user: TokenData = Depends(get_current_user)):
    """Get user's wishlist"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT di.*, w.notes, w.created_at as added_at
            FROM wishlist w
            JOIN date_ideas di ON w.date_idea_id = di.id
            WHERE w.user_id = $1
            ORDER BY w.created_at DESC
        ''', uuid.UUID(user.user_id))
        
        ideas = [dict(row) for row in rows]
        for idea in ideas:
            idea['id'] = str(idea['id'])
    
    return {"ideas": ideas, "total": len(ideas)}

@app.post("/api/wishlist/add")
async def add_to_wishlist_legacy(request: WishlistAdd, user: TokenData = Depends(get_current_user)):
    """Add idea to wishlist (legacy endpoint for frontend compatibility)"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO wishlist (user_id, date_idea_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, date_idea_id) DO NOTHING
            ''', uuid.UUID(user.user_id), uuid.UUID(request.date_idea_id))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    return {"success": True, "message": "Added to wishlist"}

@app.post("/api/wishlist/{idea_id}")
async def add_to_wishlist(idea_id: str, user: TokenData = Depends(get_current_user)):
    """Add idea to wishlist"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO wishlist (user_id, date_idea_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, date_idea_id) DO NOTHING
            ''', uuid.UUID(user.user_id), uuid.UUID(idea_id))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    return {"success": True, "message": "Added to wishlist"}

@app.delete("/api/wishlist/{idea_id}")
async def remove_from_wishlist(idea_id: str, user: TokenData = Depends(get_current_user)):
    """Remove idea from wishlist"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        await conn.execute('''
            DELETE FROM wishlist WHERE user_id = $1 AND date_idea_id = $2
        ''', uuid.UUID(user.user_id), uuid.UUID(idea_id))
    
    return {"success": True, "message": "Removed from wishlist"}

# ==================== CALENDAR ====================

@app.get("/api/calendar")
async def get_calendar(user: TokenData = Depends(get_current_user)):
    """Get user's planned dates"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT pd.*, di.title as idea_title, di.description, di.category, di.image_url
            FROM planned_dates pd
            LEFT JOIN date_ideas di ON pd.date_idea_id = di.id
            WHERE pd.user_id = $1
            ORDER BY pd.scheduled_date ASC
        ''', uuid.UUID(user.user_id))
        
        events = [dict(row) for row in rows]
        for event in events:
            event['id'] = str(event['id'])
            if event.get('date_idea_id'):
                event['date_idea_id'] = str(event['date_idea_id'])
    
    return {"events": events}

@app.post("/api/calendar")
async def plan_date(
    date_idea_id: Optional[str] = None,
    title: str = "Date Night",
    scheduled_date: Optional[datetime] = None,
    notes: Optional[str] = None,
    user: TokenData = Depends(get_current_user)
):
    """Plan a new date"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        event_id = uuid.uuid4()
        await conn.execute('''
            INSERT INTO planned_dates (id, user_id, date_idea_id, title, scheduled_date, notes)
            VALUES ($1, $2, $3, $4, $5, $6)
        ''', event_id, uuid.UUID(user.user_id), 
           uuid.UUID(date_idea_id) if date_idea_id else None,
           title, scheduled_date, notes)
    
    return {"success": True, "event_id": str(event_id)}

# ==================== PROFILE ====================

@app.get("/api/profile")
async def get_profile(user: TokenData = Depends(get_current_user)):
    """Get user profile"""
    pool = await get_db()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", uuid.UUID(user.user_id))
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get stats
        wishlist_count = await conn.fetchval(
            "SELECT COUNT(*) FROM wishlist WHERE user_id = $1", 
            uuid.UUID(user.user_id)
        )
        completed_dates = await conn.fetchval(
            "SELECT COUNT(*) FROM planned_dates WHERE user_id = $1 AND status = 'completed'",
            uuid.UUID(user.user_id)
        )
        
        profile = dict(row)
        profile['id'] = str(profile['id'])
        profile['wishlist_count'] = wishlist_count
        profile['completed_dates'] = completed_dates
    
    return profile

@app.patch("/api/profile")
async def update_profile(data: ProfileUpdate, user: TokenData = Depends(get_current_user)):
    """Update user profile"""
    pool = await get_db()
    
    updates = []
    params = []
    param_count = 0
    
    if data.name is not None:
        param_count += 1
        updates.append(f"name = ${param_count}")
        params.append(data.name)
    
    if data.email is not None:
        param_count += 1
        updates.append(f"email = ${param_count}")
        params.append(data.email)
    
    if updates:
        param_count += 1
        query = f"UPDATE users SET {', '.join(updates)}, updated_at = NOW() WHERE id = ${param_count}"
        params.append(uuid.UUID(user.user_id))
        
        async with pool.acquire() as conn:
            await conn.execute(query, *params)
    
    return {"success": True, "message": "Profile updated"}

# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
