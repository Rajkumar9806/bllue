"""
Arrow API - Production Backend with Neon PostgreSQL
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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

# Import admin router
from admin import router as admin_router, set_db_pool as admin_set_db_pool

# Import review queue router
from review_queue import router as review_queue_router, set_db_pool as review_queue_set_db_pool, set_ai_provider as review_queue_set_ai_provider, init_review_queue_table

# Import partner pairing router
from partner import router as partner_router, set_db_pool as partner_set_db_pool, init_partner_tables

# Import journal router
from journal import router as journal_router, set_db_pool as journal_set_db_pool, init_journal_tables

# Import AI provider system
from ai_providers import get_ai_provider, get_available_providers, clean_response_text

# Import smart preference algorithm v2
from smart_algorithm import (
    compute_user_preferences,
    build_smart_prompt,
    compute_partner_compatibility,
    get_current_weather,
    compute_temporal_preferences,
    compute_feedback_enhanced_preferences,
    get_seasonal_context,
    get_anniversary_context,
    compute_budget_context,
    get_freshness_context,
    MOOD_OPTIONS,
    ENERGY_LEVELS
)

# Import idea seeder
from idea_seeder import router as seeder_router, set_db_pool as seeder_set_db_pool, set_ai_generator, init_seeder_tables

# Import retail partner system
from retail_partners import router as retail_router, set_db_pool as retail_set_db_pool, init_retail_tables

# Import live events & multi-source scraper
from live_events import router as events_router, set_db_pool as events_set_db_pool, init_events_tables

# Import daily pipeline scheduler
from daily_pipeline import router as pipeline_router, set_db_pool as pipeline_set_db_pool, start_pipeline_scheduler, stop_pipeline_scheduler

# Configuration - Use PROD_DATABASE_URL for production, DATABASE_URL for dev (Neon)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
if ENVIRONMENT == "production":
    DATABASE_URL = os.getenv("PROD_DATABASE_URL", os.getenv("DATABASE_URL"))
else:
    DATABASE_URL = os.getenv("DATABASE_URL")  # Neon for dev

JWT_SECRET = os.getenv("JWT_SECRET", "arrow_jwt_secret_key_2026_production_v1")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# AI Provider Configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()  # Default to Gemini for backward compatibility
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Kept for backward compatibility
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

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
    title="Arrow API",
    description="AI-Powered Date Planning API",
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

# Mount routers
app.include_router(admin_router)
app.include_router(review_queue_router)
app.include_router(partner_router)
app.include_router(journal_router)
app.include_router(seeder_router)
app.include_router(retail_router)
app.include_router(events_router)
app.include_router(pipeline_router)

# Admin Dashboard UI
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard UI"""
    template_path = ROOT_DIR / "templates" / "admin_dashboard.html"
    if template_path.exists():
        return HTMLResponse(content=template_path.read_text(), status_code=200)
    return HTMLResponse(content="<h1>Admin Dashboard not found</h1>", status_code=404)

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None

# Current AI provider (can be changed at runtime)
current_ai_provider: str = AI_PROVIDER

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

class OccasionCreate(BaseModel):
    person_name: str
    occasion_type: str  # birthday, anniversary, valentine, holiday, date_night, other
    date: str  # Accept string dates (ISO format or common formats)
    reminder_days_before: int = 7
    notes: Optional[str] = None

class OccasionUpdate(BaseModel):
    person_name: Optional[str] = None
    occasion_type: Optional[str] = None
    date: Optional[str] = None
    reminder_days_before: Optional[int] = None
    notes: Optional[str] = None

class Occasion(BaseModel):
    id: str
    user_id: str
    person_name: str
    occasion_type: str
    date: str  # ISO format string
    reminder_days_before: int
    notes: Optional[str]
    reminder_sent: bool
    created_at: str
    updated_at: str

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
                source VARCHAR(50) DEFAULT 'curated',
                updated_at TIMESTAMP DEFAULT NOW(),
                updated_by VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Add new columns to date_ideas if they don't exist
        for column_def in [
            ('source', "VARCHAR(50) DEFAULT 'curated'"),
            ('updated_at', "TIMESTAMP DEFAULT NOW()"),
            ('updated_by', "VARCHAR(255)")
        ]:
            col_name = column_def[0]
            try:
                await conn.execute(f'ALTER TABLE date_ideas ADD COLUMN IF NOT EXISTS {col_name} {column_def[1]}')
            except Exception:
                pass  # Column might already exist
        
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

        # Occasions table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS occasions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                person_name VARCHAR(255) NOT NULL,
                occasion_type VARCHAR(50) NOT NULL,
                date TIMESTAMP NOT NULL,
                reminder_days_before INTEGER DEFAULT 7,
                notes TEXT,
                reminder_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Featured ideas table (daily/weekly picks)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS featured_ideas (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                date_idea_id UUID REFERENCES date_ideas(id) ON DELETE CASCADE,
                feature_type VARCHAR(10) NOT NULL,
                feature_date DATE NOT NULL,
                featured_by VARCHAR(255) DEFAULT 'system',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(feature_type, feature_date)
            )
        ''')

        # Idea interactions table (accept/reject tracking)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS idea_interactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                date_idea_id UUID,
                idea_title VARCHAR(255),
                action VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, date_idea_id)
            )
        ''')

        logger.info("Database tables initialized")

