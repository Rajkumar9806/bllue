"""
Arrow Idea Seeding Engine

Provides multiple strategies for populating the date_ideas table at scale:
1. AI Bulk Generation - Generate 50-100 ideas in batches via AI providers
2. Curated Packs - Pre-built themed collections (Seasons, Budget, Occasion)
3. Community Sourcing - Users can submit ideas for review
4. Category Gap Filler - Auto-detect under-represented categories and fill them
5. Trending Refresh - Periodic refresh of trending/viral ideas

Admin dashboard included for managing seed operations.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import json
import logging
import random

logger = logging.getLogger(__name__)

# Global db_pool reference (injected from main.py)
db_pool: Optional[asyncpg.Pool] = None

# AI provider callback (set from main.py)
_generate_ai_fn = None
_current_provider = "gemini"

router = APIRouter()


def set_db_pool(pool: asyncpg.Pool):
    global db_pool
    db_pool = pool


def set_ai_generator(fn, provider: str = "gemini"):
    """Set the AI generation function from main.py"""
    global _generate_ai_fn, _current_provider
    _generate_ai_fn = fn
    _current_provider = provider


# ==================== CURATED IDEA PACKS ====================

IDEA_PACKS = {
    "budget_free": {
        "name": "Free & Fabulous",
        "description": "Amazing dates that cost nothing",
        "ideas": [
            ("Sunset Watching Marathon", "Find the highest point in your city and watch the sun paint the sky. Bring a blanket and your favorite playlist.", "romantic", "low", "1-2 hours", "outdoor", ["romantic", "free", "nature", "sunset"]),
            ("Photo Walk Challenge", "Take 50 photos of each other in creative spots around your neighborhood. Best photo wins bragging rights.", "creative", "low", "2-3 hours", "outdoor", ["creative", "free", "photography", "urban"]),
            ("Home Spa Night", "DIY face masks from kitchen ingredients, foot soaks, back massages, and aromatherapy with candles.", "relaxing", "low", "2 hours", "indoor", ["relaxing", "free", "spa", "romantic"]),
            ("Stargazing Blanket Date", "Lay under the stars with a star map app. Learn constellations and make wishes on shooting stars.", "romantic", "low", "2-3 hours", "outdoor", ["romantic", "free", "nature", "night"]),
            ("Living Room Dance Party", "Create a shared playlist, push the furniture aside, and dance like nobody's watching.", "fun", "low", "1-2 hours", "indoor", ["fun", "free", "music", "energetic"]),
            ("Bookstore Browsing", "Spend an hour picking books for each other. Read the first chapters together at a nearby cafe.", "cultural", "low", "2 hours", "indoor", ["cultural", "free", "intellectual", "cozy"]),
            ("Sunrise Hike", "Set an alarm, make thermos coffee, and hike to see the sunrise. The early wake-up makes it feel like an adventure.", "adventure", "low", "3-4 hours", "outdoor", ["adventure", "free", "nature", "morning"]),
            ("Memory Lane Walk", "Walk through places that are meaningful to your relationship. First date spot, first kiss location, etc.", "romantic", "low", "2 hours", "outdoor", ["romantic", "free", "nostalgic", "walking"]),
            ("DIY Movie Night", "Build a blanket fort, make popcorn, create a double feature with your favorite genres.", "relaxing", "low", "3-4 hours", "indoor", ["relaxing", "free", "cozy", "movie"]),
            ("Volunteer Together", "Spend a morning at a food bank, animal shelter, or community garden. Doing good together strengthens bonds.", "meaningful", "low", "3-4 hours", "outdoor", ["meaningful", "free", "giving-back", "bonding"]),
        ]
    },
    "luxury_splurge": {
        "name": "Luxury Splurge",
        "description": "Premium date experiences for special occasions",
        "ideas": [
            ("Private Chef Dinner", "Hire a private chef to prepare a multi-course tasting menu in your home. Wine pairing included.", "foodie", "high", "3-4 hours", "indoor", ["foodie", "luxurious", "special", "gourmet"]),
            ("Helicopter City Tour", "See your city from above with a sunset helicopter ride. Some include champagne service.", "adventure", "high", "1-2 hours", "outdoor", ["adventure", "luxurious", "views", "bucket-list"]),
            ("Couples Spa Retreat", "Full-day spa package with couples massage, facial, sauna, and champagne lunch.", "relaxing", "high", "full day", "indoor", ["relaxing", "luxurious", "spa", "romantic"]),
            ("Wine Country Day Trip", "Private car to wine country. Visit 3-4 wineries with tastings and a vineyard lunch.", "foodie", "high", "full day", "outdoor", ["foodie", "luxurious", "wine", "scenic"]),
            ("Rooftop Suite Staycation", "Book a luxury hotel suite with skyline views. Room service breakfast, late checkout.", "romantic", "high", "overnight", "indoor", ["romantic", "luxurious", "staycation", "special"]),
            ("Private Sailing Sunset", "Charter a private sailboat for a sunset cruise with champagne and charcuterie.", "romantic", "high", "2-3 hours", "outdoor", ["romantic", "luxurious", "water", "sunset"]),
            ("Omakase Sushi Experience", "Book a chef's counter omakase at a top Japanese restaurant. 15+ courses of seasonal sushi.", "foodie", "high", "2 hours", "indoor", ["foodie", "luxurious", "japanese", "fine-dining"]),
            ("Hot Air Balloon Sunrise", "Float above vineyards or mountains at sunrise. Many include post-flight champagne brunch.", "adventure", "high", "3-4 hours", "outdoor", ["adventure", "luxurious", "bucket-list", "romantic"]),
        ]
    },
    "stay_home": {
        "name": "Stay Home Dates",
        "description": "Cozy ideas when you don't want to leave the house",
        "ideas": [
            ("International Cooking Challenge", "Pick a country, find an authentic recipe, shop for ingredients, and cook a full meal together.", "foodie", "medium", "3 hours", "indoor", ["foodie", "cooking", "interactive", "learning"]),
            ("Board Game Tournament", "Set up a bracket with 4-5 games. Keep score across all games. Loser makes dessert.", "fun", "low", "3-4 hours", "indoor", ["fun", "competitive", "cozy", "games"]),
            ("Paint & Sip Night", "Buy canvases and paint from the dollar store. Follow a YouTube tutorial together while sipping wine.", "creative", "low", "2-3 hours", "indoor", ["creative", "artistic", "relaxing", "wine"]),
            ("Blindfolded Taste Test", "Blindfold each other and guess foods, drinks, or snacks. Points for correct guesses.", "fun", "low", "1-2 hours", "indoor", ["fun", "interactive", "foodie", "silly"]),
            ("Build Something Together", "LEGO set, puzzle, model kit, or flat-pack furniture. Teamwork with a tangible result.", "creative", "medium", "2-4 hours", "indoor", ["creative", "teamwork", "hands-on", "rewarding"]),
            ("At-Home Wine Tasting", "Buy 4-5 small bottles from different regions. Make tasting notes, rate them, find your couple favorite.", "foodie", "medium", "2 hours", "indoor", ["foodie", "wine", "sophisticated", "learning"]),
            ("Couple's Quiz Night", "Take online couple quizzes, create questions about each other, see who knows the other better.", "fun", "low", "1-2 hours", "indoor", ["fun", "bonding", "interactive", "romantic"]),
            ("Documentary Deep Dive", "Pick a topic neither of you knows about. Watch 2-3 related documentaries and discuss.", "cultural", "low", "3-4 hours", "indoor", ["cultural", "intellectual", "cozy", "learning"]),
            ("Indoor Camping", "Set up a tent (or blanket fort), make s'mores on the stove, tell stories, sleep in sleeping bags.", "romantic", "low", "overnight", "indoor", ["romantic", "fun", "creative", "cozy"]),
            ("Cocktail Lab", "Pick 3 cocktails you've never made. Buy ingredients, experiment, create your signature couple drink.", "foodie", "medium", "2 hours", "indoor", ["foodie", "creative", "drinks", "fun"]),
        ]
    },
    "adventure_seekers": {
        "name": "Adventure Seekers",
        "description": "Adrenaline-pumping dates for thrill-loving couples",
        "ideas": [
            ("Indoor Rock Climbing", "Hit a climbing gym together. Belaying each other builds trust literally and figuratively.", "adventure", "medium", "2-3 hours", "indoor", ["adventure", "active", "trust", "fitness"]),
            ("Go-Kart Racing", "Channel your competitive side at an indoor go-kart track. Best of 3 races.", "fun", "medium", "1-2 hours", "indoor", ["fun", "competitive", "adrenaline", "exciting"]),
            ("Zip-Lining", "Soar through the treetops on a zip-line course. The shared adrenaline creates lasting memories.", "adventure", "medium", "2-3 hours", "outdoor", ["adventure", "adrenaline", "nature", "exciting"]),
            ("Surfing Lesson", "Book a couples surfing lesson. Laughing at each other's wipeouts is half the fun.", "adventure", "medium", "2-3 hours", "outdoor", ["adventure", "water", "active", "summer"]),
            ("Escape Room: Hard Mode", "Book the hardest escape room available. Test your teamwork under pressure.", "adventure", "medium", "1-2 hours", "indoor", ["adventure", "teamwork", "puzzle", "exciting"]),
            ("Night Kayaking", "Some companies offer LED-lit night kayaking tours. Paddle through glowing water together.", "adventure", "medium", "2 hours", "outdoor", ["adventure", "water", "unique", "night"]),
            ("Trampoline Park", "Jump, flip, and play dodgeball at a trampoline park. You'll feel like kids again.", "fun", "medium", "1-2 hours", "indoor", ["fun", "active", "playful", "energetic"]),
            ("Mountain Biking", "Rent mountain bikes and hit a trail. Start with beginner-friendly routes and work your way up.", "adventure", "medium", "3-4 hours", "outdoor", ["adventure", "active", "nature", "fitness"]),
        ]
    },
    "cultural_enrichment": {
        "name": "Culture & Connection",
        "description": "Feed your minds and souls together",
        "ideas": [
            ("Live Theater Night", "See a play or musical at a local theater. Dress up and make it an event.", "cultural", "medium", "3 hours", "indoor", ["cultural", "theater", "artistic", "evening"]),
            ("Museum Scavenger Hunt", "Create a list of things to find in a museum. First to find all items picks dinner.", "cultural", "low", "2-3 hours", "indoor", ["cultural", "fun", "interactive", "arts"]),
            ("Foreign Film Marathon", "Pick a country and watch 3 films from that culture. Cook food from the same country.", "cultural", "low", "4-5 hours", "indoor", ["cultural", "intellectual", "cozy", "worldly"]),
            ("Poetry Open Mic", "Attend a local poetry slam or open mic night. Bonus: write and perform a piece for each other.", "creative", "low", "2-3 hours", "indoor", ["creative", "artistic", "intellectual", "nightlife"]),
            ("Cooking Class: New Cuisine", "Take a class in a cuisine neither of you has cooked — Ethiopian, Thai, Moroccan.", "foodie", "medium", "3 hours", "indoor", ["foodie", "learning", "cultural", "hands-on"]),
            ("Street Art Walking Tour", "Map out murals and street art in your city. Take photos, research the artists.", "cultural", "low", "2-3 hours", "outdoor", ["cultural", "artistic", "urban", "photography"]),
            ("Jazz Club Evening", "Find a dimly lit jazz club. Order craft cocktails and let the music set the mood.", "cultural", "medium", "2-3 hours", "indoor", ["cultural", "music", "romantic", "nightlife"]),
            ("Bookshop Crawl", "Visit 3-4 independent bookshops. Buy one book at each. Share your finds over dinner.", "cultural", "medium", "3-4 hours", "indoor", ["cultural", "intellectual", "urban", "cozy"]),
        ]
    },
    "seasonal_spring": {
        "name": "Spring Awakening",
        "description": "Fresh ideas for the season of renewal",
        "ideas": [
            ("Cherry Blossom Picnic", "Find a park with blooming trees. Pack a picnic basket and enjoy the petals falling around you.", "romantic", "low", "2-3 hours", "outdoor", ["romantic", "spring", "nature", "picnic"]),
            ("Farmers Market & Cook", "Hit the first spring farmers market. Buy fresh produce and cook a seasonal meal together.", "foodie", "medium", "3-4 hours", "outdoor", ["foodie", "spring", "local", "cooking"]),
            ("Garden Center Date", "Browse a garden center together. Pick plants for your balcony or windowsill. Start something growing.", "creative", "low", "1-2 hours", "outdoor", ["creative", "spring", "nature", "building"]),
            ("Bike the Bloom Route", "Rent bikes and ride through neighborhoods with the best spring flowers. End at a cafe.", "adventure", "low", "2-3 hours", "outdoor", ["adventure", "spring", "active", "scenic"]),
            ("Outdoor Yoga Session", "Find a park, lay out mats, and do a couples yoga session in the fresh spring air.", "relaxing", "low", "1-2 hours", "outdoor", ["relaxing", "spring", "fitness", "mindful"]),
        ]
    },
    "seasonal_summer": {
        "name": "Summer Heat",
        "description": "Sizzling summer date ideas",
        "ideas": [
            ("Beach Bonfire Sunset", "Build a bonfire on the beach at sunset. Bring marshmallows, a guitar, or a bluetooth speaker.", "romantic", "low", "3-4 hours", "outdoor", ["romantic", "summer", "beach", "night"]),
            ("Outdoor Movie Screening", "Find an outdoor cinema or set up a projector in the backyard. Blankets and popcorn required.", "relaxing", "low", "2-3 hours", "outdoor", ["relaxing", "summer", "movie", "outdoor"]),
            ("Stand-Up Paddleboard", "Rent paddleboards and explore a lake or calm bay. Bring a waterproof speaker for tunes.", "adventure", "medium", "2-3 hours", "outdoor", ["adventure", "summer", "water", "active"]),
            ("Food Festival Crawl", "Hit a summer food festival. Try everything, share bites, rate each vendor.", "foodie", "medium", "3-4 hours", "outdoor", ["foodie", "summer", "festival", "social"]),
            ("Rooftop Sunset Drinks", "Find the best rooftop bar in the city. Arrive before sunset, stay for golden hour.", "romantic", "medium", "2-3 hours", "outdoor", ["romantic", "summer", "views", "drinks"]),
        ]
    },
    "seasonal_fall": {
        "name": "Autumn Coziness",
        "description": "Warm and cozy fall date ideas",
        "ideas": [
            ("Apple Picking & Cider", "Visit an apple orchard. Pick apples, drink fresh cider, share a cider donut.", "fun", "low", "3-4 hours", "outdoor", ["fun", "fall", "nature", "seasonal"]),
            ("Pumpkin Patch & Carving", "Visit a pumpkin patch, pick your pumpkins, then carve them together at home.", "creative", "low", "3-4 hours", "both", ["creative", "fall", "seasonal", "fun"]),
            ("Cozy Café Crawl", "Visit 3-4 cafes in one afternoon. Rate each one's latte, ambiance, and pastry.", "foodie", "medium", "3 hours", "indoor", ["foodie", "fall", "cozy", "urban"]),
            ("Haunted House", "Visit a haunted house or haunted corn maze. Hold hands through the scares.", "fun", "medium", "1-2 hours", "outdoor", ["fun", "fall", "spooky", "adrenaline"]),
            ("Leaf Peeping Drive", "Drive scenic routes to see fall foliage. Stop at a small-town diner for lunch.", "romantic", "low", "full day", "outdoor", ["romantic", "fall", "nature", "scenic"]),
        ]
    },
    "seasonal_winter": {
        "name": "Winter Warmth",
        "description": "Cozy winter date night ideas",
        "ideas": [
            ("Ice Skating & Hot Cocoa", "Hit an outdoor ice rink, hold hands (or fall together), warm up with hot chocolate after.", "fun", "low", "2 hours", "outdoor", ["fun", "winter", "active", "romantic"]),
            ("Holiday Light Drive", "Drive around neighborhoods with the best holiday lights. Rate houses, sip hot cocoa in the car.", "romantic", "low", "1-2 hours", "outdoor", ["romantic", "winter", "holiday", "cozy"]),
            ("Fondue Night", "Make cheese fondue and chocolate fondue at home. Dip everything — bread, fruit, pretzels, marshmallows.", "foodie", "medium", "2-3 hours", "indoor", ["foodie", "winter", "romantic", "indulgent"]),
            ("Cabin Getaway", "Book a cozy cabin for a weekend. Fireplace, hot tub, no cell service. Just the two of you.", "romantic", "high", "weekend", "indoor", ["romantic", "winter", "getaway", "luxurious"]),
            ("Snowshoeing or Cross-Country Skiing", "Rent gear and explore snowy trails. The quiet of a winter forest is magical.", "adventure", "medium", "3-4 hours", "outdoor", ["adventure", "winter", "active", "nature"]),
        ]
    },
}


# ==================== AI BULK GENERATION ====================

async def generate_bulk_ideas(
    category: Optional[str] = None,
    budget: Optional[str] = None,
    count: int = 20,
    theme: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate a batch of ideas using AI, optionally filtered by category/budget/theme.
    Returns parsed ideas ready for DB insertion.
    """
    from ai_providers import get_ai_provider, clean_response_text

    constraints = []
    if category:
        constraints.append(f"Category focus: {category}")
    if budget:
        constraints.append(f"Budget level: {budget}")
    if theme:
        constraints.append(f"Theme: {theme}")

    constraint_text = "\n".join(constraints) if constraints else "Variety across all categories and budgets"

    prompt = f"""Generate exactly {count} unique, creative date night ideas for a dating app.

Requirements:
{constraint_text}

Rules:
- Every idea must be unique and specific (not generic)
- Include a mix of indoor/outdoor, different durations, and varied tags
- Make ideas actionable and detailed
- Include estimated cost range in the description
- Each idea should have 3-5 relevant tags

Return ONLY a valid JSON array (no markdown):
[
  {{
    "title": "Specific Date Idea Title",
    "description": "Detailed 2-3 sentence description with actionable steps",
    "category": "romantic|adventure|foodie|creative|relaxing|fun|cultural|active",
    "budget": "low|medium|high",
    "duration": "duration estimate",
    "location_type": "indoor|outdoor|both",
    "tags": ["tag1", "tag2", "tag3"],
    "source": "ai-seeded"
  }}
]"""

    try:
        provider = get_ai_provider(_current_provider)
        text = await provider.generate(prompt, temperature=0.95, max_tokens=4096)
        text = clean_response_text(text)
        ideas = json.loads(text)

        # Validate and clean
        valid = []
        for idea in ideas:
            if idea.get('title') and idea.get('description'):
                idea['id'] = str(uuid.uuid4())
                idea['source'] = 'ai-seeded'
                valid.append(idea)

        return valid
    except Exception as e:
        logger.error(f"Bulk generation failed: {e}")
        return []


