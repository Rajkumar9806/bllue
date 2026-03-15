# Smart Algorithm - Quick Reference

## Core Functions

### `compute_user_preferences(user_id, pool)`
Analyzes user's accept/reject history.

```python
prefs = await compute_user_preferences(user_id, pool)
# Returns:
# {
#   "category_scores": {"romantic": 0.85, ...},
#   "budget_preference": {"low": 0.3, "medium": 0.5, "high": 0.2},
#   "location_preference": {"indoor": 0.4, "outdoor": 0.45, "both": 0.15},
#   "top_tags": ["romantic", "outdoor", ...],
#   "avoided_tags": ["nightlife", ...],
#   "total_interactions": 42,
#   "acceptance_rate": 0.65,
#   "personality_evolution": "Trending toward romantic",
#   "confidence": "high" # or "medium" or "low"
# }
```

**Use when:**
- Building user preference profiles
- Analyzing behavior patterns
- Comparing stated vs actual preferences

---

### `build_smart_prompt(user_id, pool, partner_id=None, mood=None, weather=None)`
Constructs AI prompt with behavioral insights.

```python
prompt = await build_smart_prompt(
    user_id=user_id,
    pool=pool,
    partner_id="partner-uuid",  # optional
    mood="romantic",            # optional
    weather=weather_data        # optional
)
# Returns: Complete prompt string ready for AI provider
```

**Use when:**
- Generating personalized date ideas
- You want behavior-driven recommendations
- Context: mood/weather available

---

### `compute_partner_compatibility(user_id, partner_id, pool)`
Compares two users' preferences.

```python
compat = await compute_partner_compatibility(user_id, partner_id, pool)
# Returns:
# {
#   "compatibility_score": 78,           # 0-100
#   "shared_categories": ["romantic"],
#   "compromise_categories": ["adventure"],
#   "conflict_categories": [],
#   "ideal_budget": "medium",
#   "ideal_location": "both",
#   "recommended_tags": ["romantic", "foodie"],
#   "avoid_tags": ["extreme"]
# }
```

**Use when:**
- Couple mode recommendations
- Analyzing relationship compatibility
- Finding compromise date types

---

### `get_current_weather(lat, lon)`
Fetches weather data.

```python
weather = await get_current_weather(lat=40.7128, lon=-74.0060)
# Returns:
# {
#   "temp_f": 72.5,
#   "condition": "sunny",  # sunny/rainy/cloudy/snowy/unknown
#   "is_outdoor_friendly": True,
#   "description": "Sunny, 72.5°F"
# }
```

**Use when:**
- User provides location
- You want weather context in recommendations
- Gracefully degrades if API unavailable

---

## API Endpoints

### GET `/api/recommendations/smart`
Get smart personalized ideas.

**Query Params:**
```
mood=romantic|adventurous|low_key|spontaneous|foodie|creative  # optional
lat=40.7128                                                      # optional
lon=-74.0060                                                     # optional
count=5                                                          # default 5
```

**Response:** `{ "ideas": [...], "count": 5 }`

---

### GET `/api/recommendations/preferences`
Get user's preference profile.

**Response:** Complete preference analysis with confidence level

---

### GET `/api/recommendations/mood-options`
Get available moods.

**Response:** `{ "moods": { "romantic": "...", ... } }`

---

### GET `/api/recommendations/partner-compatibility`
Get couple analysis.

**Query Params:**
```
partner_id=uuid  # optional, auto-detects if not provided
```

**Response:** Compatibility score and recommendations

---

## Constants

### MOOD_OPTIONS
```python
{
    "adventurous": "Feeling daring and want to try something exciting",
    "romantic": "Want something intimate, meaningful, and connection-focused",
    "low_key": "Prefer relaxed, comfortable, and laid-back activities",
    "spontaneous": "Open to anything fun and unexpected",
    "foodie": "Focus on culinary experiences and food adventures",
    "creative": "Interested in artistic, cultural, or hands-on experiences"
}
```

### MOOD_WEIGHTS
```python
{
    "adventurous": {"adventure": 1.5, "active": 1.3, "outdoor": 1.2},
    "romantic": {"romantic": 1.5, "relaxing": 1.2, "indoor": 1.1},
    "low_key": {"relaxing": 1.5, "fun": 1.2, "indoor": 1.3, "low": 1.2},
    "spontaneous": {"adventure": 1.3, "fun": 1.3, "trending": 1.2},
    "foodie": {"foodie": 1.5, "cultural": 1.1},
    "creative": {"creative": 1.5, "cultural": 1.2}
}
```

---

## Confidence Levels

| Interactions | Level    | Behavior                              |
|--------------|----------|---------------------------------------|
| < 5          | `"low"`  | Fallback to questionnaire data        |
| 5-15         | `"medium"` | Blending questionnaire + behavior   |
| 15+          | `"high"` | Behavior-driven (reliable)            |

