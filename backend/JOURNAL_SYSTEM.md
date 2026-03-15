# Date Memory Journal System - API Documentation

## Overview

The Date Memory Journal is a comprehensive system for tracking, reflecting on, and analyzing dates. Users can record detailed journal entries after dates, earn milestones/badges, view timeline visualizations, and access comprehensive statistics about their dating patterns.

## Database Schema

### `date_memories` Table
Primary table for storing journal entries.

```sql
CREATE TABLE date_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    planned_date_id UUID REFERENCES planned_dates(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    date_date TIMESTAMP NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    mood VARCHAR(50),  -- amazing, fun, romantic, okay, meh
    notes TEXT,
    highlights TEXT,  -- What was the best part?
    would_repeat BOOLEAN DEFAULT TRUE,
    total_cost DECIMAL(10,2),
    location_name VARCHAR(255),
    photos TEXT[],  -- Array of photo URLs
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes:**
- `idx_date_memories_user_id`: Fast lookup of user's entries
- `idx_date_memories_user_date`: Efficient date-based queries for one user

### `date_milestones` Table
Stores earned achievements/badges.

```sql
CREATE TABLE date_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    milestone_type VARCHAR(50) NOT NULL,
    milestone_name VARCHAR(255) NOT NULL,
    milestone_description TEXT,
    achieved_at TIMESTAMP DEFAULT NOW()
);
```

**Unique Index:**
- `idx_date_milestones_user_type`: Prevents duplicate milestones per user

## API Endpoints

### Create Journal Entry
**POST** `/api/journal/entry`

Creates a new journal entry and checks for new milestone achievements.

**Request Body:**
```json
{
  "title": "Amazing dinner at the new Italian place",
  "date_date": "2026-03-15T19:30:00Z",
  "rating": 5,
  "mood": "amazing",
  "notes": "The pasta was incredible",
  "highlights": "shared tiramisu for dessert",
  "would_repeat": true,
  "total_cost": 85.50,
  "location_name": "Marco's Italian Restaurant",
  "photos": [
    "https://s3.amazonaws.com/photos/date1.jpg",
    "https://s3.amazonaws.com/photos/date2.jpg"
  ],
  "tags": ["foodie", "romantic", "dinner"],
  "planned_date_id": "optional-uuid"
}
```

**Response:** `JournalEntryResponse` (201 Created)

---

### Get Journal Entries
**GET** `/api/journal/entries`

Retrieves all journal entries for the authenticated user with optional filtering and pagination.

**Query Parameters:**
- `rating_min` (optional, int): Minimum rating filter (1-5)
- `rating_max` (optional, int): Maximum rating filter (1-5)
- `mood` (optional, string): Filter by mood (amazing, fun, romantic, okay, meh)
- `tag` (optional, string): Filter by tag (returns entries with this tag)
- `page` (optional, int): Page number (default: 1)
- `per_page` (optional, int): Results per page (default: 20, max: 100)

**Response:** `List[JournalEntryResponse]` (200 OK)

**Examples:**
- GET `/api/journal/entries?rating_min=4` - High-rated dates
- GET `/api/journal/entries?mood=romantic&tag=adventure` - Romantic adventure dates
- GET `/api/journal/entries?page=2&per_page=10` - Pagination

---

### Get Single Entry
**GET** `/api/journal/entry/{entry_id}`

Retrieves a specific journal entry with full details.

**Path Parameters:**
- `entry_id`: UUID of the journal entry

**Response:** `JournalEntryResponse` (200 OK)

**Error Responses:**
- 404: Entry not found
- 401: Unauthorized

---

### Update Entry
**PUT** `/api/journal/entry/{entry_id}`

Updates an existing journal entry. All fields are optional.

**Request Body:**
```json
{
  "title": "Updated title",
  "rating": 4,
  "mood": "fun",
  "notes": "Updated notes",
  "photos": ["new-photo-url.jpg"],
  "tags": ["updated", "tags"]
}
```

**Response:** `JournalEntryResponse` (200 OK)

---

### Delete Entry
**DELETE** `/api/journal/entry/{entry_id}`

Deletes a journal entry permanently.

**Response:**
```json
{
  "message": "Journal entry deleted successfully"
}
```

**Error Responses:**
- 404: Entry not found
- 401: Unauthorized

---

### Get Timeline View
**GET** `/api/journal/timeline`

Returns entries grouped by month with monthly statistics for a beautiful timeline UI.

**Response:** `List[TimelineEntry]`

**Response Example:**
```json
[
  {
    "month": "2026-03",
    "total_dates": 4,
    "average_rating": 4.5,
    "top_mood": "amazing",
    "total_spent": 320.75,
    "entries": [
      {
        "id": "...",
        "title": "...",
        ...
      }
    ]
  },
  {
    "month": "2026-02",
    "total_dates": 3,
    "average_rating": 4.0,
    "top_mood": "fun",
    "total_spent": 215.50,
    "entries": [...]
  }
]
```

---

### "On This Day" Feature
**GET** `/api/journal/on-this-day`

Returns journal entries from the same date in previous years, like "On this day in 2024..."

**Response:** `OnThisDayResponse`

**Response Example:**
```json
{
  "year_ago": 2,
  "message": "2 years ago, you went stargazing!",
  "entries": [
    {
      "id": "...",
      "title": "Stargazing at the observatory",
      "date_date": "2024-03-15T20:00:00Z",
      ...
    }
  ]
}
```

---

### Get Date Statistics
**GET** `/api/journal/stats`

Comprehensive date statistics dashboard with trends and distributions.

**Response:** `DateStatsResponse`

**Response Example:**
```json
{
  "total_dates_completed": 47,
  "average_rating": 4.2,
  "most_common_mood": "amazing",
  "total_money_spent": 2847.50,
  "average_cost_per_date": 60.58,
  "favorite_category": "romantic",
  "dates_per_week": 1.2,
  "longest_streak_weeks": 5,
  "rating_trend": "improving",
  "mood_distribution": {
    "amazing": 15,
    "fun": 18,
    "romantic": 8,
    "okay": 5,
    "meh": 1
  },
  "category_distribution": {
    "romantic": 12,
    "adventure": 10,
    "foodie": 15,
    "creative": 8,
    "outdoor": 2
  }
}
```

**Stats Calculated:**
- `total_dates_completed`: Count of all journal entries
- `average_rating`: Average of all ratings
- `most_common_mood`: Most frequently selected mood
- `total_money_spent`: Sum of all total_cost fields
- `average_cost_per_date`: Average spending per date
- `favorite_category`: Most common category from linked date ideas
- `dates_per_week`: Average dates per week since first entry
- `longest_streak_weeks`: Longest consecutive weeks with at least one date
- `rating_trend`: "improving", "declining", or "stable" (based on last 10 entries)
- `mood_distribution`: Count of each mood type
- `category_distribution`: Count of each category

---

### Get Milestones
**GET** `/api/journal/milestones`

Retrieves all earned milestones/badges for the user.

**Response:** `List[DateMilestoneResponse]` (sorted by achieved_at DESC)

**Response Example:**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "milestone_type": "five_stars",
    "milestone_name": "Five Stars",
    "milestone_description": "Earned your first 5-star date",
    "achieved_at": "2026-03-10T15:30:00Z"
  },
  {
    "id": "uuid",
    "user_id": "uuid",
    "milestone_type": "date_night_pro",
    "milestone_name": "Date Night Pro",
    "milestone_description": "Completed 10 dates",
    "achieved_at": "2026-02-28T09:00:00Z"
  }
]
```