async def init_review_queue():
    """Initialize review queue tables"""
    await init_review_queue_table()

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
                INSERT INTO date_ideas (title, description, category, budget, duration, location_type, image_url, tags, is_trending, source, updated_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ''', title, desc, cat, budget, duration, loc_type, img_url, tags, random.random() > 0.7, 'curated', 'seed')
        
        logger.info(f"Seeded {len(ideas)} date ideas")

# ==================== STARTUP ====================

@app.on_event("startup")
async def startup():
    logger.info("Starting Arrow API...")
    global db_pool
    await init_database()
    
    # Get database pool FIRST
    db_pool = await get_db()
    
    # Set db_pool in all routers BEFORE initializing tables
    admin_set_db_pool(db_pool)
    review_queue_set_db_pool(db_pool)
    partner_set_db_pool(db_pool)
    journal_set_db_pool(db_pool)
    seeder_set_db_pool(db_pool)
    retail_set_db_pool(db_pool)
    events_set_db_pool(db_pool)
    pipeline_set_db_pool(db_pool)
    
    # Set AI provider for review queue
    review_queue_set_ai_provider(current_ai_provider)
    set_ai_generator(generate_ai_date_ideas, current_ai_provider)
    
    # NOW initialize tables (after db_pool is set)
    await init_review_queue()
    await init_partner_tables()
    await init_journal_tables()
    await init_seeder_tables()
    await init_retail_tables()
    await init_events_tables()
    
    # Start background scheduler
    start_pipeline_scheduler()
    await seed_date_ideas()
    logger.info("Arrow API started successfully!")

@app.on_event("shutdown")
async def shutdown():
    global db_pool
    stop_pipeline_scheduler()  # Stop daily pipeline background scheduler
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

def parse_date_string(date_str: str) -> datetime:
    """Parse various date formats - crucial for the date button fix

    Supports:
    - ISO format with milliseconds: 2026-03-15T14:30:00.000Z
    - ISO format: 2026-03-15T14:30:00Z
    - ISO format no Z: 2026-03-15T14:30:00
    - Simple date: 2026-03-15
    - US format with slashes: 03/15/2026
    - US format with dashes: 03-15-2026
    - EU format: 15/03/2026
    """
    if not date_str:
        raise HTTPException(status_code=400, detail="Date is required")

    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with millis
        "%Y-%m-%dT%H:%M:%SZ",      # ISO
        "%Y-%m-%dT%H:%M:%S",       # ISO no Z
        "%Y-%m-%d",                # Simple date
        "%m/%d/%Y",                # US format
        "%m-%d-%Y",                # US with dashes
        "%d/%m/%Y",                # EU format
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # If no format matched, raise error
    raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Expected ISO, US (MM/DD/YYYY), or EU (DD/MM/YYYY) format")

# ==================== AI PROVIDERS ====================

async def generate_ai_date_ideas(personality: Dict[str, Any], count: int = 5, require_review: bool = False) -> List[Dict[str, Any]]:
    """Generate personalized date ideas using configured AI provider

    Args:
        personality: User personality profile dict
        count: Number of ideas to generate
        require_review: If True, insert into review queue instead of returning directly

    Returns:
        List of generated ideas (empty if require_review is True)
    """

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
        provider = get_ai_provider(current_ai_provider)
        text = await provider.generate(prompt, temperature=0.9, max_tokens=2048)

        # Clean up the response - remove markdown code blocks if present
        text = clean_response_text(text)

        ideas = json.loads(text)

        # If require_review is True, insert into review queue and return empty list
        if require_review:
            async with db_pool.acquire() as conn:
                for idea in ideas:
                    idea_id = uuid.uuid4()
                    await conn.execute('''
                        INSERT INTO idea_reviews
                        (id, idea_title, idea_description, idea_category, idea_budget,
                         idea_duration, idea_location_type, idea_tags, ai_provider, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')
                    ''', idea_id, idea.get('title', ''), idea.get('description', ''),
                       idea.get('category', 'fun'), idea.get('budget', 'medium'),
                       idea.get('duration', ''), idea.get('location_type', 'both'),
                       idea.get('tags', []), current_ai_provider)
            logger.info(f"Inserted {len(ideas)} ideas into review queue")
            return []

        # Add UUIDs and timestamps for direct return
        for idea in ideas:
            idea["id"] = str(uuid.uuid4())
            idea["image_url"] = get_image_for_category(idea.get("category", "romantic"))
            idea["is_trending"] = bool(idea.get("trending_on"))
            idea["created_at"] = datetime.utcnow().isoformat()

        return ideas

    except ValueError as e:
        logger.warning(f"AI provider not configured: {e}")
        return []
    except Exception as e:
        logger.error(f"Error generating AI date ideas: {e}")
        return []

def get_image_for_category(category: str) -> str:
    """Get fallback image URL for category (when database doesn't have image)"""
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
    """Fetch trending date ideas using configured AI provider"""

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
        provider = get_ai_provider(current_ai_provider)
        text = await provider.generate(prompt, temperature=0.95, max_tokens=2048)

        # Clean markdown
        text = clean_response_text(text)

        ideas = json.loads(text)

        for idea in ideas:
            idea["id"] = str(uuid.uuid4())
            idea["image_url"] = get_image_for_category(idea.get("category", "fun"))
            idea["is_trending"] = True
            idea["created_at"] = datetime.utcnow().isoformat()

        return ideas

    except ValueError as e:
        logger.warning(f"AI provider not configured: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching trending ideas: {e}")
        return []

# ==================== ROUTES ====================

@app.get("/")
async def root():
    return {"message": "Arrow API", "version": "1.0.0", "status": "running"}

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

# ==================== FEATURED IDEAS (Daily/Weekly) ====================

@app.get("/api/date-ideas/daily")
async def get_daily_idea():
    """Get the featured date idea of the day.
    Uses a deterministic pick based on today's date, or a manually featured idea if set."""
    pool = await get_db()
    today = datetime.utcnow().date()

    async with pool.acquire() as conn:
        # Check for manually featured daily idea
        featured = await conn.fetchrow('''
            SELECT di.* FROM featured_ideas fi
            JOIN date_ideas di ON fi.date_idea_id = di.id
            WHERE fi.feature_type = 'daily' AND fi.feature_date = $1
        ''', today)

        if featured:
            idea = dict(featured)
            idea['id'] = str(idea['id'])
            idea['featured'] = True
            idea['feature_type'] = 'daily'
            return {"idea": idea, "date": str(today), "source": "curated_feature"}

        # Auto-select: deterministic random based on date
        count = await conn.fetchval("SELECT COUNT(*) FROM date_ideas")
        if count == 0:
            return {"idea": None, "date": str(today), "message": "No ideas available"}

        day_seed = int(today.strftime("%Y%m%d"))
        offset = day_seed % count

        row = await conn.fetchrow(
            "SELECT * FROM date_ideas ORDER BY created_at LIMIT 1 OFFSET $1", offset
        )
        idea = dict(row)
        idea['id'] = str(idea['id'])
        idea['featured'] = True
        idea['feature_type'] = 'daily'
        return {"idea": idea, "date": str(today), "source": "auto"}


@app.get("/api/date-ideas/weekly")
async def get_weekly_ideas():
    """Get featured date ideas for the current week (up to 7, one per day)."""
    pool = await get_db()
    today = datetime.utcnow().date()
    # Start of week (Monday)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    async with pool.acquire() as conn:
        # Check for manually featured weekly idea
        featured = await conn.fetchrow('''
            SELECT di.* FROM featured_ideas fi
            JOIN date_ideas di ON fi.date_idea_id = di.id
            WHERE fi.feature_type = 'weekly' AND fi.feature_date = $1
        ''', start_of_week)

        if featured:
            idea = dict(featured)
            idea['id'] = str(idea['id'])
            idea['featured'] = True
            idea['feature_type'] = 'weekly'
            return {"idea": idea, "week_start": str(start_of_week), "week_end": str(end_of_week), "source": "curated_feature"}

        # Auto-select: deterministic based on week number
        count = await conn.fetchval("SELECT COUNT(*) FROM date_ideas")
        if count == 0:
            return {"idea": None, "week_start": str(start_of_week), "message": "No ideas available"}

        week_seed = int(start_of_week.strftime("%Y%m%d"))
        offset = week_seed % count

        row = await conn.fetchrow(
            "SELECT * FROM date_ideas ORDER BY created_at LIMIT 1 OFFSET $1", offset
        )
        idea = dict(row)
        idea['id'] = str(idea['id'])
        idea['featured'] = True
        idea['feature_type'] = 'weekly'
        return {"idea": idea, "week_start": str(start_of_week), "week_end": str(end_of_week), "source": "auto"}


@app.post("/api/date-ideas/feature")
async def feature_idea(
    date_idea_id: str,
    feature_type: str = "daily",
    feature_date: Optional[str] = None
):
    """Manually set a featured idea for a specific date or week.
    feature_type: 'daily' or 'weekly'
    feature_date: ISO date string (defaults to today)"""
    pool = await get_db()

    if feature_type not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="feature_type must be 'daily' or 'weekly'")

    if feature_date:
        try:
            target_date = datetime.strptime(feature_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="feature_date must be YYYY-MM-DD")
    else:
        target_date = datetime.utcnow().date()

    async with pool.acquire() as conn:
        # Verify idea exists
        idea = await conn.fetchrow("SELECT id FROM date_ideas WHERE id = $1", uuid.UUID(date_idea_id))
        if not idea:
            raise HTTPException(status_code=404, detail="Date idea not found")

        # Upsert featured idea
        await conn.execute('''
            INSERT INTO featured_ideas (date_idea_id, feature_type, feature_date)
            VALUES ($1, $2, $3)
            ON CONFLICT (feature_type, feature_date)
            DO UPDATE SET date_idea_id = $1
        ''', uuid.UUID(date_idea_id), feature_type, target_date)

    return {"success": True, "message": f"Idea featured as {feature_type} for {target_date}"}

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

# ==================== OCCASIONS ====================

@app.post("/api/occasions/add")
async def add_occasion(data: OccasionCreate, user: TokenData = Depends(get_current_user)):
    """Add a special occasion (birthday, anniversary, holiday, etc.)"""
    pool = await get_db()

    try:
        # Parse the date string flexibly
        parsed_date = parse_date_string(data.date)

        occasion_id = uuid.uuid4()
        user_id = uuid.UUID(user.user_id)

        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO occasions
                    (id, user_id, person_name, occasion_type, date, reminder_days_before, notes, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            ''', occasion_id, user_id, data.person_name, data.occasion_type,
                parsed_date, data.reminder_days_before, data.notes)

        return {
            "success": True,
            "message": "Occasion added successfully",
            "occasion_id": str(occasion_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding occasion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding occasion: {str(e)}")

@app.get("/api/occasions")
async def get_user_occasions(user: TokenData = Depends(get_current_user)):
    """Get all occasions for current user"""
    pool = await get_db()

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT
                    id, user_id, person_name, occasion_type, date,
                    reminder_days_before, notes, reminder_sent, created_at, updated_at
                FROM occasions
                WHERE user_id = $1
                ORDER BY date ASC
            ''', uuid.UUID(user.user_id))

            occasions = []
            for row in rows:
                occasions.append({
                    "id": str(row['id']),
                    "user_id": str(row['user_id']),
                    "person_name": row['person_name'],
                    "occasion_type": row['occasion_type'],
                    "date": row['date'].isoformat() if row['date'] else None,
                    "reminder_days_before": row['reminder_days_before'],
                    "notes": row['notes'],
                    "reminder_sent": row['reminder_sent'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
                })

        return {"success": True, "occasions": occasions}

    except Exception as e:
        logger.error(f"Error getting occasions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting occasions: {str(e)}")

@app.get("/api/occasions/upcoming")
async def get_upcoming_occasions(days: int = 30, user: TokenData = Depends(get_current_user)):
    """Get upcoming occasions in next N days"""
    pool = await get_db()

    try:
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days)

        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT
                    id, user_id, person_name, occasion_type, date,
                    reminder_days_before, notes, reminder_sent, created_at, updated_at
                FROM occasions
                WHERE user_id = $1
                  AND date >= $2
                  AND date <= $3
                ORDER BY date ASC
            ''', uuid.UUID(user.user_id), start_date, end_date)

            occasions = []
            for row in rows:
                occasions.append({
                    "id": str(row['id']),
                    "user_id": str(row['user_id']),
                    "person_name": row['person_name'],
                    "occasion_type": row['occasion_type'],
                    "date": row['date'].isoformat() if row['date'] else None,
                    "reminder_days_before": row['reminder_days_before'],
                    "notes": row['notes'],
                    "reminder_sent": row['reminder_sent'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
                })

        return {"success": True, "upcoming_occasions": occasions}

    except Exception as e:
        logger.error(f"Error getting upcoming occasions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting upcoming occasions: {str(e)}")

@app.put("/api/occasions/{occasion_id}")
async def update_occasion(occasion_id: str, data: OccasionUpdate, user: TokenData = Depends(get_current_user)):
    """Update an occasion"""
    pool = await get_db()

    try:
        occasion_uuid = uuid.UUID(occasion_id)
        user_uuid = uuid.UUID(user.user_id)

        # Build update query dynamically
        updates = []
        params = []
        param_count = 0

        if data.person_name is not None:
            param_count += 1
            updates.append(f"person_name = ${param_count}")
            params.append(data.person_name)

        if data.occasion_type is not None:
            param_count += 1
            updates.append(f"occasion_type = ${param_count}")
            params.append(data.occasion_type)

        if data.date is not None:
            parsed_date = parse_date_string(data.date)
            param_count += 1
            updates.append(f"date = ${param_count}")
            params.append(parsed_date)

        if data.reminder_days_before is not None:
            param_count += 1
            updates.append(f"reminder_days_before = ${param_count}")
            params.append(data.reminder_days_before)

        if data.notes is not None:
            param_count += 1
            updates.append(f"notes = ${param_count}")
            params.append(data.notes)

        if not updates:
            return {"success": True, "message": "No updates provided"}

        # Add updated_at
        param_count += 1
        updates.append(f"updated_at = NOW()")

        # Add WHERE clause
        param_count += 1
        where_clause = f"id = ${param_count} AND user_id = ${param_count + 1}"
        params.append(occasion_uuid)
        params.append(user_uuid)

        query = f"UPDATE occasions SET {', '.join(updates)} WHERE {where_clause}"

        async with pool.acquire() as conn:
            result = await conn.execute(query, *params)

        if "0" in str(result):  # No rows affected
            raise HTTPException(status_code=404, detail="Occasion not found")

        return {"success": True, "message": "Occasion updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating occasion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating occasion: {str(e)}")

@app.delete("/api/occasions/{occasion_id}")
async def delete_occasion(occasion_id: str, user: TokenData = Depends(get_current_user)):
    """Delete an occasion"""
    pool = await get_db()

    try:
        occasion_uuid = uuid.UUID(occasion_id)
        user_uuid = uuid.UUID(user.user_id)

        async with pool.acquire() as conn:
            result = await conn.execute('''
                DELETE FROM occasions
                WHERE id = $1 AND user_id = $2
            ''', occasion_uuid, user_uuid)

        if "0" in str(result):  # No rows affected
            raise HTTPException(status_code=404, detail="Occasion not found")

        return {"success": True, "message": "Occasion deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting occasion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting occasion: {str(e)}")

# ==================== IDEA INTERACTIONS (Accept/Reject Tracking) ====================

class IdeaInteraction(BaseModel):
    date_idea_id: Optional[str] = None
    idea_title: Optional[str] = None  # For AI-generated ideas that may not be in DB

@app.post("/api/ideas/accept")
async def accept_idea(data: IdeaInteraction, user: TokenData = Depends(get_current_user)):
    """Record that the user accepted/liked a date idea."""
    pool = await get_db()
    user_uuid = uuid.UUID(user.user_id)

    idea_uuid = uuid.UUID(data.date_idea_id) if data.date_idea_id else None
    title = data.idea_title or ""

    # If we have an idea_id, fetch the title from DB
    if idea_uuid and not title:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT title FROM date_ideas WHERE id = $1", idea_uuid)
            if row:
                title = row['title']

    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO idea_interactions (user_id, date_idea_id, idea_title, action)
            VALUES ($1, $2, $3, 'accepted')
            ON CONFLICT (user_id, date_idea_id)
            DO UPDATE SET action = 'accepted', created_at = NOW()
        ''', user_uuid, idea_uuid, title)

    return {"success": True, "action": "accepted", "idea_title": title}


@app.post("/api/ideas/reject")
async def reject_idea(data: IdeaInteraction, user: TokenData = Depends(get_current_user)):
    """Record that the user rejected/skipped a date idea."""
    pool = await get_db()
    user_uuid = uuid.UUID(user.user_id)

    idea_uuid = uuid.UUID(data.date_idea_id) if data.date_idea_id else None
    title = data.idea_title or ""

    if idea_uuid and not title:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT title FROM date_ideas WHERE id = $1", idea_uuid)
            if row:
                title = row['title']

    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO idea_interactions (user_id, date_idea_id, idea_title, action)
            VALUES ($1, $2, $3, 'rejected')
            ON CONFLICT (user_id, date_idea_id)
            DO UPDATE SET action = 'rejected', created_at = NOW()
        ''', user_uuid, idea_uuid, title)

    return {"success": True, "action": "rejected", "idea_title": title}


@app.get("/api/ideas/interactions")
async def get_user_interactions(
    action: Optional[str] = None,
    limit: int = 50,
    user: TokenData = Depends(get_current_user)
):
    """Get the user's idea interaction history (accepts and rejects)."""
    pool = await get_db()
    user_uuid = uuid.UUID(user.user_id)

    query = "SELECT * FROM idea_interactions WHERE user_id = $1"
    params = [user_uuid]
    param_count = 1

    if action and action in ('accepted', 'rejected'):
        param_count += 1
        query += f" AND action = ${param_count}"
        params.append(action)

    param_count += 1
    query += f" ORDER BY created_at DESC LIMIT ${param_count}"
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        interactions = []
        for row in rows:
            item = dict(row)
            item['id'] = str(item['id'])
            item['user_id'] = str(item['user_id'])
            if item.get('date_idea_id'):
                item['date_idea_id'] = str(item['date_idea_id'])
            interactions.append(item)

    return {"interactions": interactions, "total": len(interactions)}


@app.get("/api/ideas/stats")
async def get_user_idea_stats(user: TokenData = Depends(get_current_user)):
    """Get user's accept/reject stats — shows preference profile."""
    pool = await get_db()
    user_uuid = uuid.UUID(user.user_id)

    async with pool.acquire() as conn:
        accepted = await conn.fetchval(
            "SELECT COUNT(*) FROM idea_interactions WHERE user_id = $1 AND action = 'accepted'",
            user_uuid
        )
        rejected = await conn.fetchval(
            "SELECT COUNT(*) FROM idea_interactions WHERE user_id = $1 AND action = 'rejected'",
            user_uuid
        )
        total = accepted + rejected
        acceptance_rate = round((accepted / total * 100), 1) if total > 0 else 0

        # Top accepted categories
        top_categories = await conn.fetch('''
            SELECT di.category, COUNT(*) as count
            FROM idea_interactions ii
            JOIN date_ideas di ON ii.date_idea_id = di.id
            WHERE ii.user_id = $1 AND ii.action = 'accepted'
            GROUP BY di.category
            ORDER BY count DESC
            LIMIT 5
        ''', user_uuid)

        # Recently accepted ideas
        recent_accepted = await conn.fetch('''
            SELECT ii.idea_title, ii.created_at
            FROM idea_interactions ii
            WHERE ii.user_id = $1 AND ii.action = 'accepted'
            ORDER BY ii.created_at DESC
            LIMIT 5
        ''', user_uuid)

    return {
        "accepted_count": accepted,
        "rejected_count": rejected,
        "total_interactions": total,
        "acceptance_rate": acceptance_rate,
        "top_categories": [{"category": r['category'], "count": r['count']} for r in top_categories],
        "recent_accepted": [{"title": r['idea_title'], "date": r['created_at'].isoformat() if r['created_at'] else None} for r in recent_accepted]
    }

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

# ==================== AI PROVIDER MANAGEMENT ====================

class ProviderSwitchRequest(BaseModel):
    """Request model for switching AI provider"""
    provider: str = Field(..., description="Provider name: gemini, claude, or openai")


@app.get("/api/ai/provider")
async def get_current_provider():
    """Get the current AI provider in use"""
    return {
        "current_provider": current_ai_provider,
        "available_providers": get_available_providers(),
        "description": f"Currently using {current_ai_provider.upper()} for AI generation"
    }


@app.get("/api/ai/providers")
async def list_available_providers():
    """List all available AI providers (those with API keys configured)"""
    available = get_available_providers()
    return {
        "available_providers": available,
        "count": len(available),
        "configured": {
            "gemini": bool(GEMINI_API_KEY),
            "claude": bool(ANTHROPIC_API_KEY),
            "openai": bool(OPENAI_API_KEY)
        }
    }


@app.put("/api/ai/provider")
async def switch_provider(request: ProviderSwitchRequest):
    """Switch to a different AI provider at runtime

    Args:
        request: Contains 'provider' field with target provider name

    Returns:
        Confirmation of provider switch
    """
    global current_ai_provider

    provider_name = request.provider.lower()
    available = get_available_providers()

    if provider_name not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_name}' is not available. Available providers: {', '.join(available)}"
        )

    current_ai_provider = provider_name
    logger.info(f"Switched AI provider to: {current_ai_provider}")

    return {
        "success": True,
        "current_provider": current_ai_provider,
        "message": f"Successfully switched to {current_ai_provider.upper()}"
    }


