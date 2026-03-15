"""
Arrow Live Events & Multi-Source Idea Scraper

Fetches real-time date ideas from multiple sources:
1. Live Events — Concerts, festivals, shows (Ticketmaster, Eventbrite APIs)
2. Social Media Trends — TikTok, Instagram trending date ideas via AI
3. Local Happenings — Farmers markets, pop-ups, food festivals
4. Seasonal Events — Holiday markets, outdoor movie nights, etc.
5. Retail Partner Events — Partner-hosted events with boosting

All ideas go through image validation — stock images auto-flagged for review.
"""

from fastapi import APIRouter, HTTPException, Query
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import json
import logging
import httpx
import os

logger = logging.getLogger(__name__)

db_pool: Optional[asyncpg.Pool] = None
router = APIRouter()

# API Keys
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "")
EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_API_KEY", "")

# Stock image domains (for detection)
STOCK_DOMAINS = [
    'unsplash.com', 'pexels.com', 'pixabay.com', 'shutterstock.com',
    'istockphoto.com', 'gettyimages.com', 'stock.adobe.com', 'dreamstime.com',
    'depositphotos.com', '123rf.com', 'freepik.com', 'stocksy.com',
    'alamy.com', 'bigstockphoto.com', 'canstockphoto.com',
]

# Nashville default coordinates
NASHVILLE_LAT = 36.1627
NASHVILLE_LON = -86.7816

# City configs (expandable)
CITY_CONFIGS = {
    "Nashville": {"lat": 36.1627, "lon": -86.7816, "tm_market": "Nashville", "state": "TN", "dma_id": "659"},
    "Austin": {"lat": 30.2672, "lon": -97.7431, "tm_market": "Austin", "state": "TX", "dma_id": "635"},
    "Denver": {"lat": 39.7392, "lon": -104.9903, "tm_market": "Denver", "state": "CO", "dma_id": "751"},
}


def set_db_pool(pool: asyncpg.Pool):
    global db_pool
    db_pool = pool


