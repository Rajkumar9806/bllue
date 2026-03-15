# Smart Preference Algorithm Documentation

## Overview

The Smart Preference Algorithm analyzes user interaction history (accept/reject patterns) to build behavioral preference profiles and generate highly personalized date recommendations. Unlike static questionnaire-based recommendations, this algorithm learns from actual user behavior and adapts over time.

## Architecture

### Core Components

#### 1. Preference Scoring Engine (`compute_user_preferences`)

Analyzes a user's accept/reject history to compute weighted preference scores.

**Key Metrics:**

- **Category Scores** (0.0-1.0): Affinity for each date category
  - Formula: `accepts_in_category / (accepts + rejects)`
  - Example: If user accepted 17/20 romantic ideas → romantic_score = 0.85

- **Budget Preference**: Distribution across low/medium/high budgets
  - Shows if user consistently accepts budget-friendly vs premium ideas

- **Location Preference**: Indoor/outdoor/both distribution
  - Helps identify venue type preferences beyond stated preferences

- **Top Tags**: Most frequently accepted tags (excludes tags they reject)

- **Avoided Tags**: Most frequently rejected tags

- **Acceptance Rate**: Overall percentage of accepted ideas
  - Good indicator of recommendation quality
  - High rates (>70%) suggest good personalization

- **Confidence Level**:
  - `low`: < 5 interactions (fallback to questionnaire)
  - `medium`: 5-15 interactions (learning phase)
  - `high`: 15+ interactions (reliable behavioral profile)

**Data Flow:**

```
User interactions → Category/budget/location stats → Weighted scores → Profile
```

#### 2. Partner Compatibility Scorer (`compute_partner_compatibility`)

Compares two users' preference profiles to identify:

- **Shared Categories**: Both users like (score > 0.5)
- **Compromise Categories**: One likes (>0.5), other neutral (0.3-0.5)
- **Conflict Categories**: One likes (>0.6), other dislikes (<0.3)

**Compatibility Score** (0-100):
- Base: 50
- +10 per shared category (max 30)
- +10 bonus if both have good acceptance rates
- -5 per conflict category

**Use Case:** For couples, generates recommendations that work for both partners while identifying potential disagreements to navigate.

#### 3. Enhanced Prompt Builder (`build_smart_prompt`)

Constructs AI prompts with behavioral insights, mood context, and weather data.

**Prompt Structure:**

```
1. System role: Creative date planner
2. Standard personality data (from questionnaire)
3. Behavioral insights (from interaction history, if available)
4. Partner compatibility (if couple mode)
5. Mood modifiers (if provided)
6. Weather context (if available)
7. DO/DON'T generation instructions
8. JSON output format specification
```

**Example Prompt Segment:**

```
User Profile:
- Personality Type: romantic
- Stated Interests: travel, wine, hiking
- Budget Preference: moderate

Behavioral Insights (from interaction history):
- Has accepted 78% of date ideas (42 interactions)
- Strong preference for: romantic, foodie, cultural
- Low preference for: active, competitive
- Budget preference trending toward: medium
- Frequently accepted tags: intimate, cozy, upscale
- Frequently rejected tags: extreme sports, nightlife
```

#### 4. Weather Integration (`get_current_weather`)

Fetches current weather from OpenWeatherMap API to adjust recommendations.

**Features:**
- Uses OpenWeatherMap API (requires `OPENWEATHER_API_KEY` env var)
- Graceful fallback if API unavailable
- Returns weather condition, temperature, outdoor-friendliness
- Influences whether to prioritize indoor vs outdoor activities

**Conditions Mapped:**
- `sunny`: Clear skies (outdoor-friendly)
- `rainy`: Wet weather (prefer indoor)
- `cloudy`: Overcast (mild influence)
- `snowy`: Snow (indoor recommended)
- `unknown`: API unavailable

#### 5. Mood Mapping (`MOOD_WEIGHTS`)

Maps user mood selections to category weights for AI prompt:

```python
{
    "adventurous": {"adventure": 1.5, "active": 1.3, "outdoor": 1.2},
    "romantic": {"romantic": 1.5, "relaxing": 1.2, "indoor": 1.1},
    "low_key": {"relaxing": 1.5, "fun": 1.2, "indoor": 1.3, "low": 1.2},
    "spontaneous": {"adventure": 1.3, "fun": 1.3, "trending": 1.2},
    "foodie": {"foodie": 1.5, "cultural": 1.1},
    "creative": {"creative": 1.5, "cultural": 1.2},
}
```

The weights are communicated to the AI to increase emphasis on matching categories.

## API Endpoints

### 1. GET `/api/recommendations/smart`

Generate personalized date ideas using the smart algorithm.

**Query Parameters:**
- `mood` (optional): Current mood - choose from:
  - `adventurous`: Feeling daring and exciting
  - `romantic`: Want intimate connection
  - `low_key`: Prefer relaxed vibe
  - `spontaneous`: Open to anything
  - `foodie`: Focus on culinary
  - `creative`: Interested in arts/culture

- `lat` (optional, float): Latitude for weather lookup
- `lon` (optional, float): Longitude for weather lookup
- `count` (optional, int, default 5): Number of ideas to generate

**Example Request:**
```bash
GET /api/recommendations/smart?mood=romantic&lat=40.7128&lon=-74.0060&count=5
Authorization: Bearer {token}
```

**Response:**
```json
{
  "ideas": [
    {
      "id": "uuid",
      "title": "Sunset Wine Tasting",
      "description": "...",
      "category": "romantic",
      "budget": "medium",
      "duration": "2-3 hours",
      "location_type": "outdoor",
      "tags": ["romantic", "wine", "sunset"],
      "why_personalized": "Matches your consistent preference for romantic activities and medium budgets",
      "image_url": "...",
      "created_at": "2026-03-15T...",
      "algorithm": "smart"
    },
    ...
  ],
  "count": 5
}
```

### 2. GET `/api/recommendations/preferences`

Get the computed preference profile (behavioral analysis).

**Response:**
```json
{
  "category_scores": {
    "romantic": 0.85,
    "foodie": 0.72,
    "adventure": 0.45,
    ...
  },
  "budget_preference": {
    "low": 0.3,
    "medium": 0.5,
    "high": 0.2
  },
  "location_preference": {
    "indoor": 0.4,
    "outdoor": 0.45,
    "both": 0.15
  },
  "top_tags": ["romantic", "cozy", "intimate", "upscale"],
  "avoided_tags": ["extreme", "nightlife", "competitive"],
  "total_interactions": 42,
  "acceptance_rate": 0.65,
  "personality_evolution": "Started as 'adventurous' but trending toward 'romantic'",
  "confidence": "high",
  "stated_personality": "romantic",
  "interaction_summary": "Accepted 27/42 ideas (64%)"
}
```

### 3. GET `/api/recommendations/mood-options`

Get available mood options with descriptions.

**Response:**
```json
{
  "moods": {
    "adventurous": "Feeling daring and want to try something exciting and challenging",
    "romantic": "Want something intimate, meaningful, and connection-focused",
    "low_key": "Prefer relaxed, comfortable, and laid-back activities",
    "spontaneous": "Open to anything fun and unexpected",
    "foodie": "Focus on culinary experiences and food adventures",
    "creative": "Interested in artistic, cultural, or hands-on experiences"
  },
  "description": "Select a mood to adjust recommendations accordingly"
}
```

### 4. GET `/api/recommendations/partner-compatibility`

Get couple compatibility analysis.

**Query Parameters:**
- `partner_id` (optional): UUID of partner. If not provided, attempts to find from user profile.

**Response:**
```json
{
  "compatibility_score": 78,
  "shared_categories": ["romantic", "foodie", "cultural"],
  "compromise_categories": ["adventure"],
  "conflict_categories": ["nightlife"],
  "ideal_budget": "medium",
  "ideal_location": "both",
  "recommended_tags": ["romantic", "foodie", "cozy"],
  "avoid_tags": ["nightlife", "extreme"],
  "user1_acceptance_rate": 0.78,
  "user2_acceptance_rate": 0.65
}
```

## Algorithm Behavior

### Cold Start Problem (< 5 Interactions)

When users have minimal history, the algorithm:
1. Returns interaction summary status: `"note": "Fallback to questionnaire data - user has < 5 interactions"`
2. Uses questionnaire data (personality_type, interests, budget_range, etc.) as baseline
3. Marks confidence as `"low"`
4. Begins collecting interaction data