# ==================== CATEGORY GAP ANALYSIS ====================

async def analyze_category_gaps() -> Dict[str, Any]:
    """
    Analyze the current idea database to find under-represented categories,
    budgets, and location types.
    """
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM date_ideas")

        cat_counts = await conn.fetch("""
            SELECT category, COUNT(*) as count
            FROM date_ideas
            GROUP BY category
            ORDER BY count ASC
        """)

        budget_counts = await conn.fetch("""
            SELECT budget, COUNT(*) as count
            FROM date_ideas
            GROUP BY budget
            ORDER BY count ASC
        """)

        loc_counts = await conn.fetch("""
            SELECT location_type, COUNT(*) as count
            FROM date_ideas
            GROUP BY location_type
            ORDER BY count ASC
        """)

        # Source distribution
        source_counts = await conn.fetch("""
            SELECT COALESCE(source, 'unknown') as source, COUNT(*) as count
            FROM date_ideas
            GROUP BY source
            ORDER BY count DESC
        """)

    target_cats = ["romantic", "adventure", "foodie", "creative", "relaxing", "fun", "cultural", "active"]
    cat_dict = {row['category']: row['count'] for row in cat_counts}
    avg_per_cat = total / max(len(target_cats), 1)

    gaps = {
        "total_ideas": total,
        "category_distribution": {row['category']: row['count'] for row in cat_counts},
        "budget_distribution": {row['budget']: row['count'] for row in budget_counts},
        "location_distribution": {row['location_type']: row['count'] for row in loc_counts},
        "source_distribution": {row['source']: row['count'] for row in source_counts},
        "under_represented_categories": [
            cat for cat in target_cats if cat_dict.get(cat, 0) < avg_per_cat * 0.5
        ],
        "missing_categories": [
            cat for cat in target_cats if cat not in cat_dict
        ],
        "avg_per_category": round(avg_per_cat, 1),
    }

    return gaps


