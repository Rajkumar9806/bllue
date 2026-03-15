"""
Arrow Date Memory Journal System
Allows users to record and reflect on their dates with ratings, moods, photos, and milestones
"""
from fastapi import APIRouter, HTTPException, Query, Header, Depends
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# Global db_pool reference (injected from main.py)
db_pool: Optional[asyncpg.Pool] = None

def set_db_pool(pool: asyncpg.Pool):
    """Set the database pool (called from main.py on startup)"""
    global db_pool
    db_pool = pool


# ==================== SCHEMAS ====================

class JournalEntryCreate(BaseModel):
    """Create a new journal entry"""
    title: str = Field(..., min_length=1, max_length=255)
    date_date: datetime
    rating: Optional[int] = Field(None, ge=1, le=5)
    mood: Optional[str] = None  # amazing, fun, romantic, okay, meh
    notes: Optional[str] = None
    highlights: Optional[str] = None
    would_repeat: Optional[bool] = True
    total_cost: Optional[float] = None
    location_name: Optional[str] = None
    photos: Optional[List[str]] = []  # Array of photo URLs
    tags: Optional[List[str]] = []
    planned_date_id: Optional[str] = None


class JournalEntryUpdate(BaseModel):
    """Update a journal entry"""
    title: Optional[str] = None
    date_date: Optional[datetime] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    mood: Optional[str] = None
    notes: Optional[str] = None
    highlights: Optional[str] = None
    would_repeat: Optional[bool] = None
    total_cost: Optional[float] = None
    location_name: Optional[str] = None
    photos: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class JournalEntryResponse(BaseModel):
    """Response model for a journal entry"""
    id: str
    user_id: str
    planned_date_id: Optional[str]
    title: str
    date_date: datetime
    rating: Optional[int]
    mood: Optional[str]
    notes: Optional[str]
    highlights: Optional[str]
    would_repeat: bool
    total_cost: Optional[float]
    location_name: Optional[str]
    photos: List[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime


class DateMilestoneResponse(BaseModel):
    """Response model for a milestone"""
    id: str
    user_id: str
    milestone_type: str
    milestone_name: str
    milestone_description: Optional[str]
    achieved_at: datetime


class DateStatsResponse(BaseModel):
    """Comprehensive date statistics"""
    total_dates_completed: int
    average_rating: Optional[float]
    most_common_mood: Optional[str]
    total_money_spent: float
    average_cost_per_date: float
    favorite_category: Optional[str]
    dates_per_week: float
    longest_streak_weeks: int
    rating_trend: Optional[str]  # improving, declining, stable
    mood_distribution: Dict[str, int]
    category_distribution: Dict[str, int]


class TimelineEntry(BaseModel):
    """Entry for timeline view"""
    month: str  # YYYY-MM format
    total_dates: int
    average_rating: Optional[float]
    top_mood: Optional[str]
    total_spent: float
    entries: List[JournalEntryResponse]


class OnThisDayResponse(BaseModel):
    """Response for on-this-day feature"""
    year_ago: int
    message: str
    entries: List[JournalEntryResponse]


router = APIRouter(prefix="/api/journal", tags=["journal"])


# ==================== DATABASE INITIALIZATION ====================

async def init_journal_tables():
    """Create the journal tables if they don't exist"""
    if not db_pool:
        logger.error("Database pool not initialized")
        return

    async with db_pool.acquire() as conn:
        # Create date_memories table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS date_memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                planned_date_id UUID REFERENCES planned_dates(id) ON DELETE SET NULL,
                title VARCHAR(255) NOT NULL,
                date_date TIMESTAMP NOT NULL,
                rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                mood VARCHAR(50),
                notes TEXT,
                highlights TEXT,
                would_repeat BOOLEAN DEFAULT TRUE,
                total_cost DECIMAL(10,2),
                location_name VARCHAR(255),
                photos TEXT[],
                tags TEXT[],
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        ''')

        # Create index for user_id and date_date for efficient querying
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_date_memories_user_id
            ON date_memories(user_id);
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_date_memories_user_date
            ON date_memories(user_id, date_date DESC);
        ''')

        # Create date_milestones table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS date_milestones (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                milestone_type VARCHAR(50) NOT NULL,
                milestone_name VARCHAR(255) NOT NULL,
                milestone_description TEXT,
                achieved_at TIMESTAMP DEFAULT NOW()
            );
        ''')

        # Create index for user_id
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_date_milestones_user_id
            ON date_milestones(user_id);
        ''')

        # Create unique index to prevent duplicate milestones per user
        await conn.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_date_milestones_user_type
            ON date_milestones(user_id, milestone_type);
        ''')

        logger.info("Journal tables initialized successfully")


# ==================== MILESTONE LOGIC ====================

async def check_and_award_milestones(user_id: str, conn: asyncpg.Connection):
    """Check all milestone conditions and award any new ones"""
    try:
        milestones_to_check = [
            ("first_date", "First Date", "Created your first journal entry"),
            ("regular_dater", "Regular Dater", "Completed 5 dates"),
            ("date_night_pro", "Date Night Pro", "Completed 10 dates"),
            ("half_century", "Half Century", "Completed 50 dates"),
            ("five_stars", "Five Stars", "Earned your first 5-star date"),
            ("adventurer", "Adventurer", "Completed 3 adventure dates"),
            ("foodie_couple", "Foodie Couple", "Completed 3 foodie dates"),
            ("creative_souls", "Creative Souls", "Completed 3 creative dates"),
            ("budget_friendly", "Budget Friendly", "Completed 5 dates under $30"),
            ("big_spender", "Big Spender", "Completed a date over $200"),
            ("streak_week", "Streak Week", "Dated in 3 consecutive weeks"),
            ("anniversary", "Anniversary", "Logged a date on an occasion date"),
        ]

        for milestone_type, milestone_name, description in milestones_to_check:
            # Check if already awarded
            existing = await conn.fetchval(
                'SELECT id FROM date_milestones WHERE user_id = $1 AND milestone_type = $2',
                user_id, milestone_type
            )

            if existing:
                continue  # Already awarded

            # Check conditions
            award = False

            if milestone_type == "first_date":
                count = await conn.fetchval(
                    'SELECT COUNT(*) FROM date_memories WHERE user_id = $1',
                    user_id
                )
                award = count == 1

            elif milestone_type == "regular_dater":
                count = await conn.fetchval(
                    'SELECT COUNT(*) FROM date_memories WHERE user_id = $1',
                    user_id
                )
                award = count == 5

            elif milestone_type == "date_night_pro":
                count = await conn.fetchval(
                    'SELECT COUNT(*) FROM date_memories WHERE user_id = $1',
                    user_id
                )
                award = count == 10

            elif milestone_type == "half_century":
                count = await conn.fetchval(
                    'SELECT COUNT(*) FROM date_memories WHERE user_id = $1',
                    user_id
                )
                award = count == 50

            elif milestone_type == "five_stars":
                has_five_star = await conn.fetchval(
                    'SELECT COUNT(*) FROM date_memories WHERE user_id = $1 AND rating = 5',
                    user_id
                )
                award = has_five_star > 0

            elif milestone_type == "adventurer":
                count = await conn.fetchval(
                    '''SELECT COUNT(*) FROM date_memories dm
                    LEFT JOIN planned_dates pd ON dm.planned_date_id = pd.id
                    LEFT JOIN date_ideas di ON pd.date_idea_id = di.id
                    WHERE dm.user_id = $1 AND (di.category = $2 OR dm.tags @> $3)''',
                    user_id, "adventure", ["adventure"]
                )
                award = count >= 3

            elif milestone_type == "foodie_couple":
                count = await conn.fetchval(
                    '''SELECT COUNT(*) FROM date_memories dm
                    LEFT JOIN planned_dates pd ON dm.planned_date_id = pd.id
                    LEFT JOIN date_ideas di ON pd.date_idea_id = di.id
                    WHERE dm.user_id = $1 AND (di.category = $2 OR dm.tags @> $3)''',
                    user_id, "foodie", ["foodie"]
                )
                award = count >= 3

            elif milestone_type == "creative_souls":
                count = await conn.fetchval(
                    '''SELECT COUNT(*) FROM date_memories dm
                    LEFT JOIN planned_dates pd ON dm.planned_date_id = pd.id
                    LEFT JOIN date_ideas di ON pd.date_idea_id = di.id
                    WHERE dm.user_id = $1 AND (di.category = $2 OR dm.tags @> $3)''',
                    user_id, "creative", ["creative"]
                )
                award = count >= 3

            elif milestone_type == "budget_friendly":
                count = await conn.fetchval(
                    '''SELECT COUNT(*) FROM date_memories
                    WHERE user_id = $1 AND (total_cost IS NULL OR total_cost < 30)''',
                    user_id
                )
                award = count >= 5

            elif milestone_type == "big_spender":
                has_expensive = await conn.fetchval(
                    'SELECT COUNT(*) FROM date_memories WHERE user_id = $1 AND total_cost > 200',
                    user_id
                )
                award = has_expensive > 0

            elif milestone_type == "streak_week":
                # Check for 3 consecutive weeks with at least one date each
                dates = await conn.fetch(
                    '''SELECT DISTINCT DATE_TRUNC('week', date_date) as week
                    FROM date_memories WHERE user_id = $1
                    ORDER BY week DESC LIMIT 10''',
                    user_id
                )
                if len(dates) >= 3:
                    # Check if the last 3 are consecutive
                    consecutive = 0
                    current_week = None
                    for row in dates:
                        week = row['week']
                        if current_week is None:
                            current_week = week
                            consecutive = 1
                        elif week == current_week - timedelta(weeks=consecutive):
                            consecutive += 1
                        else:
                            break
                    award = consecutive >= 3

            elif milestone_type == "anniversary":
                # Check if a date memory matches an occasion date
                has_match = await conn.fetchval(
                    '''SELECT COUNT(*) FROM date_memories dm
                    JOIN occasions o ON dm.user_id = o.user_id
                    WHERE dm.user_id = $1
                    AND DATE(dm.date_date) = DATE(o.date)''',
                    user_id
                )
                award = has_match > 0

            # Award the milestone if condition is met
            if award:
                try:
                    await conn.execute(
                        '''INSERT INTO date_milestones
                        (user_id, milestone_type, milestone_name, milestone_description)
                        VALUES ($1, $2, $3, $4)''',
                        user_id, milestone_type, milestone_name, description
                    )
                    logger.info(f"Awarded milestone '{milestone_name}' to user {user_id}")
                except asyncpg.UniqueViolationError:
                    # Already awarded (race condition)
                    pass

    except Exception as e:
        logger.error(f"Error checking milestones for user {user_id}: {str(e)}")


# ==================== ENDPOINTS ====================

async def get_current_user_from_header(authorization: str = Header(None)) -> str:
    """Extract user_id from authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    # This would normally verify the token, but we'll use the pattern from main.py
    # For now, just pass through - the actual token verification happens in main.py
    return authorization


@router.post("/entry", response_model=JournalEntryResponse)
async def create_journal_entry(
    entry: JournalEntryCreate,
    user_id: str = Depends(lambda auth=Header(None): auth.replace("Bearer ", "") if auth else None)
):
    """Create a new journal entry"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract actual user_id from token - this is a simplified version
    # In production, you'd verify the JWT token properly
    # For now, we'll use a pattern where the token contains the user_id
    try:
        from main import verify_token
        # Try to parse the authorization header properly
        if user_id.startswith("Bearer "):
            user_id = user_id.replace("Bearer ", "")
        token_data = verify_token(user_id)
        user_id = token_data.user_id
    except:
        # If token verification fails in this context, use the passed user_id
        if not user_id or user_id.startswith("Bearer"):
            raise HTTPException(status_code=401, detail="Invalid token")

    entry_id = str(uuid.uuid4())

    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Create the journal entry
                await conn.execute(
                    '''INSERT INTO date_memories
                    (id, user_id, planned_date_id, title, date_date, rating, mood,
                     notes, highlights, would_repeat, total_cost, location_name, photos, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)''',
                    entry_id, user_id, entry.planned_date_id, entry.title, entry.date_date,
                    entry.rating, entry.mood, entry.notes, entry.highlights,
                    entry.would_repeat, entry.total_cost, entry.location_name,
                    entry.photos or [], entry.tags or []
                )

                # Check and award milestones
                await check_and_award_milestones(user_id, conn)

        # Fetch and return the created entry
        return await get_journal_entry_by_id(entry_id, user_id)

    except Exception as e:
        logger.error(f"Error creating journal entry: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create journal entry")


async def get_journal_entry_by_id(entry_id: str, user_id: str) -> JournalEntryResponse:
    """Helper to fetch a journal entry by ID"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            '''SELECT * FROM date_memories
            WHERE id = $1 AND user_id = $2''',
            entry_id, user_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    return JournalEntryResponse(
        id=str(row['id']),
        user_id=str(row['user_id']),
        planned_date_id=str(row['planned_date_id']) if row['planned_date_id'] else None,
        title=row['title'],
        date_date=row['date_date'],
        rating=row['rating'],
        mood=row['mood'],
        notes=row['notes'],
        highlights=row['highlights'],
        would_repeat=row['would_repeat'],
        total_cost=float(row['total_cost']) if row['total_cost'] else None,
        location_name=row['location_name'],
        photos=list(row['photos']) if row['photos'] else [],
        tags=list(row['tags']) if row['tags'] else [],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )


@router.get("/entries", response_model=List[JournalEntryResponse])
async def get_journal_entries(
    rating_min: Optional[int] = Query(None, ge=1, le=5),
    rating_max: Optional[int] = Query(None, ge=1, le=5),
    mood: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    authorization: str = Header(None)
):
    """Get all journal entries for user with optional filters"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    offset = (page - 1) * per_page
    query = "SELECT * FROM date_memories WHERE user_id = $1"
    params = [user_id]

    if rating_min is not None:
        query += f" AND rating >= ${len(params) + 1}"
        params.append(rating_min)

    if rating_max is not None:
        query += f" AND rating <= ${len(params) + 1}"
        params.append(rating_max)

    if mood:
        query += f" AND mood = ${len(params) + 1}"
        params.append(mood)

    if tag:
        query += f" AND tags @> ${len(params) + 1}"
        params.append([tag])

    query += f" ORDER BY date_date DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
    params.extend([per_page, offset])

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [
        JournalEntryResponse(
            id=str(row['id']),
            user_id=str(row['user_id']),
            planned_date_id=str(row['planned_date_id']) if row['planned_date_id'] else None,
            title=row['title'],
            date_date=row['date_date'],
            rating=row['rating'],
            mood=row['mood'],
            notes=row['notes'],
            highlights=row['highlights'],
            would_repeat=row['would_repeat'],
            total_cost=float(row['total_cost']) if row['total_cost'] else None,
            location_name=row['location_name'],
            photos=list(row['photos']) if row['photos'] else [],
            tags=list(row['tags']) if row['tags'] else [],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        for row in rows
    ]


@router.get("/entry/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: str,
    authorization: str = Header(None)
):
    """Get a single journal entry by ID"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            '''SELECT * FROM date_memories
            WHERE id = $1 AND user_id = $2''',
            entry_id, user_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    return JournalEntryResponse(
        id=str(row['id']),
        user_id=str(row['user_id']),
        planned_date_id=str(row['planned_date_id']) if row['planned_date_id'] else None,
        title=row['title'],
        date_date=row['date_date'],
        rating=row['rating'],
        mood=row['mood'],
        notes=row['notes'],
        highlights=row['highlights'],
        would_repeat=row['would_repeat'],
        total_cost=float(row['total_cost']) if row['total_cost'] else None,
        location_name=row['location_name'],
        photos=list(row['photos']) if row['photos'] else [],
        tags=list(row['tags']) if row['tags'] else [],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )


@router.put("/entry/{entry_id}", response_model=JournalEntryResponse)
async def update_journal_entry(
    entry_id: str,
    update: JournalEntryUpdate,
    authorization: str = Header(None)
):
    """Update a journal entry"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify entry exists and belongs to user
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            'SELECT * FROM date_memories WHERE id = $1 AND user_id = $2',
            entry_id, user_id
        )

    if not existing:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    # Build update query dynamically
    update_fields = []
    update_values = []
    param_index = 1

    if update.title is not None:
        update_fields.append(f"title = ${param_index}")
        update_values.append(update.title)
        param_index += 1

    if update.date_date is not None:
        update_fields.append(f"date_date = ${param_index}")
        update_values.append(update.date_date)
        param_index += 1

    if update.rating is not None:
        update_fields.append(f"rating = ${param_index}")
        update_values.append(update.rating)
        param_index += 1

    if update.mood is not None:
        update_fields.append(f"mood = ${param_index}")
        update_values.append(update.mood)
        param_index += 1

    if update.notes is not None:
        update_fields.append(f"notes = ${param_index}")
        update_values.append(update.notes)
        param_index += 1

    if update.highlights is not None:
        update_fields.append(f"highlights = ${param_index}")
        update_values.append(update.highlights)
        param_index += 1

    if update.would_repeat is not None:
        update_fields.append(f"would_repeat = ${param_index}")
        update_values.append(update.would_repeat)
        param_index += 1

    if update.total_cost is not None:
        update_fields.append(f"total_cost = ${param_index}")
        update_values.append(update.total_cost)
        param_index += 1

    if update.location_name is not None:
        update_fields.append(f"location_name = ${param_index}")
        update_values.append(update.location_name)
        param_index += 1

    if update.photos is not None:
        update_fields.append(f"photos = ${param_index}")
        update_values.append(update.photos)
        param_index += 1

    if update.tags is not None:
        update_fields.append(f"tags = ${param_index}")
        update_values.append(update.tags)
        param_index += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_fields.append(f"updated_at = NOW()")

    try:
        query = f"UPDATE date_memories SET {', '.join(update_fields)} WHERE id = $1"
        update_values.append(entry_id)

        async with db_pool.acquire() as conn:
            await conn.execute(query, *update_values)

        return await get_journal_entry_by_id(entry_id, user_id)

    except Exception as e:
        logger.error(f"Error updating journal entry: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update journal entry")


@router.delete("/entry/{entry_id}")
async def delete_journal_entry(
    entry_id: str,
    authorization: str = Header(None)
):
    """Delete a journal entry"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                '''DELETE FROM date_memories
                WHERE id = $1 AND user_id = $2''',
                entry_id, user_id
            )

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Journal entry not found")

        return {"message": "Journal entry deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting journal entry: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete journal entry")


@router.get("/timeline", response_model=List[TimelineEntry])
async def get_timeline(
    authorization: str = Header(None)
):
    """Get timeline view grouped by month with monthly stats"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with db_pool.acquire() as conn:
        # Get monthly stats
        monthly_stats = await conn.fetch(
            '''SELECT
                TO_CHAR(date_date, 'YYYY-MM') as month,
                COUNT(*) as total_dates,
                AVG(rating)::float as average_rating,
                MODE() WITHIN GROUP (ORDER BY mood) as top_mood,
                COALESCE(SUM(total_cost), 0)::float as total_spent
            FROM date_memories
            WHERE user_id = $1
            GROUP BY TO_CHAR(date_date, 'YYYY-MM')
            ORDER BY month DESC''',
            user_id
        )

        timeline_entries = []
        for stat in monthly_stats:
            # Get all entries for this month
            entries = await conn.fetch(
                '''SELECT * FROM date_memories
                WHERE user_id = $1
                AND TO_CHAR(date_date, 'YYYY-MM') = $2
                ORDER BY date_date DESC''',
                user_id, stat['month']
            )

            entry_models = [
                JournalEntryResponse(
                    id=str(row['id']),
                    user_id=str(row['user_id']),
                    planned_date_id=str(row['planned_date_id']) if row['planned_date_id'] else None,
                    title=row['title'],
                    date_date=row['date_date'],
                    rating=row['rating'],
                    mood=row['mood'],
                    notes=row['notes'],
                    highlights=row['highlights'],
                    would_repeat=row['would_repeat'],
                    total_cost=float(row['total_cost']) if row['total_cost'] else None,
                    location_name=row['location_name'],
                    photos=list(row['photos']) if row['photos'] else [],
                    tags=list(row['tags']) if row['tags'] else [],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in entries
            ]

            timeline_entries.append(TimelineEntry(
                month=stat['month'],
                total_dates=stat['total_dates'],
                average_rating=stat['average_rating'],
                top_mood=stat['top_mood'],
                total_spent=stat['total_spent'],
                entries=entry_models
            ))

    return timeline_entries


@router.get("/on-this-day", response_model=OnThisDayResponse)
async def get_on_this_day(
    authorization: str = Header(None)
):
    """Get journal entries from the same date in previous years"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    today = datetime.now()
    month_day = today.strftime("%m-%d")

    async with db_pool.acquire() as conn:
        # Find entries from same month/day in previous years
        entries = await conn.fetch(
            '''SELECT * FROM date_memories
            WHERE user_id = $1
            AND TO_CHAR(date_date, 'MM-DD') = $2
            AND EXTRACT(YEAR FROM date_date) < EXTRACT(YEAR FROM NOW())
            ORDER BY date_date DESC''',
            user_id, month_day
        )

    if not entries:
        return OnThisDayResponse(
            year_ago=0,
            message="No memories on this day from previous years",
            entries=[]
        )

    # Calculate how many years ago the most recent one was
    most_recent = entries[0]
    year_diff = today.year - most_recent['date_date'].year

    entry_models = [
        JournalEntryResponse(
            id=str(row['id']),
            user_id=str(row['user_id']),
            planned_date_id=str(row['planned_date_id']) if row['planned_date_id'] else None,
            title=row['title'],
            date_date=row['date_date'],
            rating=row['rating'],
            mood=row['mood'],
            notes=row['notes'],
            highlights=row['highlights'],
            would_repeat=row['would_repeat'],
            total_cost=float(row['total_cost']) if row['total_cost'] else None,
            location_name=row['location_name'],
            photos=list(row['photos']) if row['photos'] else [],
            tags=list(row['tags']) if row['tags'] else [],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        for row in entries
    ]

    message = f"{year_diff} year{'s' if year_diff != 1 else ''} ago, you {entry_models[0].highlights or entry_models[0].title.lower()}!"

    return OnThisDayResponse(
        year_ago=year_diff,
        message=message,
        entries=entry_models
    )


@router.get("/stats", response_model=DateStatsResponse)
async def get_date_stats(
    authorization: str = Header(None)
):
    """Get comprehensive date statistics dashboard"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with db_pool.acquire() as conn:
        # Total dates completed
        total_dates = await conn.fetchval(
            'SELECT COUNT(*) FROM date_memories WHERE user_id = $1',
            user_id
        )

        # Average rating
        avg_rating = await conn.fetchval(
            'SELECT AVG(rating)::float FROM date_memories WHERE user_id = $1',
            user_id
        )

        # Most common mood
        most_common_mood = await conn.fetchval(
            '''SELECT mood FROM date_memories
            WHERE user_id = $1 AND mood IS NOT NULL
            GROUP BY mood ORDER BY COUNT(*) DESC LIMIT 1''',
            user_id
        )

        # Total and average spending
        total_spent = await conn.fetchval(
            'SELECT COALESCE(SUM(total_cost), 0)::float FROM date_memories WHERE user_id = $1',
            user_id
        )

        avg_cost = await conn.fetchval(
            '''SELECT COALESCE(AVG(total_cost), 0)::float FROM date_memories
            WHERE user_id = $1 AND total_cost IS NOT NULL''',
            user_id
        )

        # Favorite category (from linked date ideas)
        favorite_category = await conn.fetchval(
            '''SELECT di.category FROM date_memories dm
            LEFT JOIN planned_dates pd ON dm.planned_date_id = pd.id
            LEFT JOIN date_ideas di ON pd.date_idea_id = di.id
            WHERE dm.user_id = $1 AND di.category IS NOT NULL
            GROUP BY di.category ORDER BY COUNT(*) DESC LIMIT 1''',
            user_id
        )

        # Date frequency (per week)
        first_date = await conn.fetchval(
            'SELECT MIN(date_date) FROM date_memories WHERE user_id = $1',
            user_id
        )

        dates_per_week = 0.0
        if first_date and total_dates > 0:
            weeks_since_first = (datetime.now() - first_date).days / 7
            if weeks_since_first > 0:
                dates_per_week = total_dates / weeks_since_first

        # Longest streak (consecutive weeks with a date)
        longest_streak = await _calculate_longest_streak(conn, user_id)

        # Rating trend
        rating_trend = await _calculate_rating_trend(conn, user_id)

        # Mood distribution
        mood_dist = await conn.fetch(
            '''SELECT mood, COUNT(*) as count FROM date_memories
            WHERE user_id = $1 AND mood IS NOT NULL
            GROUP BY mood''',
            user_id
        )
        mood_distribution = {row['mood']: row['count'] for row in mood_dist}

        # Category distribution
        cat_dist = await conn.fetch(
            '''SELECT di.category, COUNT(*) as count FROM date_memories dm
            LEFT JOIN planned_dates pd ON dm.planned_date_id = pd.id
            LEFT JOIN date_ideas di ON pd.date_idea_id = di.id
            WHERE dm.user_id = $1 AND di.category IS NOT NULL
            GROUP BY di.category''',
            user_id
        )
        category_distribution = {row['category']: row['count'] for row in cat_dist}

    return DateStatsResponse(
        total_dates_completed=total_dates or 0,
        average_rating=avg_rating,
        most_common_mood=most_common_mood,
        total_money_spent=total_spent or 0.0,
        average_cost_per_date=avg_cost or 0.0,
        favorite_category=favorite_category,
        dates_per_week=dates_per_week,
        longest_streak_weeks=longest_streak,
        rating_trend=rating_trend,
        mood_distribution=mood_distribution,
        category_distribution=category_distribution
    )


async def _calculate_longest_streak(conn: asyncpg.Connection, user_id: str) -> int:
    """Calculate longest consecutive weeks with at least one date"""
    weeks = await conn.fetch(
        '''SELECT DISTINCT DATE_TRUNC('week', date_date) as week
        FROM date_memories WHERE user_id = $1
        ORDER BY week DESC''',
        user_id
    )

    if not weeks:
        return 0

    longest = 1
    current = 1

    for i in range(1, len(weeks)):
        prev_week = weeks[i - 1]['week']
        curr_week = weeks[i]['week']

        # Check if weeks are consecutive
        if (prev_week - curr_week).days == 7:
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    return longest


async def _calculate_rating_trend(conn: asyncpg.Connection, user_id: str) -> Optional[str]:
    """Calculate if rating trend is improving, declining, or stable"""
    ratings = await conn.fetch(
        '''SELECT rating FROM date_memories
        WHERE user_id = $1 AND rating IS NOT NULL
        ORDER BY date_date DESC LIMIT 10''',
        user_id
    )

    if len(ratings) < 2:
        return None

    first_half_avg = sum(r['rating'] for r in ratings[:5]) / 5
    second_half_avg = sum(r['rating'] for r in ratings[5:]) / len(ratings[5:])

    if first_half_avg > second_half_avg + 0.5:
        return "improving"
    elif first_half_avg < second_half_avg - 0.5:
        return "declining"
    else:
        return "stable"


@router.get("/milestones", response_model=List[DateMilestoneResponse])
async def get_milestones(
    authorization: str = Header(None)
):
    """Get earned milestones/badges for user"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        from main import verify_token
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        user_id = token_data.user_id
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            '''SELECT * FROM date_milestones
            WHERE user_id = $1
            ORDER BY achieved_at DESC''',
            user_id
        )

    return [
        DateMilestoneResponse(
            id=str(row['id']),
            user_id=str(row['user_id']),
            milestone_type=row['milestone_type'],
            milestone_name=row['milestone_name'],
            milestone_description=row['milestone_description'],
            achieved_at=row['achieved_at']
        )
        for row in rows
    ]