# ==================== SMART RECOMMENDATIONS ====================

@app.get("/api/recommendations/smart")
async def get_smart_recommendations(
    mood: Optional[str] = None,
    energy: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    count: int = 5,
    user: TokenData = Depends(get_current_user)
):
    """
    Get personalized date ideas using the smart preference algorithm v2.

    The algorithm analyzes:
    - User's accept/reject history (with recency weighting)
    - Temporal patterns (time-of-day, day-of-week preferences)
    - Post-date journal ratings (feedback depth)
    - Seasonal and anniversary awareness
    - Budget pacing (monthly spend tracking)
    - Freshness decay (suppress recently-done ideas)
    - Current mood and energy level
    - Current weather (if lat/lon provided)
    - Partner compatibility (if user has a partner)
    - Wildcard surprise injection

    Args:
        mood: Current mood ('adventurous', 'romantic', 'low_key', 'spontaneous', 'foodie', 'creative')
        energy: Energy level ('low', 'medium', 'high')
        lat: Latitude for weather lookup (optional)
        lon: Longitude for weather lookup (optional)
        count: Number of ideas to generate (default 5)
        user: Current authenticated user

    Returns:
        List of AI-generated date ideas tailored to all contextual signals
    """
    try:
        pool = await get_db()

        # Validate mood
        if mood and mood.lower() not in MOOD_OPTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mood. Choose from: {', '.join(MOOD_OPTIONS.keys())}"
            )

        # Validate energy
        if energy and energy.lower() not in ENERGY_LEVELS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid energy level. Choose from: {', '.join(ENERGY_LEVELS.keys())}"
            )

        # Get weather if coordinates provided
        weather = None
        if lat is not None and lon is not None:
            weather = await get_current_weather(lat, lon)

        # Get partner ID if user has a partner
        partner_id = None
        async with pool.acquire() as conn:
            partner_row = await conn.fetchrow(
                "SELECT id FROM users WHERE partner_name IS NOT NULL LIMIT 1"
            )
            if partner_row:
                partner_id = str(partner_row['id'])

        # Build smart prompt (v2 — includes all new signals)
        smart_prompt = await build_smart_prompt(
            user_id=user.user_id,
            pool=pool,
            partner_id=partner_id,
            mood=mood,
            energy=energy,
            weather=weather
        )

        # Generate ideas using AI provider
        provider = get_ai_provider(current_ai_provider)
        text = await provider.generate(smart_prompt, temperature=0.9, max_tokens=2048)

        # Clean and parse response
        text = clean_response_text(text)
        ideas = json.loads(text)

        # Enrich ideas with metadata
        for idea in ideas:
            idea["id"] = str(uuid.uuid4())
            idea["image_url"] = get_image_for_category(idea.get("category", "romantic"))
            idea["is_trending"] = False
            idea["created_at"] = datetime.utcnow().isoformat()
            idea["algorithm"] = "smart_v2"
            if mood:
                idea["mood_context"] = mood
            if energy:
                idea["energy_context"] = energy

        logger.info(f"Generated {len(ideas)} smart v2 recommendations for user {user.user_id}")
        return {"ideas": ideas, "count": len(ideas), "algorithm": "smart_v2"}

    except ValueError as e:
        logger.error(f"AI provider error: {e}")
        raise HTTPException(status_code=500, detail="AI provider not configured")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse recommendations")
    except Exception as e:
        logger.error(f"Error generating smart recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/preferences")