def is_stock_image(url: str) -> bool:
    """Check if URL is from a stock image provider."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in STOCK_DOMAINS)


# ==================== TABLE INIT ====================

async def init_events_tables():
    """Initialize events tables."""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS live_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                external_id VARCHAR(255),
                source VARCHAR(50) NOT NULL,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                venue_name VARCHAR(255),
                venue_address TEXT,
                city VARCHAR(100) DEFAULT 'Nashville',
                event_date TIMESTAMP,
                end_date TIMESTAMP,
                category VARCHAR(50),
                subcategory VARCHAR(100),
                budget VARCHAR(20),
                price_min NUMERIC(10,2),
                price_max NUMERIC(10,2),
                image_url TEXT,
                image_status VARCHAR(20) DEFAULT 'pending',
                ticket_url TEXT,
                tags TEXT[],
                is_date_friendly BOOLEAN DEFAULT TRUE,
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(external_id, source)
            )
        ''')

        # Source scrape log
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS scrape_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source VARCHAR(50) NOT NULL,
                city VARCHAR(100),
                status VARCHAR(20) DEFAULT 'running',
                events_found INTEGER DEFAULT 0,
                events_inserted INTEGER DEFAULT 0,
                events_flagged INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        ''')

    logger.info("Events tables initialized")


# ==================== TICKETMASTER INTEGRATION ====================

async def scrape_ticketmaster(city: str = "Nashville", days_ahead: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch events from Ticketmaster Discovery API.
    Returns concerts, shows, festivals, sports events.
    """
    if not TICKETMASTER_API_KEY:
        logger.warning("Ticketmaster API key not configured")
        return []

    config = CITY_CONFIGS.get(city, CITY_CONFIGS["Nashville"])
    start_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")

    events = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fetch multiple pages
            for page in range(3):  # Max 3 pages = ~60 events
                response = await client.get(
                    "https://app.ticketmaster.com/discovery/v2/events.json",
                    params={
                        "apikey": TICKETMASTER_API_KEY,
                        "dmaId": config.get("dma_id", "659"),
                        "startDateTime": start_date,
                        "endDateTime": end_date,
                        "size": 20,
                        "page": page,
                        "sort": "date,asc",
                        "classificationName": "Music,Arts & Theatre,Comedy,Sports"
                    }
                )

                if response.status_code != 200:
                    logger.warning(f"Ticketmaster API error: {response.status_code}")
                    break

                data = response.json()
                tm_events = data.get("_embedded", {}).get("events", [])

                if not tm_events:
                    break

                for ev in tm_events:
                    # Parse event
                    venue_info = ev.get("_embedded", {}).get("venues", [{}])[0]
                    price_info = ev.get("priceRanges", [{}])[0] if ev.get("priceRanges") else {}

                    # Get best image (prefer 16:9 ratio, large)
                    image_url = ""
                    for img in ev.get("images", []):
                        if img.get("ratio") == "16_9" and img.get("width", 0) >= 640:
                            image_url = img.get("url", "")
                            break
                    if not image_url and ev.get("images"):
                        image_url = ev["images"][0].get("url", "")

                    # Determine image status
                    img_status = "approved"  # Ticketmaster images are official event images
                    if is_stock_image(image_url):
                        img_status = "pending_review"

                    # Map category
                    classifications = ev.get("classifications", [{}])[0]
                    segment = classifications.get("segment", {}).get("name", "").lower()
                    genre = classifications.get("genre", {}).get("name", "")

                    category = _map_event_category(segment, genre)
                    budget = _estimate_budget(price_info.get("min"), price_info.get("max"))

                    # Build tags
                    tags = ["live-event", "ticketmaster", city.lower()]
                    if genre:
                        tags.append(genre.lower())
                    if segment:
                        tags.append(segment)
                    tags.append("date-night")

                    event_date = None
                    date_str = ev.get("dates", {}).get("start", {}).get("dateTime")
                    if date_str:
                        try:
                            event_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
                        except ValueError:
                            pass

                    events.append({
                        "external_id": ev.get("id", ""),
                        "source": "ticketmaster",
                        "title": ev.get("name", ""),
                        "description": f"Live event at {venue_info.get('name', 'TBD')}. {genre} experience perfect for a date night.",
                        "venue_name": venue_info.get("name", ""),
                        "venue_address": f"{venue_info.get('address', {}).get('line1', '')}, {venue_info.get('city', {}).get('name', city)}",
                        "city": city,
                        "event_date": event_date,
                        "category": category,
                        "subcategory": genre,
                        "budget": budget,
                        "price_min": price_info.get("min"),
                        "price_max": price_info.get("max"),
                        "image_url": image_url,
                        "image_status": img_status,
                        "ticket_url": ev.get("url", ""),
                        "tags": tags,
                        "is_date_friendly": True,
                        "metadata": json.dumps({
                            "segment": segment,
                            "genre": genre,
                            "promoter": ev.get("promoter", {}).get("name", ""),
                        })
                    })

    except Exception as e:
        logger.error(f"Ticketmaster scrape error: {e}")

    return events


# ==================== AI-POWERED SOCIAL MEDIA TRENDS ====================

