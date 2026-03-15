# Arrow Partner Pairing System - API Documentation

## Overview

The Partner Pairing System enables couples using the Arrow dating app to connect, share wishlists, and receive compatibility-based date recommendations. The system matches users based on their interaction history with date ideas and generates smart compatibility reports.

## Architecture

### Database Tables

#### `partner_connections`
Stores partner relationship metadata.

```sql
CREATE TABLE partner_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    partner_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    invite_code VARCHAR(8) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, accepted, declined
    created_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP,
    UNIQUE(user_id, partner_user_id)
);
```

#### `shared_wishlist`
Stores items that partners have shared with each other.

```sql
CREATE TABLE shared_wishlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID REFERENCES partner_connections(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date_idea_id UUID REFERENCES date_ideas(id) ON DELETE CASCADE,
    notes TEXT,
    shared_at TIMESTAMP DEFAULT NOW()
);
```

### Invite Code Format

Invite codes are 6 alphanumeric characters in the format `XXX-XXX` (e.g., `ARW-X4K`). They:
- Use uppercase letters and digits (excluding I, l, O, 0 for clarity)
- Are globally unique
- Expire when the partnership is accepted or manually declined
- Are case-insensitive when validating

## API Endpoints

All endpoints require the `Authorization: Bearer <token>` header.

### 1. Generate Invite Code

**POST** `/api/partner/invite`

Generate a unique 6-character invite code for the current user.

**Request Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "invite_code": "ARW-X4K"
}
```

**Error Responses:**
- `400 Bad Request`: User already has pending/active partnership
- `500 Internal Server Error`: Failed to generate unique code
- `401 Unauthorized`: Missing/invalid token

**Notes:**
- Only one pending invitation per user allowed
- Cannot generate code if already connected to a partner
- Save the code and share with partner via SMS/QR code

---

### 2. Accept Invite Code

**POST** `/api/partner/accept`

Accept a partner invitation using their invite code.

**Request Body:**
```json
{
  "invite_code": "ARW-X4K"
}
```

**Response (200 OK):**
```json
{
  "status": "accepted",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "partner": {
    "id": "650e8400-e29b-41d4-a716-446655440000",
    "name": "Sarah",
    "phone_number": "+1234567890"
  },
  "accepted_at": "2026-03-15T14:30:00"
}
```

**Error Responses:**
- `400 Bad Request`:
  - Missing `invite_code`
  - Code already accepted/declined
  - Trying to pair with yourself
  - User already has active partnership
- `404 Not Found`: Invite code doesn't exist
- `401 Unauthorized`: Missing/invalid token

**Validation Rules:**
- Code must be pending status
- Cannot pair with yourself (user_id != initiator user_id)
- Cannot have multiple active partnerships
- Partner must exist in system

---

### 3. Get Partnership Status

**GET** `/api/partner/status`

Get current partnership information.

**Request Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK) - Connected:**
```json
{
  "status": "connected",
  "connection_status": "accepted",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "partner": {
    "id": "650e8400-e29b-41d4-a716-446655440000",
    "name": "Sarah",
    "phone_number": "+1234567890"
  },
  "connected_since": "2026-03-10T10:30:00"
}
```

**Response (200 OK) - Not Connected:**
```json
{
  "status": "not_connected",
  "partner": null,
  "connection_status": "none"
}
```

**Error Responses:**
- `401 Unauthorized`: Missing/invalid token

---

### 4. Disconnect Partnership

**DELETE** `/api/partner/disconnect`

End an active partnership and delete all shared wishlist items.

**Request Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "status": "disconnected",
  "message": "Partnership ended successfully"
}
```

**Error Responses:**
- `404 Not Found`: No active partnership
- `401 Unauthorized`: Missing/invalid token

**Side Effects:**
- Deletes the `partner_connections` record
- Cascades to delete all `shared_wishlist` items
- Cannot undo - user must re-invite to reconnect

---

### 5. Share Wishlist Item

**POST** `/api/partner/wishlist/share`

Share a date idea with your partner.

**Request Body:**
```json
{
  "date_idea_id": "750e8400-e29b-41d4-a716-446655440000",
  "notes": "I think this would be perfect for us!"
}
```

**Response (200 OK):**
```json
{
  "status": "shared",
  "share_id": "850e8400-e29b-41d4-a716-446655440000",
  "idea": {
    "id": "750e8400-e29b-41d4-a716-446655440000",
    "title": "Cooking Class Date"
  },
  "notes": "I think this would be perfect for us!",
  "shared_at": "2026-03-15T14:30:00"
}
```

**Error Responses:**
- `400 Bad Request`:
  - Missing `date_idea_id`
  - No active partnership