async def get_user_preference_profile(user: TokenData = Depends(get_current_user)):
    """
    Get the user's computed preference profile from interaction history.

    Analyzes the user's accept/reject interactions to return:
    - Category affinities
    - Budget distribution
    - Location preferences
    - Most-liked and most-rejected tags
    - Acceptance rate and statistics
    - Personality evolution insights

    Returns:
        Comprehensive preference analysis
    """
    try:
        pool = await get_db()
        preferences = await compute_user_preferences(user_id=user.user_id, pool=pool)

        # Add user's stated personality for comparison
        async with pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT personality_type, interests, budget_range, indoor_outdoor_preference FROM users WHERE id = $1",
                user.user_id
            )
            if user_row:
                preferences["stated_personality"] = user_row.get('personality_type')
                preferences["stated_interests"] = user_row.get('interests', [])

        logger.info(f"Retrieved preference profile for user {user.user_id}")
        return preferences

    except Exception as e:
        logger.error(f"Error computing preference profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/mood-options")
async def get_mood_options():
    """Get available mood options with descriptions."""
    return {
        "moods": MOOD_OPTIONS,
        "description": "Select a mood to adjust recommendations accordingly"
    }


@app.get("/api/recommendations/energy-options")
async def get_energy_options():
    """Get available energy level options with descriptions."""
    return {
        "energy_levels": {k: v["description"] for k, v in ENERGY_LEVELS.items()},
        "description": "Select an energy level to filter recommendations"
    }