async def scrape_social_trends(city: str = "Nashville", count: int = 15) -> List[Dict[str, Any]]:
    """
    Use AI to generate locally-relevant date ideas based on current social media trends.
    This replaces direct API calls to TikTok/Instagram (which require approved apps).
    """
    from ai_providers import get_ai_provider, clean_response_text

    prompt = f"""You are a local date night expert in {city}. Generate {count} date night ideas that are:

1. Currently trending on TikTok, Instagram Reels, and social media in 2026
2. Specific to {city} — use REAL restaurant names, REAL venue names, REAL neighborhoods
3. Include seasonal/current events happening NOW (March 2026)
4. Include local food scene, live music venues, and unique {city} experiences
5. Mix of free, budget, and splurge options

For each idea, explain WHY it's trending (viral video, influencer mention, seasonal popularity).

IMPORTANT: For image_url, use ONLY direct URLs from the venue's own website, Google Maps, or Yelp.
DO NOT use Unsplash, Pexels, Shutterstock, or any stock photo site.
If you don't have a real URL, leave image_url as empty string.

Return ONLY valid JSON array:
[
  {{
    "title": "Specific local date idea",
    "description": "Detailed description with real venue/location names in {city}",
    "venue_name": "Real venue name or empty string",
    "venue_address": "Real address or neighborhood",
    "category": "romantic|adventure|foodie|creative|relaxing|fun|cultural|active",
    "budget": "low|medium|high",
    "price_estimate": 45,
    "tags": ["trending", "tiktok", "local-gem", "specific-tags"],
    "image_url": "",
    "trending_source": "tiktok|instagram|local-buzz",
    "why_trending": "Brief explanation of why this is trending"
  }}
]"""

    try:
        # Get current AI provider from environment
        provider_name = os.getenv("AI_PROVIDER", "gemini")
        provider = get_ai_provider(provider_name)
        text = await provider.generate(prompt, temperature=0.95, max_tokens=4096)
        text = clean_response_text(text)
        ideas = json.loads(text)

        events = []
        for idea in ideas:
            img_url = idea.get("image_url", "")
            img_status = "needs_image"
            if img_url:
                if is_stock_image(img_url):
                    img_status = "pending_review"
                else:
                    img_status = "approved"

            events.append({
                "external_id": f"social-{uuid.uuid4().hex[:12]}",
                "source": f"social-{idea.get('trending_source', 'ai')}",
                "title": idea.get("title", ""),
                "description": idea.get("description", ""),
                "venue_name": idea.get("venue_name", ""),
                "venue_address": idea.get("venue_address", ""),
                "city": city,
                "event_date": None,  # Social trends don't have specific dates
                "category": idea.get("category", "fun"),
                "subcategory": idea.get("trending_source", ""),
                "budget": idea.get("budget", "medium"),
                "price_min": idea.get("price_estimate"),
                "price_max": idea.get("price_estimate"),
                "image_url": img_url,
                "image_status": img_status,
                "ticket_url": "",
                "tags": idea.get("tags", []) + [city.lower(), "social-trend"],
                "is_date_friendly": True,
                "metadata": json.dumps({
                    "why_trending": idea.get("why_trending", ""),
                    "trending_source": idea.get("trending_source", ""),
                })
            })

        return events

    except Exception as e:
        logger.error(f"Social trend scrape error: {e}")
        return []


# ==================== LOCAL SEASONAL EVENTS ====================

async def scrape_seasonal_local(city: str = "Nashville", count: int = 10) -> List[Dict[str, Any]]:
    """
    Use AI to generate seasonal/festive local event ideas.
    Covers: holiday events, festivals, seasonal pop-ups, farmers markets, etc.
    """
    from ai_providers import get_ai_provider, clean_response_text

    now = datetime.utcnow()
    month_name = now.strftime("%B")
    season = "spring" if now.month in [3, 4, 5] else "summer" if now.month in [6, 7, 8] else "fall" if now.month in [9, 10, 11] else "winter"

    prompt = f"""You are a local events expert for {city}. It's {month_name} 2026 ({season}).

Generate {count} REAL seasonal/festive date ideas for {city} right now:
- Local festivals, markets, and seasonal events happening in {month_name}
- Holiday-related activities (if applicable)
- Seasonal food & drink experiences
- Outdoor activities perfect for this time of year
- Community events, art walks, live music scenes

Use REAL venue and event names where possible. Be specific to {city} neighborhoods.

DO NOT use stock image URLs. Leave image_url empty if no real photo available.

Return ONLY valid JSON array:
[
  {{
    "title": "Specific seasonal event/idea",
    "description": "Detailed description with real locations",
    "venue_name": "Real venue or area name",
    "venue_address": "Neighborhood or address",
    "event_date": "2026-03-20" or null,
    "end_date": "2026-03-22" or null,
    "category": "romantic|adventure|foodie|creative|relaxing|fun|cultural|active",
    "budget": "low|medium|high",
    "tags": ["seasonal", "{season}", "local", "specific-tags"],
    "image_url": ""
  }}
]"""

    try:
        provider_name = os.getenv("AI_PROVIDER", "gemini")
        provider = get_ai_provider(provider_name)
        text = await provider.generate(prompt, temperature=0.9, max_tokens=3000)
        text = clean_response_text(text)
        ideas = json.loads(text)

        events = []
        for idea in ideas:
            img_url = idea.get("image_url", "")
            img_status = "needs_image" if not img_url else ("pending_review" if is_stock_image(img_url) else "approved")

            event_date = None
            if idea.get("event_date"):
                try:
                    event_date = datetime.strptime(idea["event_date"], "%Y-%m-%d")
                except (ValueError, TypeError):
                    pass

            events.append({
                "external_id": f"seasonal-{uuid.uuid4().hex[:12]}",
                "source": "seasonal-local",
                "title": idea.get("title", ""),
                "description": idea.get("description", ""),
                "venue_name": idea.get("venue_name", ""),
                "venue_address": idea.get("venue_address", ""),
                "city": city,
                "event_date": event_date,
                "category": idea.get("category", "fun"),
                "subcategory": season,
                "budget": idea.get("budget", "medium"),
                "price_min": None,
                "price_max": None,
                "image_url": img_url,
                "image_status": img_status,
                "ticket_url": "",
                "tags": idea.get("tags", []) + [city.lower()],
                "is_date_friendly": True,
                "metadata": json.dumps({"season": season, "month": month_name})
            })

        return events

    except Exception as e:
        logger.error(f"Seasonal scrape error: {e}")
        return []