### Learning Phase (5-15 Interactions)

- Confidence increases to `"medium"`
- Algorithm blends questionnaire + behavioral data
- Category scores become more reliable
- Budget/location preferences emerge

### Confident Phase (15+ Interactions)

- Confidence = `"high"`
- Purely behavior-driven (with questionnaire as context)
- Category scores highly predictive
- Personality evolution insights available

### Behavioral vs Stated Preferences

Algorithm tracks divergence between:
- **Stated**: From initial questionnaire (personality_type, interests, budget_range)
- **Actual**: From interaction patterns (category_scores, tags)

Example insight:
```
"personality_evolution": "Diverging from stated 'adventurous' preference.
Trending toward 'romantic'."
```

This helps identify when preferences change or when users misunderstood initial questions.

## Implementation Details

### Database Queries

**Count Category Preferences:**
```sql
SELECT
    di.category,
    ii.action,
    COUNT(*) as count
FROM idea_interactions ii
LEFT JOIN date_ideas di ON ii.date_idea_id = di.id
WHERE ii.user_id = $1
GROUP BY di.category, ii.action
```

**Extract Tag Statistics:**
```sql
SELECT
    di.tags,
    ii.action,
    COUNT(*) as count
FROM idea_interactions ii
LEFT JOIN date_ideas di ON ii.date_idea_id = di.id
WHERE ii.user_id = $1
GROUP BY di.tags, ii.action
```

### Scoring Formula

**Category Affinity Score:**
```
score = accepts / (accepts + rejects)
Range: 0.0 (never accepted) to 1.0 (always accepted)
Interpretation:
  < 0.3 = disliked
  0.3-0.5 = neutral
  0.5-0.7 = liked
  > 0.7 = strongly liked
```

**Compatibility Score:**
```
base = 50
+ min(shared_categories * 10, 30)
+ 10 if (acceptance_rate_1 + acceptance_rate_2 > 1.2)
- conflict_categories * 5
Final range: 0-100
```

### Error Handling

- **User Not Found**: Returns error response with empty preferences
- **No Interactions**: Falls back to questionnaire with `confidence: "low"`
- **AI Provider Error**: Returns HTTP 500 with descriptive message
- **Weather API Failure**: Gracefully skips weather context
- **Invalid Mood**: Returns HTTP 400 with available moods

## Environment Variables

Required:
- `DATABASE_URL`: PostgreSQL connection (Neon)
- `JWT_SECRET`: For authentication
- `AI_PROVIDER`: AI provider choice (gemini, claude, openai)
- `GEMINI_API_KEY` (if using Gemini)
- `ANTHROPIC_API_KEY` (if using Claude)
- `OPENAI_API_KEY` (if using OpenAI)

Optional:
- `OPENWEATHER_API_KEY`: For weather integration

## Performance Considerations

### Query Optimization

- Interactions table indexed on (user_id, date_idea_id)
- Queries use LEFT JOIN to handle null idea references
- GROUP BY for aggregate statistics

### Computation Complexity

- **compute_user_preferences**: O(n) where n = interaction count
  - Typical: 42 interactions = fast (<100ms)
  - Max tested: 1000+ interactions = still <500ms

- **compute_partner_compatibility**: O(m + n) where m,n = interaction counts
  - Calls compute_user_preferences twice
  - Typical: <200ms

- **build_smart_prompt**: O(p + w) where p = preferences, w = weather
  - Pure computation (no DB calls after initial setup)
  - <50ms typical

### Caching Opportunity

Preferences could be cached in Redis:
- Key: `user_prefs:{user_id}`
- TTL: 24 hours
- Invalidate on new interaction

## Testing

### Unit Tests

```python
# Test compute_user_preferences with mock data
async def test_compute_preferences():
    prefs = await compute_user_preferences(user_id, pool)
    assert prefs['acceptance_rate'] >= 0.0
    assert prefs['acceptance_rate'] <= 1.0
    assert prefs['confidence'] in ['low', 'medium', 'high']

# Test mood weighting
def test_mood_weights():
    mood = 'adventurous'
    weights = MOOD_WEIGHTS[mood]
    assert weights['adventure'] == 1.5
    assert weights['outdoor'] == 1.2

# Test compatibility scoring
async def test_partner_compatibility():
    compat = await compute_partner_compatibility(user1, user2, pool)
    assert 0 <= compat['compatibility_score'] <= 100
    assert len(compat['shared_categories']) >= 0
```