@app.get("/api/recommendations/temporal")
async def get_temporal_insights(user: TokenData = Depends(get_current_user)):
    """Get the user's time-of-day and day-of-week preference patterns."""
    try:
        pool = await get_db()
        temporal = await compute_temporal_preferences(user_id=user.user_id, pool=pool)
        return temporal
    except Exception as e:
        logger.error(f"Error computing temporal preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/feedback")
async def get_feedback_insights(user: TokenData = Depends(get_current_user)):
    """Get preference insights derived from post-date journal ratings."""
    try:
        pool = await get_db()
        feedback = await compute_feedback_enhanced_preferences(user_id=user.user_id, pool=pool)
        return feedback
    except Exception as e:
        logger.error(f"Error computing feedback preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/seasonal")
async def get_seasonal_insights(user: TokenData = Depends(get_current_user)):
    """Get seasonal context and upcoming special dates / anniversaries."""
    try:
        pool = await get_db()
        seasonal = get_seasonal_context()
        anniversary = await get_anniversary_context(user_id=user.user_id, pool=pool)
        return {**seasonal, **anniversary}
    except Exception as e:
        logger.error(f"Error computing seasonal context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/budget")
async def get_budget_insights(user: TokenData = Depends(get_current_user)):
    """Get budget pacing and spending insights for the current month."""
    try:
        pool = await get_db()
        budget = await compute_budget_context(user_id=user.user_id, pool=pool)
        return budget
    except Exception as e:
        logger.error(f"Error computing budget context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/freshness")