---

## Quick Examples

### Example 1: Generate smart recommendations
```python
# In endpoint handler
pool = await get_db()
prompt = await build_smart_prompt(
    user_id=user.user_id,
    pool=pool
)
provider = get_ai_provider(current_ai_provider)
text = await provider.generate(prompt, temperature=0.9)
ideas = json.loads(clean_response_text(text))
```

### Example 2: Check user preferences
```python
pool = await get_db()
prefs = await compute_user_preferences(user.user_id, pool)

if prefs.get('confidence') == 'high':
    print(f"Strong affinity for {list(prefs['category_scores'].keys())}")
else:
    print("User has limited interaction history")
```

### Example 3: Couple recommendations
```python
pool = await get_db()
compat = await compute_partner_compatibility(user_id, partner_id, pool)

if compat['compatibility_score'] > 70:
    print(f"Shared interests: {compat['shared_categories']}")
else:
    print(f"Need compromise on: {compat['compromise_categories']}")
```

### Example 4: Mood + weather
```python
pool = await get_db()
weather = await get_current_weather(lat=40.7128, lon=-74.0060)

prompt = await build_smart_prompt(
    user_id=user.user_id,
    pool=pool,
    mood="romantic",
    weather=weather
)
```

---

## Environment Variables

**Required:**
- `DATABASE_URL` - PostgreSQL connection

**Optional:**
- `OPENWEATHER_API_KEY` - For weather integration (gracefully skipped if not set)

---

## Common Patterns

### Pattern 1: New user flow
```
1. Show mood options: GET /api/recommendations/mood-options
2. User selects mood
3. Get smart ideas: GET /api/recommendations/smart?mood=romantic
4. User accepts/rejects (builds history)
5. After 15+ interactions → confidence="high"
```

### Pattern 2: Returning user
```
1. Get preferences: GET /api/recommendations/preferences
2. Show summary to user: "You love romantic & foodie dates"
3. Get ideas: GET /api/recommendations/smart
4. Continue learning from accepts/rejects
```

### Pattern 3: Couple mode
```
1. Get compatibility: GET /api/recommendations/partner-compatibility
2. Show score + recommendations
3. Get couple ideas: GET /api/recommendations/smart
4. Both partners accept/reject (shared history)
```

---

## Scoring Formulas

**Category Affinity:**
```
score = accepts / (accepts + rejects)
Range: 0.0 to 1.0
```

**Compatibility Score:**
```
base = 50
+ min(shared_categories × 10, 30)
+ 10 if total_acceptance_rates > 1.2
- conflict_categories × 5
Final: 0-100
```

**Acceptance Rate:**
```
acceptance_rate = accepted_ideas / total_interactions
Range: 0.0 to 1.0 (displayed as percentage)
```

---

## Interpretation Guide

| Metric | Low | Medium | High |
|--------|-----|--------|------|
| Acceptance Rate | < 40% | 40-70% | > 70% |
| Confidence | < 5 interactions | 5-15 | 15+ |
| Category Score | < 0.3 | 0.3-0.7 | > 0.7 |
| Compatibility | < 40 | 40-75 | > 75 |

---

## Troubleshooting

**Q: Recommendations seem generic**
A: Check confidence level. If "low", system is using questionnaire. Continue accepting/rejecting.

**Q: Weather integration not working**
A: Set `OPENWEATHER_API_KEY` env var. System gracefully skips if not available.

**Q: User has conflicting preferences**
A: This is valid data! Use `compromise_categories` to find middle ground.

**Q: Different recommendation each time**
A: Expected! Temperature=0.9 adds randomness. Use same prompt for deterministic results.

---

## Performance Notes

- **compute_user_preferences**: O(n) where n = interactions (typically < 100ms)
- **compute_partner_compatibility**: O(m+n) (typically < 200ms)
- **build_smart_prompt**: O(p) pure computation (typically < 50ms)
- **get_current_weather**: ~500ms API call (cached in practice)

---

## Database Queries Used

The algorithm uses these queries:

1. Fetch user profile
2. Fetch interaction history with idea details
3. GROUP BY category/budget/location for statistics
4. Extract tags from accepted/rejected ideas

All efficient with proper indexing on:
- `idea_interactions(user_id, date_idea_id)`
- `users(id)`
- `date_ideas(id)`

---

## Next Steps for Enhancement

1. **Caching**: Cache preferences in Redis (24hr TTL)
2. **Temporal Decay**: Weight recent interactions more
3. **A/B Testing**: Test algorithm variants
4. **Collaborative Filtering**: Recommend based on similar users
5. **ML Model**: Train preference classifier
6. **Explanation Engine**: Generate "why we recommend this" insights