## Milestone System

Milestones are automatically awarded when journal entries are created. Each milestone is only awarded once.

### Available Milestones

| Type | Name | Requirement |
|------|------|-------------|
| `first_date` | First Date | Create your first journal entry |
| `regular_dater` | Regular Dater | Complete 5 dates |
| `date_night_pro` | Date Night Pro | Complete 10 dates |
| `half_century` | Half Century | Complete 50 dates |
| `five_stars` | Five Stars | Earn your first 5-star rating |
| `adventurer` | Adventurer | Complete 3 dates in "adventure" category |
| `foodie_couple` | Foodie Couple | Complete 3 dates in "foodie" category |
| `creative_souls` | Creative Souls | Complete 3 dates in "creative" category |
| `budget_friendly` | Budget Friendly | Complete 5 dates under $30 each |
| `big_spender` | Big Spender | Complete a single date over $200 |
| `streak_week` | Streak Week | Have dates in 3 consecutive weeks |
| `anniversary` | Anniversary | Log a date on an occasion date (birthday/anniversary) |

### Milestone Award Logic

The system uses efficient SQL queries to check conditions:

- **Count-based:** Direct COUNT(*) queries for simple thresholds
- **Category-based:** JOINs with date_ideas table to check categories and tags
- **Cost-based:** Direct filtering on total_cost field
- **Date-based:** DATE_TRUNC and EXTRACT functions for streak detection
- **Occasion-based:** JOIN with occasions table to match dates