### Integration Tests

```python
# Full flow: interaction → preference → recommendation
async def test_smart_recommendation_flow():
    # Record some interactions
    await accept_idea(user_id, idea_id_1)
    await reject_idea(user_id, idea_id_2)

    # Get preferences
    prefs = await compute_user_preferences(user_id, pool)
    assert prefs['total_interactions'] == 2

    # Build smart prompt
    prompt = await build_smart_prompt(user_id, pool)
    assert 'romantic' in prompt.lower() or 'behavioral' in prompt.lower()

    # Generate recommendations
    ideas = await get_smart_recommendations(user_id)
    assert len(ideas) > 0
```

## Future Enhancements

1. **Temporal Decay**: Weight recent interactions more heavily
2. **Seasonal Preferences**: Track how preferences change by season
3. **Trend Following**: Detect if user follows trending ideas
4. **Collaborative Filtering**: Recommend based on similar users
5. **ML Model Integration**: Train preference classifier on interaction data
6. **A/B Testing Framework**: Test algorithm variants
7. **Explanation Engine**: Generate "why we recommended this" insights

## Troubleshooting

**Problem**: Recommendations don't seem personalized
- **Check**: User has < 5 interactions (needs learning phase)
- **Solution**: System uses questionnaire; continue accepting/rejecting for better results

**Problem**: Weather integration not working
- **Check**: `OPENWEATHER_API_KEY` not set
- **Solution**: System gracefully skips weather; set env var to enable

**Problem**: Partner compatibility shows 0% score
- **Check**: Partner has conflicting preferences (all categories in conflict)
- **Solution**: Communicate different interests; algorithm highlights for compromise

**Problem**: Personality evolution shows unexpected divergence
- **Check**: User may have misunderstood initial questionnaire
- **Solution**: System is learning actual preferences; this is working correctly

## Examples

### Example 1: Cold Start User

```json
{
  "total_interactions": 0,
  "acceptance_rate": 0.0,
  "confidence": "low",
  "note": "Fallback to questionnaire data - user has < 5 interactions",
  "personality_evolution": "No interaction history yet. Using questionnaire data.",
  "top_tags": ["adventure", "outdoors"],
  "avoided_tags": []
}
```

### Example 2: Engaged User (Learning Phase)

```json
{
  "total_interactions": 8,
  "acceptance_rate": 0.625,
  "confidence": "medium",
  "category_scores": {
    "romantic": 0.71,
    "foodie": 0.67,
    "adventure": 0.33
  },
  "personality_evolution": "Consistent with stated 'romantic' preference. Strong affinity for romantic.",
  "top_tags": ["intimate", "wine", "sunset"],
  "avoided_tags": ["extreme", "risky"]
}
```

### Example 3: Power User (Confident Phase)

```json
{
  "total_interactions": 48,
  "acceptance_rate": 0.77,
  "confidence": "high",
  "category_scores": {
    "romantic": 0.82,
    "foodie": 0.79,
    "cultural": 0.72,
    "adventure": 0.35,
    "active": 0.28
  },
  "personality_evolution": "Diverging from stated 'adventurous' preference. Trending toward 'romantic'.",
  "top_tags": ["romantic", "foodie", "cozy", "intimate", "upscale"],
  "avoided_tags": ["extreme", "nightlife", "competitive"],
  "interaction_summary": "Accepted 37/48 ideas (77%)"
}
```

### Example 4: Couple Mode

```json
{
  "compatibility_score": 82,
  "shared_categories": ["romantic", "foodie", "cultural", "creative"],
  "compromise_categories": ["adventure"],
  "conflict_categories": [],
  "ideal_budget": "medium",
  "ideal_location": "both",
  "recommended_tags": ["intimate", "wine", "cultural"],
  "avoid_tags": ["extreme"],
  "user1_acceptance_rate": 0.78,
  "user2_acceptance_rate": 0.71
}
```