# ==================== HELPERS ====================

def _map_event_category(segment: str, genre: str) -> str:
    """Map Ticketmaster segment/genre to Arrow category."""
    segment = segment.lower()
    genre = genre.lower()

    if "music" in segment or "concert" in genre:
        return "cultural"
    elif "comedy" in segment or "comedy" in genre:
        return "fun"
    elif "theatre" in segment or "theater" in segment:
        return "cultural"
    elif "sport" in segment:
        return "active"
    elif "art" in segment:
        return "creative"
    elif "food" in genre or "wine" in genre:
        return "foodie"
    elif "festival" in genre:
        return "adventure"
    return "fun"


def _estimate_budget(min_price: float = None, max_price: float = None) -> str:
    """Estimate budget level from price range (for 2 tickets)."""
    if min_price is None:
        return "medium"
    total = (min_price or 0) * 2  # Two tickets
    if total < 50:
        return "low"
    elif total < 150:
        return "medium"
    return "high"


# ==================== DB INSERTION WITH IMAGE VALIDATION ====================

async def insert_events_batch(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """Insert events with stock image detection. Returns counts."""
    inserted = 0
    flagged = 0
    skipped = 0

    async with db_pool.acquire() as conn:
        for event in events:
            try:
                # Check duplicate
                if event.get('external_id'):
                    exists = await conn.fetchval(
                        "SELECT COUNT(*) FROM live_events WHERE external_id = $1 AND source = $2",
                        event['external_id'], event['source']
                    )
                    if exists > 0:
                        skipped += 1
                        continue

                # Final image check
                img_url = event.get('image_url', '')
                img_status = event.get('image_status', 'needs_image')

                if img_url and is_stock_image(img_url):
                    img_status = "pending_review"
                    flagged += 1
                elif not img_url:
                    img_status = "needs_image"
                    flagged += 1

                await conn.execute('''
                    INSERT INTO live_events
                    (external_id, source, title, description, venue_name, venue_address,
                     city, event_date, category, subcategory, budget, price_min, price_max,
                     image_url, image_status, ticket_url, tags, is_date_friendly, metadata)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                    ON CONFLICT (external_id, source) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        event_date = EXCLUDED.event_date,
                        image_url = EXCLUDED.image_url,
                        updated_at = NOW()
                ''', event.get('external_id'), event['source'],
                    event['title'], event.get('description', ''),
                    event.get('venue_name', ''), event.get('venue_address', ''),
                    event.get('city', 'Nashville'), event.get('event_date'),
                    event.get('category', 'fun'), event.get('subcategory', ''),
                    event.get('budget', 'medium'),
                    event.get('price_min'), event.get('price_max'),
                    img_url, img_status,
                    event.get('ticket_url', ''),
                    event.get('tags', []),
                    event.get('is_date_friendly', True),
                    event.get('metadata', '{}'))
                inserted += 1

            except Exception as e:
                logger.warning(f"Failed to insert event '{event.get('title')}': {e}")

    return {"inserted": inserted, "flagged": flagged, "skipped": skipped}


# ==================== API ENDPOINTS ====================

@router.post("/admin/events/scrape/ticketmaster")
async def scrape_ticketmaster_endpoint(city: str = "Nashville", days_ahead: int = 30):
    """Scrape Ticketmaster for live events."""
    job_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO scrape_jobs (id, source, city, status) VALUES ($1, 'ticketmaster', $2, 'running')",
            job_id, city
        )

    events = await scrape_ticketmaster(city, days_ahead)
    result = await insert_events_batch(events)

    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE scrape_jobs SET status='completed', events_found=$1, events_inserted=$2,
            events_flagged=$3, completed_at=NOW() WHERE id=$4
        ''', len(events), result['inserted'], result['flagged'], job_id)

    return {"success": True, "source": "ticketmaster", "city": city, **result, "total_found": len(events)}


@router.post("/admin/events/scrape/social-trends")
async def scrape_social_endpoint(city: str = "Nashville", count: int = 15):
    """Generate social-trend-based local date ideas via AI."""
    job_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO scrape_jobs (id, source, city, status) VALUES ($1, 'social-trends', $2, 'running')",
            job_id, city
        )

    events = await scrape_social_trends(city, count)
    result = await insert_events_batch(events)

    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE scrape_jobs SET status='completed', events_found=$1, events_inserted=$2,
            events_flagged=$3, completed_at=NOW() WHERE id=$4
        ''', len(events), result['inserted'], result['flagged'], job_id)

    return {"success": True, "source": "social-trends", "city": city, **result}