All milestone checks are performed in a transaction within the same database connection to ensure consistency.

## Data Models

### JournalEntryResponse
```python
{
    "id": "UUID",
    "user_id": "UUID",
    "planned_date_id": "UUID | null",
    "title": "str",
    "date_date": "datetime",
    "rating": "int | null",  # 1-5
    "mood": "str | null",    # amazing, fun, romantic, okay, meh
    "notes": "str | null",
    "highlights": "str | null",
    "would_repeat": "bool",
    "total_cost": "float | null",
    "location_name": "str | null",
    "photos": "List[str]",
    "tags": "List[str]",
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

### DateStatsResponse
```python
{
    "total_dates_completed": "int",
    "average_rating": "float | null",
    "most_common_mood": "str | null",
    "total_money_spent": "float",
    "average_cost_per_date": "float",
    "favorite_category": "str | null",
    "dates_per_week": "float",
    "longest_streak_weeks": "int",
    "rating_trend": "str | null",  # improving, declining, stable
    "mood_distribution": "Dict[str, int]",
    "category_distribution": "Dict[str, int]"
}
```

### TimelineEntry
```python
{
    "month": "YYYY-MM",
    "total_dates": "int",
    "average_rating": "float | null",
    "top_mood": "str | null",
    "total_spent": "float",
    "entries": "List[JournalEntryResponse]"
}
```

### DateMilestoneResponse
```python
{
    "id": "UUID",
    "user_id": "UUID",
    "milestone_type": "str",
    "milestone_name": "str",
    "milestone_description": "str | null",
    "achieved_at": "datetime"
}
```

## Authentication

All endpoints require authentication via JWT token in the Authorization header:

```
Authorization: Bearer <jwt-token>
```

Tokens are validated using the same JWT verification mechanism as the main application.

## Error Handling

All endpoints follow standard HTTP error conventions:

- **400**: Bad request (invalid parameters)
- **401**: Unauthorized (missing/invalid token)
- **404**: Not found (entry/resource doesn't exist)
- **500**: Internal server error

Error responses:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Performance Considerations

### Indexes
- All user-scoped queries use `idx_date_memories_user_id` for fast filtering
- Timeline and date range queries use `idx_date_memories_user_date` for efficient sorting
- Milestone checks use unique index to prevent duplicates

### Query Optimization
- Timeline view uses GROUP BY and aggregation functions for monthly stats
- Statistics use efficient SQL aggregation (AVG, SUM, COUNT)
- Milestone checks use efficient JOINs rather than in-memory processing
- Pagination is implemented with LIMIT/OFFSET

### Database Operations
- All milestone checks happen within a transaction during entry creation
- Bulk milestone checking uses batched queries
- No N+1 query problems in any endpoint

## Integration with Planned Dates

Journal entries can be linked to planned dates via the `planned_date_id` field. This allows:

- Tracking which planned date ideas were executed
- Joining with date_ideas table to get category information for stats
- Matching dates with occasions (anniversaries, birthdays)

The relationship is optional (SET NULL on planned_dates deletion), allowing entries to exist independently.

## Files Modified/Created

### Created:
- `/sessions/jolly-elegant-bohr/bllue/backend/journal.py` - Complete journal system implementation (1089 lines)

### Modified:
- `/sessions/jolly-elegant-bohr/bllue/backend/main.py`
  - Added import of journal router, set_db_pool, and init_journal_tables
  - Added app.include_router(journal_router)
  - Added await init_journal_tables() in startup
  - Added journal_set_db_pool(db_pool) in startup

## Usage Examples

### Create a journal entry
```bash
curl -X POST http://localhost:8000/api/journal/entry \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Romantic dinner",
    "date_date": "2026-03-15T19:30:00Z",
    "rating": 5,
    "mood": "amazing",
    "notes": "Perfect evening",
    "highlights": "shared dessert",
    "would_repeat": true,
    "total_cost": 85.50,
    "location_name": "Trattoria",
    "photos": [],
    "tags": ["romantic", "foodie"]
  }'
```

### Get all entries with high ratings
```bash
curl http://localhost:8000/api/journal/entries?rating_min=4 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get comprehensive stats
```bash
curl http://localhost:8000/api/journal/stats \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get timeline view
```bash
curl http://localhost:8000/api/journal/timeline \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### View milestones earned
```bash
curl http://localhost:8000/api/journal/milestones \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Logging

The journal system uses Python's standard logging module with the logger name `journal`. All significant operations are logged:

- Table initialization
- Milestone awards
- Database errors
- Query execution issues

Logs are written to the application's standard logger configured in main.py.