- `404 Not Found`: Date idea doesn't exist
- `401 Unauthorized`: Missing/invalid token

**Notes:**
- Only 1 entry per (connection, idea) combination (prevents duplicates)
- Notes field is optional (max length not enforced)
- Sharing multiple ideas is allowed

---

### 6. Get Shared Wishlist

**GET** `/api/partner/wishlist`

Retrieve all ideas shared between partners.

**Request Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK) - Connected:**
```json
{
  "status": "success",
  "total_items": 3,
  "items": [
    {
      "id": "950e8400-e29b-41d4-a716-446655440000",
      "user_id": "650e8400-e29b-41d4-a716-446655440000",
      "date_idea_id": "750e8400-e29b-41d4-a716-446655440000",
      "notes": "This looks amazing!",
      "shared_at": "2026-03-15T14:30:00"
    }
  ],
  "shared_by_me": [
    {
      "id": "950e8400-e29b-41d4-a716-446655440000",
      "date_idea": {
        "id": "750e8400-e29b-41d4-a716-446655440000",
        "title": "Cooking Class Date",
        "description": "Learn to cook Italian cuisine...",
        "category": "food",
        "budget_estimate": "medium",
        "duration": "3-4 hours",
        "image_url": "https://..."
      },
      "notes": "I think this would be perfect for us!",
      "shared_at": "2026-03-15T14:30:00",
      "shared_by": "You"
    }
  ],
  "shared_by_partner": [
    {
      "id": "850e8400-e29b-41d4-a716-446655440000",
      "date_idea": {
        "id": "650e8400-e29b-41d4-a716-446655440000",
        "title": "Sunset Picnic",
        "description": "Pack a basket and watch the sunset...",
        "category": "romantic",
        "budget_estimate": "low",
        "duration": "2 hours",
        "image_url": "https://..."
      },
      "notes": "Let's do this next weekend!",
      "shared_at": "2026-03-14T10:00:00",
      "shared_by": "Sarah"
    }
  ]
}
```

**Response (200 OK) - Not Connected:**
```json
{
  "status": "no_partnership",
  "items": [],
  "shared_by_me": [],
  "shared_by_partner": []
}
```

**Error Responses:**
- `401 Unauthorized`: Missing/invalid token

---

### 7. Get Combined Preferences

**GET** `/api/partner/preferences`

Get merged preference profile for both partners (used by AI for date recommendations).

**Request Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "status": "success",
  "user": {
    "personality_type": "romantic",
    "interests": ["cooking", "travel", "art"],
    "budget_preference": "medium"
  },
  "partner": {
    "personality_type": "adventurous",
    "interests": ["hiking", "food", "art"],
    "budget_preference": "medium"
  },
  "combined": {
    "shared_interests": ["art", "food"],
    "all_interests": ["cooking", "travel", "art", "hiking", "food"],
    "budget_compatibility": true,
    "shared_budgets": ["medium"]
  },
  "compatibility": {
    "compatibility_score": 75,
    "shared_interests": ["food", "art"],
    "category_overlap_percentage": 66.7,
    "budget_compatible": true,
    "shared_budgets": ["medium"],
    "category_conflicts": [],
    "suggested_date_types": ["food", "art", "adventure"]
  }
}
```

**Error Responses:**
- `400 Bad Request`: No active partnership
- `401 Unauthorized`: Missing/invalid token

**Notes:**
- `compatibility_score` ranges from 0-100
- Based on `idea_interactions` table (accept/reject history)
- Used by AI to generate personalized date recommendations
- Both users' data is merged for holistic profile

---

### 8. Get Compatibility Report

**GET** `/api/partner/compatibility`

Get detailed compatibility analysis with recommendations.

**Request Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "status": "success",
  "you": "You",
  "partner": "Sarah",
  "compatibility_score": 78,
  "compatibility_level": "great_match",
  "shared_interests": ["food", "adventure", "culture"],
  "category_overlap_percentage": 75.0,
  "budget_compatible": true,
  "shared_budgets": ["medium", "high"],
  "category_conflicts": [],
  "suggested_date_types": ["food", "adventure", "culture"],
  "recommendations": [
    "You two have excellent compatibility! Plan your date night!",
    "You share budget preferences: medium, high",
    "Your shared interests: food, adventure, culture",
    "Try these date types: food, adventure, culture"
  ]
}
```

**Compatibility Levels:**
- `perfect_match`: Score >= 80
- `great_match`: Score >= 60
- `good_match`: Score >= 40
- `potential_match`: Score < 40