# ==================== DB INSERTION ====================

async def insert_ideas_batch(ideas: List[Dict[str, Any]], source: str = "seeded") -> int:
    """Insert a batch of ideas into date_ideas table. Returns count inserted."""
    if not ideas:
        return 0

    inserted = 0
    async with db_pool.acquire() as conn:
        for idea in ideas:
            try:
                # Check for duplicate title
                existing = await conn.fetchval(
                    "SELECT COUNT(*) FROM date_ideas WHERE LOWER(title) = LOWER($1)",
                    idea.get('title', '')
                )
                if existing > 0:
                    continue

                await conn.execute('''
                    INSERT INTO date_ideas
                    (title, description, category, budget, duration, location_type,
                     image_url, tags, is_trending, source, updated_by)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ''',
                    idea.get('title', 'Untitled'),
                    idea.get('description', ''),
                    idea.get('category', 'fun'),
                    idea.get('budget', 'medium'),
                    idea.get('duration', ''),
                    idea.get('location_type', 'both'),
                    idea.get('image_url', ''),
                    idea.get('tags', []),
                    idea.get('is_trending', False),
                    source,
                    'seeder'
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert idea '{idea.get('title')}': {e}")

    return inserted


# ==================== USER IDEA SUBMISSION ====================

async def init_seeder_tables():
    """Initialize tables needed by the seeder."""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_submitted_ideas (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                budget VARCHAR(20),
                location_type VARCHAR(50),
                tags TEXT[],
                status VARCHAR(20) DEFAULT 'pending',
                reviewed_by VARCHAR(255),
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Seed job tracking
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS seed_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                job_type VARCHAR(50) NOT NULL,
                status VARCHAR(20) DEFAULT 'running',
                ideas_generated INTEGER DEFAULT 0,
                ideas_inserted INTEGER DEFAULT 0,
                details JSONB,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        ''')
    logger.info("Seeder tables initialized")


# ==================== API ENDPOINTS ====================

@router.post("/admin/seeder/install-pack")
async def install_idea_pack(pack_name: str):
    """Install a curated idea pack into the database."""
    if pack_name not in IDEA_PACKS:
        raise HTTPException(
            status_code=404,
            detail=f"Pack '{pack_name}' not found. Available: {', '.join(IDEA_PACKS.keys())}"
        )

    pack = IDEA_PACKS[pack_name]
    ideas = []
    for title, desc, cat, budget, duration, loc, tags in pack["ideas"]:
        ideas.append({
            "title": title,
            "description": desc,
            "category": cat,
            "budget": budget,
            "duration": duration,
            "location_type": loc,
            "tags": tags,
            "image_url": "",
            "is_trending": False,
        })

    inserted = await insert_ideas_batch(ideas, source=f"pack:{pack_name}")

    # Log the job
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO seed_jobs (job_type, status, ideas_generated, ideas_inserted, details, completed_at)
            VALUES ($1, 'completed', $2, $3, $4, NOW())
        ''', f"pack:{pack_name}", len(ideas), inserted,
            json.dumps({"pack": pack_name, "pack_size": len(ideas)}))

    return {
        "success": True,
        "pack": pack_name,
        "total_in_pack": len(ideas),
        "inserted": inserted,
        "skipped_duplicates": len(ideas) - inserted
    }


@router.post("/admin/seeder/install-all-packs")
async def install_all_packs():
    """Install ALL curated idea packs."""
    results = {}
    total_inserted = 0

    for pack_name in IDEA_PACKS:
        pack = IDEA_PACKS[pack_name]
        ideas = []
        for title, desc, cat, budget, duration, loc, tags in pack["ideas"]:
            ideas.append({
                "title": title,
                "description": desc,
                "category": cat,
                "budget": budget,
                "duration": duration,
                "location_type": loc,
                "tags": tags,
                "image_url": "",
                "is_trending": False,
            })

        inserted = await insert_ideas_batch(ideas, source=f"pack:{pack_name}")
        results[pack_name] = {"total": len(ideas), "inserted": inserted}
        total_inserted += inserted

    return {
        "success": True,
        "packs_installed": len(IDEA_PACKS),
        "total_inserted": total_inserted,
        "details": results
    }


@router.post("/admin/seeder/generate-ai")
async def ai_bulk_generate(
    category: Optional[str] = None,
    budget: Optional[str] = None,
    count: int = 20,
    theme: Optional[str] = None
):
    """Generate ideas using AI and insert into database."""
    job_id = uuid.uuid4()

    # Log job start
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO seed_jobs (id, job_type, status, details)
            VALUES ($1, 'ai-bulk', 'running', $2)
        ''', job_id, json.dumps({"category": category, "budget": budget, "count": count, "theme": theme}))

    ideas = await generate_bulk_ideas(category=category, budget=budget, count=count, theme=theme)
    inserted = await insert_ideas_batch(ideas, source="ai-seeded")

    # Update job
    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE seed_jobs SET status = 'completed', ideas_generated = $1, ideas_inserted = $2, completed_at = NOW()
            WHERE id = $3
        ''', len(ideas), inserted, job_id)

    return {
        "success": True,
        "job_id": str(job_id),
        "generated": len(ideas),
        "inserted": inserted,
        "skipped_duplicates": len(ideas) - inserted
    }