async def get_freshness_insights(user: TokenData = Depends(get_current_user)):
    """Get freshness decay data — recently done ideas and suppressed tags."""
    try:
        pool = await get_db()
        freshness = await get_freshness_context(user_id=user.user_id, pool=pool)
        return freshness
    except Exception as e:
        logger.error(f"Error computing freshness context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/full-profile")
async def get_full_algorithm_profile(user: TokenData = Depends(get_current_user)):
    """
    Get the COMPLETE algorithm profile — all signals combined.
    Useful for debugging, admin view, or showing users their full preference DNA.
    """
    try:
        pool = await get_db()

        prefs = await compute_user_preferences(user_id=user.user_id, pool=pool)
        temporal = await compute_temporal_preferences(user_id=user.user_id, pool=pool)
        feedback = await compute_feedback_enhanced_preferences(user_id=user.user_id, pool=pool)
        seasonal = get_seasonal_context()
        anniversary = await get_anniversary_context(user_id=user.user_id, pool=pool)
        budget = await compute_budget_context(user_id=user.user_id, pool=pool)
        freshness = await get_freshness_context(user_id=user.user_id, pool=pool)

        return {
            "algorithm_version": "smart_v2",
            "preferences": prefs,
            "temporal_patterns": temporal,
            "feedback_depth": feedback,
            "seasonal_context": seasonal,
            "anniversary_context": anniversary,
            "budget_context": budget,
            "freshness_context": freshness,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error computing full profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/partner-compatibility")
async def get_partner_compatibility(
    partner_id: Optional[str] = None,
    user: TokenData = Depends(get_current_user)
):
    """
    Get couple compatibility analysis with the partner.

    If partner_id not provided, attempts to find the user's partner
    from their profile.

    Args:
        partner_id: UUID of partner (optional)
        user: Current authenticated user

    Returns:
        Compatibility score and recommendations for couple activities
    """
    try:
        pool = await get_db()

        # If no partner_id provided, try to find from user's profile
        if not partner_id:
            async with pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    "SELECT id FROM users WHERE partner_name IS NOT NULL LIMIT 1"
                )
                if not user_row:
                    raise HTTPException(
                        status_code=400,
                        detail="No partner information found. Provide partner_id parameter."
                    )
                partner_id = str(user_row['id'])

        # Compute compatibility
        compatibility = await compute_partner_compatibility(
            user_id=user.user_id,
            partner_id=partner_id,
            pool=pool
        )

        logger.info(f"Retrieved partner compatibility for user {user.user_id}")
        return compatibility

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing partner compatibility: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