**Error Responses:**
- `400 Bad Request`: No active partnership
- `401 Unauthorized`: Missing/invalid token

**Notes:**
- Recommendations are dynamically generated
- Based on shared interests, budget alignment, and interaction history
- `suggested_date_types` come from shared accepted categories
- Conflicts are categories one person rejected while other accepted

## Implementation Details

### Invite Code Generation

```python
def generate_invite_code() -> str:
    """Generate unique 6-char alphanumeric code (XXX-XXX format)"""
    # Uses uppercase letters and digits, excludes I, l, O, 0
    # Retries up to 10 times if collision detected
```

### Compatibility Calculation

Compatibility is calculated from `idea_interactions` table:

1. **Category Analysis**: Compare accepted/rejected categories between partners
2. **Overlap Score**: (Shared accepted / Total accepted) * 100
3. **Budget Alignment**: Check if users accepted same budget ranges
4. **Conflict Detection**: Identify categories where opinions diverge

```python
compatibility_score = min(100, int(category_overlap * 100))
```

### Partnership Workflow

1. User A generates invite code → Pending connection created
2. User A shares code with User B (out-of-band)
3. User B accepts code → Partnership accepted, timestamps set
4. Both users can now share wishlists and view compatibility
5. Either user can delete partnership (cascades to shared items)

### Indexes

Optimized with indexes on:
- `partner_connections(invite_code)` - For lookup during accept
- `partner_connections(status)` - For filtering pending/active
- `shared_wishlist(connection_id)` - For retrieving partner's shares

## Error Handling

All endpoints follow consistent error patterns:

```json
{
  "detail": "Error message describing the issue"
}
```

HTTP Status Codes:
- `200 OK` - Successful operation
- `400 Bad Request` - Invalid input, missing fields, business logic violations
- `401 Unauthorized` - Missing/invalid JWT token
- `404 Not Found` - Resource doesn't exist
- `500 Internal Server Error` - Database/system error

## Authentication

All endpoints require Bearer token in Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Token contains:
- `user_id`: UUID of authenticated user
- `phone_number`: User's phone number
- `exp`: Token expiration timestamp

## Rate Limiting

No explicit rate limiting implemented (consider adding at production):
- Generate invite: 1 per user (per active partnership)
- Share wishlist: Multiple allowed
- Accept invite: 1 per user (per active partnership)

## Testing Examples

### Complete Workflow

```bash
# 1. User A generates invite
curl -X POST http://localhost:8000/api/partner/invite \
  -H "Authorization: Bearer <token_a>" \
  -H "Content-Type: application/json"

# Response: { "invite_code": "ARW-X4K" }

# 2. User A shares code with User B out-of-band (SMS, QR, etc)

# 3. User B accepts invite
curl -X POST http://localhost:8000/api/partner/accept \
  -H "Authorization: Bearer <token_b>" \
  -H "Content-Type: application/json" \
  -d '{"invite_code": "ARW-X4K"}'

# 4. Both check status
curl http://localhost:8000/api/partner/status \
  -H "Authorization: Bearer <token_a>"

# 5. Either user shares ideas
curl -X POST http://localhost:8000/api/partner/wishlist/share \
  -H "Authorization: Bearer <token_a>" \
  -H "Content-Type: application/json" \
  -d '{"date_idea_id": "...", "notes": "Perfect for us!"}'

# 6. View shared wishlist
curl http://localhost:8000/api/partner/wishlist \
  -H "Authorization: Bearer <token_a>"

# 7. Check compatibility
curl http://localhost:8000/api/partner/compatibility \
  -H "Authorization: Bearer <token_a>"

# 8. Disconnect if needed
curl -X DELETE http://localhost:8000/api/partner/disconnect \
  -H "Authorization: Bearer <token_a>"
```

## Production Considerations

1. **Rate Limiting**: Add per-user rate limits to prevent abuse
2. **Encryption**: Consider encrypting shared notes at rest
3. **Audit Trail**: Log all partnership changes for support
4. **Notifications**: Send push notifications on invite/acceptance
5. **Expiry**: Implement time-based expiry for pending invites (e.g., 30 days)
6. **Analytics**: Track compatibility scores and date type suggestions

## Future Enhancements

1. **Partnership History**: Keep deleted partnerships for analytics
2. **Conflict Resolution**: AI-powered suggestions for conflicting interests
3. **Mood/Context Matching**: Factor in current mood/occasion
4. **Seasonal Recommendations**: Adjust suggestions based on season
5. **Location-Aware**: Consider both partners' locations for recommendations
6. **Activity Tracking**: Track which shared ideas were actually done
7. **Feedback Loop**: Learn from completed dates to improve recommendations