@router.post("/admin/seeder/fill-gaps")
async def auto_fill_gaps():
    """Analyze category gaps and auto-generate ideas to fill them."""
    gaps = await analyze_category_gaps()
    under = gaps.get("under_represented_categories", []) + gaps.get("missing_categories", [])

    if not under:
        return {"success": True, "message": "No gaps found. Database is well balanced.", "gaps": gaps}

    total_inserted = 0
    fill_results = {}

    for cat in under:
        ideas = await generate_bulk_ideas(category=cat, count=10)
        inserted = await insert_ideas_batch(ideas, source="gap-fill")
        fill_results[cat] = {"generated": len(ideas), "inserted": inserted}
        total_inserted += inserted

    return {
        "success": True,
        "gaps_found": under,
        "total_inserted": total_inserted,
        "details": fill_results
    }


@router.get("/admin/seeder/gaps")
async def get_category_gaps():
    """Get current category gap analysis."""
    gaps = await analyze_category_gaps()
    return gaps


@router.get("/admin/seeder/packs")
async def list_available_packs():
    """List all available curated idea packs."""
    packs = {}
    for name, pack in IDEA_PACKS.items():
        packs[name] = {
            "name": pack["name"],
            "description": pack["description"],
            "idea_count": len(pack["ideas"]),
            "categories": list(set(idea[2] for idea in pack["ideas"])),
        }
    return {"packs": packs, "total_packs": len(IDEA_PACKS)}