@router.post("/admin/events/scrape/seasonal")
async def scrape_seasonal_endpoint(city: str = "Nashville", count: int = 10):
    """Generate seasonal/festive local event ideas via AI."""
    job_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO scrape_jobs (id, source, city, status) VALUES ($1, 'seasonal', $2, 'running')",
            job_id, city
        )

    events = await scrape_seasonal_local(city, count)
    result = await insert_events_batch(events)

    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE scrape_jobs SET status='completed', events_found=$1, events_inserted=$2,
            events_flagged=$3, completed_at=NOW() WHERE id=$4
        ''', len(events), result['inserted'], result['flagged'], job_id)

    return {"success": True, "source": "seasonal", "city": city, **result}


@router.post("/admin/events/scrape/all")
async def scrape_all_sources(city: str = "Nashville"):
    """Run all scrapers for a city."""
    results = {}

    # Ticketmaster
    tm_events = await scrape_ticketmaster(city)
    tm_result = await insert_events_batch(tm_events)
    results["ticketmaster"] = {"found": len(tm_events), **tm_result}

    # Social trends
    social_events = await scrape_social_trends(city)
    social_result = await insert_events_batch(social_events)
    results["social_trends"] = {"found": len(social_events), **social_result}

    # Seasonal
    seasonal_events = await scrape_seasonal_local(city)
    seasonal_result = await insert_events_batch(seasonal_events)
    results["seasonal"] = {"found": len(seasonal_events), **seasonal_result}

    total_inserted = sum(r['inserted'] for r in results.values())
    total_flagged = sum(r['flagged'] for r in results.values())

    return {
        "success": True,
        "city": city,
        "total_inserted": total_inserted,
        "total_flagged": total_flagged,
        "sources": results
    }


# ==================== USER-FACING ENDPOINTS ====================

@router.get("/api/events")
async def get_live_events(
    city: str = "Nashville",
    category: Optional[str] = None,
    budget: Optional[str] = None,
    source: Optional[str] = None,
    days_ahead: int = 14,
    limit: int = 20
):
    """Get live events and trending ideas for users."""
    now = datetime.utcnow()
    future = now + timedelta(days=days_ahead)

    query = """
        SELECT * FROM live_events
        WHERE city = $1 AND is_active = TRUE
          AND image_status = 'approved'
          AND (event_date IS NULL OR event_date >= $2)
          AND (event_date IS NULL OR event_date <= $3)
    """
    params: list = [city, now, future]
    idx = 3

    if category:
        idx += 1
        query += f" AND category = ${idx}"
        params.append(category)

    if budget:
        idx += 1
        query += f" AND budget = ${idx}"
        params.append(budget)

    if source:
        idx += 1
        query += f" AND source = ${idx}"
        params.append(source)

    query += " ORDER BY event_date ASC NULLS LAST"
    idx += 1
    query += f" LIMIT ${idx}"
    params.append(limit)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    events = []
    for row in rows:
        e = dict(row)
        e['id'] = str(e['id'])
        events.append(e)

    return {"events": events, "total": len(events), "city": city}


# ==================== IMAGE REVIEW FOR EVENTS ====================

@router.get("/admin/events/image-review")
async def get_event_image_review(limit: int = 50):
    """Get events with images needing review."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM live_events
            WHERE image_status IN ('pending_review', 'needs_image')
            ORDER BY created_at ASC LIMIT $1
        """, limit)

    items = [dict(row) for row in rows]
    for i in items:
        i['id'] = str(i['id'])
    return {"pending": items, "total": len(items)}


@router.post("/admin/events/{event_id}/approve-image")
async def approve_event_image(event_id: str):
    """Approve an event's image."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE live_events SET image_status = 'approved', updated_at = NOW() WHERE id = $1",
            uuid.UUID(event_id)
        )
    return {"success": True}


@router.post("/admin/events/{event_id}/update-image")
async def update_event_image(event_id: str, new_image_url: str):
    """Admin replaces an event's image and approves it."""
    if is_stock_image(new_image_url):
        raise HTTPException(status_code=400, detail="New URL is also a stock image")

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE live_events SET image_url = $1, image_status = 'approved', updated_at = NOW() WHERE id = $2",
            new_image_url, uuid.UUID(event_id)
        )
    return {"success": True, "message": "Image updated and approved"}


@router.post("/admin/events/{event_id}/reject-image")
async def reject_event_image(event_id: str):
    """Reject an event's image."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE live_events SET image_status = 'rejected', is_active = FALSE, updated_at = NOW() WHERE id = $1",
            uuid.UUID(event_id)
        )
    return {"success": True}


# ==================== SCRAPE JOB HISTORY ====================

@router.get("/admin/events/scrape-history")
async def get_scrape_history(limit: int = 20):
    """Get scrape job history."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM scrape_jobs ORDER BY started_at DESC LIMIT $1", limit
        )
    jobs = [dict(row) for row in rows]
    for j in jobs:
        j['id'] = str(j['id'])
    return {"jobs": jobs}


# ==================== STATS ====================

@router.get("/admin/events/stats")
async def get_events_stats(city: str = "Nashville"):
    """Get event database stats."""
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM live_events WHERE city = $1", city)
        approved = await conn.fetchval("SELECT COUNT(*) FROM live_events WHERE city = $1 AND image_status = 'approved'", city)
        pending = await conn.fetchval("SELECT COUNT(*) FROM live_events WHERE city = $1 AND image_status IN ('pending_review', 'needs_image')", city)
        by_source = await conn.fetch("SELECT source, COUNT(*) as count FROM live_events WHERE city = $1 GROUP BY source", city)
        by_cat = await conn.fetch("SELECT category, COUNT(*) as count FROM live_events WHERE city = $1 GROUP BY category ORDER BY count DESC", city)

    return {
        "city": city,
        "total_events": total,
        "approved": approved,
        "pending_review": pending,
        "by_source": {row['source']: row['count'] for row in by_source},
        "by_category": {row['category']: row['count'] for row in by_cat},
    }