@router.get("/admin/seeder/jobs")
async def get_seed_jobs(limit: int = 20):
    """Get recent seed job history."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM seed_jobs
            ORDER BY started_at DESC
            LIMIT $1
        """, limit)

    jobs = []
    for row in rows:
        item = dict(row)
        item['id'] = str(item['id'])
        jobs.append(item)

    return {"jobs": jobs}


@router.post("/api/ideas/submit")
async def submit_user_idea(
    title: str,
    description: str,
    category: str = "fun",
    budget: str = "medium",
    location_type: str = "both",
    tags: str = "",  # Comma-separated
    user_id: Optional[str] = None
):
    """Allow users to submit their own date ideas for review."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    async with db_pool.acquire() as conn:
        idea_id = uuid.uuid4()
        await conn.execute('''
            INSERT INTO user_submitted_ideas
            (id, user_id, title, description, category, budget, location_type, tags, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
        ''', idea_id,
            uuid.UUID(user_id) if user_id else None,
            title, description, category, budget, location_type, tag_list)

    return {"success": True, "idea_id": str(idea_id), "status": "pending"}


@router.get("/admin/seeder/submissions")
async def get_user_submissions(status: str = "pending", limit: int = 50):
    """Get user-submitted ideas by status."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM user_submitted_ideas
            WHERE status = $1
            ORDER BY created_at DESC
            LIMIT $2
        """, status, limit)

    items = []
    for row in rows:
        item = dict(row)
        item['id'] = str(item['id'])
        if item.get('user_id'):
            item['user_id'] = str(item['user_id'])
        items.append(item)

    return {"submissions": items, "total": len(items)}


@router.post("/admin/seeder/submissions/{idea_id}/approve")
async def approve_submission(idea_id: str):
    """Approve a user-submitted idea and add it to the main database."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_submitted_ideas WHERE id = $1",
            uuid.UUID(idea_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        if row['status'] != 'pending':
            raise HTTPException(status_code=400, detail=f"Submission already {row['status']}")

        # Insert into main ideas table
        await conn.execute('''
            INSERT INTO date_ideas
            (title, description, category, budget, location_type, tags, source, updated_by)
            VALUES ($1, $2, $3, $4, $5, $6, 'user-submitted', 'admin')
        ''', row['title'], row['description'], row['category'],
            row['budget'], row['location_type'], row['tags'])

        # Update submission status
        await conn.execute('''
            UPDATE user_submitted_ideas SET status = 'approved', reviewed_at = NOW()
            WHERE id = $1
        ''', uuid.UUID(idea_id))

    return {"success": True, "message": "Submission approved and added to database"}


@router.post("/admin/seeder/submissions/{idea_id}/reject")
async def reject_submission(idea_id: str):
    """Reject a user-submitted idea."""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE user_submitted_ideas SET status = 'rejected', reviewed_at = NOW()
            WHERE id = $1
        ''', uuid.UUID(idea_id))

    return {"success": True, "message": "Submission rejected"}


# ==================== ADMIN DASHBOARD ====================

@router.get("/admin/seeder", response_class=HTMLResponse)
async def seeder_dashboard():
    """Idea Seeding Engine admin dashboard."""

    # Gather stats
    gaps = await analyze_category_gaps()
    total = gaps['total_ideas']
    cat_dist = gaps['category_distribution']
    source_dist = gaps['source_distribution']

    # Build category bars
    max_count = max(cat_dist.values()) if cat_dist else 1
    cat_bars = ""
    for cat, count in sorted(cat_dist.items(), key=lambda x: -x[1]):
        pct = int(count / max_count * 100)
        cat_bars += f"""
        <div class="bar-row">
            <span class="bar-label">{cat}</span>
            <div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>
            <span class="bar-count">{count}</span>
        </div>"""

    # Build pack cards
    pack_cards = ""
    for name, pack in IDEA_PACKS.items():
        cats = list(set(idea[2] for idea in pack["ideas"]))
        pack_cards += f"""
        <div class="pack-card">
            <h4>{pack['name']}</h4>
            <p>{pack['description']}</p>
            <div class="pack-meta">{len(pack['ideas'])} ideas &middot; {', '.join(cats[:3])}</div>
            <button onclick="installPack('{name}')" class="btn btn-sm">Install Pack</button>
        </div>"""

    # Source badges
    source_html = ""
    for src, count in source_dist.items():
        source_html += f'<span class="source-badge">{src}: {count}</span> '

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Arrow — Idea Seeding Engine</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', sans-serif; background: #0f0f13; color: #e0e0e0; padding: 24px; }}
  h1 {{ font-size: 28px; color: #fff; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; color: #aaa; margin-bottom: 20px; font-weight: 400; }}
  h3 {{ font-size: 16px; color: #E83858; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }}

  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .stat {{ background: #1a1a22; border-radius: 12px; padding: 20px; text-align: center; }}
  .stat .num {{ font-size: 36px; font-weight: 700; color: #E83858; }}
  .stat .label {{ font-size: 12px; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }}

  .section {{ background: #1a1a22; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}

  .bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
  .bar-label {{ width: 80px; font-size: 13px; color: #aaa; text-align: right; }}
  .bar-track {{ flex: 1; height: 20px; background: #2a2a35; border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg, #E83858, #FF6B8A); border-radius: 4px; transition: width 0.5s; }}
  .bar-count {{ width: 40px; font-size: 13px; color: #888; }}

  .pack-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }}
  .pack-card {{ background: #22222e; border-radius: 10px; padding: 16px; }}
  .pack-card h4 {{ color: #fff; margin-bottom: 4px; }}
  .pack-card p {{ font-size: 12px; color: #888; margin-bottom: 8px; }}
  .pack-meta {{ font-size: 11px; color: #666; margin-bottom: 10px; }}

  .btn {{ background: #E83858; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }}
  .btn:hover {{ background: #d02e4c; }}
  .btn-sm {{ padding: 6px 12px; font-size: 12px; }}
  .btn-outline {{ background: transparent; border: 1px solid #E83858; color: #E83858; }}
  .btn-outline:hover {{ background: #E83858; color: white; }}

  .actions {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}

  .source-badge {{ display: inline-block; background: #2a2a35; padding: 4px 10px; border-radius: 12px; font-size: 11px; color: #aaa; margin-right: 6px; }}

  .ai-form {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: end; }}
  .form-group {{ display: flex; flex-direction: column; gap: 4px; }}
  .form-group label {{ font-size: 11px; color: #888; text-transform: uppercase; }}
  .form-group select, .form-group input {{ background: #2a2a35; border: 1px solid #333; color: #fff; padding: 8px; border-radius: 6px; font-size: 13px; }}

  #result {{ margin-top: 16px; padding: 12px; background: #161620; border-radius: 8px; font-size: 13px; color: #aaa; display: none; }}

  .gaps-list {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .gap-tag {{ background: #3a1a22; color: #E83858; padding: 4px 10px; border-radius: 12px; font-size: 12px; }}
</style>
</head><body>

<h1>Idea Seeding Engine</h1>
<h2>Populate your date ideas database at scale</h2>

<div class="stats">
  <div class="stat"><div class="num">{total}</div><div class="label">Total Ideas</div></div>
  <div class="stat"><div class="num">{len(cat_dist)}</div><div class="label">Categories</div></div>
  <div class="stat"><div class="num">{len(IDEA_PACKS)}</div><div class="label">Packs Available</div></div>
  <div class="stat"><div class="num">{len(gaps.get('under_represented_categories', []))}</div><div class="label">Gaps Found</div></div>
</div>

<div class="section">
  <h3>Quick Actions</h3>
  <div class="actions">
    <button onclick="installAll()" class="btn">Install All Packs</button>
    <button onclick="fillGaps()" class="btn btn-outline">Auto-Fill Gaps</button>
    <button onclick="refreshGaps()" class="btn btn-outline">Re-analyze Gaps</button>
  </div>
  <div id="result"></div>
</div>

<div class="section">
  <h3>Category Distribution</h3>
  {cat_bars}
  <div style="margin-top:16px;">
    <h3 style="margin-top:16px;">Sources</h3>
    {source_html}
  </div>
  {"<div style='margin-top:16px;'><h3>Under-Represented</h3><div class='gaps-list'>" + "".join(f"<span class='gap-tag'>{c}</span>" for c in gaps.get('under_represented_categories', [])) + "</div></div>" if gaps.get('under_represented_categories') else ""}
</div>

<div class="section">
  <h3>AI Bulk Generate</h3>
  <div class="ai-form">
    <div class="form-group">
      <label>Category</label>
      <select id="ai-cat">
        <option value="">Any</option>
        <option value="romantic">Romantic</option>
        <option value="adventure">Adventure</option>
        <option value="foodie">Foodie</option>
        <option value="creative">Creative</option>
        <option value="relaxing">Relaxing</option>
        <option value="fun">Fun</option>
        <option value="cultural">Cultural</option>
        <option value="active">Active</option>
      </select>
    </div>
    <div class="form-group">
      <label>Budget</label>
      <select id="ai-budget">
        <option value="">Any</option>
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
    </div>
    <div class="form-group">
      <label>Count</label>
      <input type="number" id="ai-count" value="20" min="5" max="50" style="width:70px">
    </div>
    <div class="form-group">
      <label>Theme (optional)</label>
      <input type="text" id="ai-theme" placeholder="e.g. TikTok viral, summer..." style="width:180px">
    </div>
    <button onclick="generateAI()" class="btn">Generate</button>
  </div>
</div>

<div class="section">
  <h3>Curated Packs</h3>
  <div class="pack-grid">{pack_cards}</div>
</div>

<script>
const showResult = (msg, ok) => {{
  const r = document.getElementById('result');
  r.style.display = 'block';
  r.style.color = ok ? '#4CAF50' : '#E83858';
  r.textContent = msg;
}};

async function installPack(name) {{
  showResult('Installing pack...', true);
  const res = await fetch('/admin/seeder/install-pack?pack_name=' + name, {{method:'POST'}});
  const data = await res.json();
  showResult(`Pack "${{name}}": ${{data.inserted}} ideas inserted, ${{data.skipped_duplicates}} duplicates skipped`, true);
}}

async function installAll() {{
  showResult('Installing all packs...', true);
  const res = await fetch('/admin/seeder/install-all-packs', {{method:'POST'}});
  const data = await res.json();
  showResult(`All packs installed: ${{data.total_inserted}} total ideas added`, true);
}}

async function fillGaps() {{
  showResult('Analyzing gaps and generating...', true);
  const res = await fetch('/admin/seeder/fill-gaps', {{method:'POST'}});
  const data = await res.json();
  if (data.gaps_found) {{
    showResult(`Filled gaps in: ${{data.gaps_found.join(', ')}}. ${{data.total_inserted}} ideas added.`, true);
  }} else {{
    showResult(data.message || 'No gaps found!', true);
  }}
}}

async function generateAI() {{
  const cat = document.getElementById('ai-cat').value;
  const budget = document.getElementById('ai-budget').value;
  const count = document.getElementById('ai-count').value;
  const theme = document.getElementById('ai-theme').value;

  let url = `/admin/seeder/generate-ai?count=${{count}}`;
  if (cat) url += `&category=${{cat}}`;
  if (budget) url += `&budget=${{budget}}`;
  if (theme) url += `&theme=${{encodeURIComponent(theme)}}`;

  showResult('Generating with AI...', true);
  const res = await fetch(url, {{method:'POST'}});
  const data = await res.json();
  showResult(`Generated ${{data.generated}} ideas, inserted ${{data.inserted}}, skipped ${{data.skipped_duplicates}} duplicates`, true);
}}

async function refreshGaps() {{
  showResult('Analyzing...', true);
  const res = await fetch('/admin/seeder/gaps');
  const data = await res.json();
  showResult(`Total: ${{data.total_ideas}} ideas across ${{Object.keys(data.category_distribution).length}} categories. Under-represented: ${{data.under_represented_categories.join(', ') || 'none'}}`, true);
}}
</script>
</body></html>"""

    return HTMLResponse(content=html)
