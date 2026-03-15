"""
Smart Algorithm Usage Examples

This file demonstrates how to use the smart preference algorithm
with real-world examples and test cases.
"""

import asyncio
import asyncpg
from datetime import datetime
from smart_algorithm import (
    compute_user_preferences,
    compute_partner_compatibility,
    build_smart_prompt,
    get_current_weather,
    MOOD_OPTIONS,
    MOOD_WEIGHTS,
)


# ============================================================================
# EXAMPLE 1: Cold Start User (< 5 interactions)
# ============================================================================
async def example_cold_start():
    """
    A brand new user who just completed the questionnaire.
    The algorithm should fall back to questionnaire data.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Cold Start User")
    print("=" * 70)

    # Simulated new user (no interactions yet)
    user_id = "550e8400-e29b-41d4-a716-446655440000"

    print(f"\nNew user {user_id} with NO interaction history.")
    print("Expected behavior: Use questionnaire data with low confidence\n")

    # In real scenario, you'd have a database connection:
    # pool = await get_db()
    # prefs = await compute_user_preferences(user_id, pool)
    #
    # Expected output:
    # {
    #     "total_interactions": 0,
    #     "confidence": "low",
    #     "note": "Fallback to questionnaire data - user has < 5 interactions",
    #     "personality_evolution": "No interaction history yet. Using questionnaire data.",
    #     "acceptance_rate": 0.0
    # }

    print("Expected preference structure:")
    print("""
    {
        "category_scores": {},
        "budget_preference": {},
        "location_preference": {},
        "top_tags": ["adventure", "outdoor"],
        "avoided_tags": [],
        "total_interactions": 0,
        "acceptance_rate": 0.0,
        "confidence": "low",
        "note": "Fallback to questionnaire data - user has < 5 interactions"
    }
    """)


# ============================================================================
# EXAMPLE 2: Learning Phase User (5-15 interactions)
# ============================================================================
async def example_learning_phase():
    """
    A user with emerging preferences from recent interactions.
    The algorithm combines questionnaire + behavior.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Learning Phase User (8 interactions)")
    print("=" * 70)

    print("""
Scenario:
- User stated "adventurous" but accepted mostly romantic ideas
- Has 8 total interactions: 5 accepted, 3 rejected
- Acceptance rate: 62.5%

Expected preference structure:
    {
        "category_scores": {
            "romantic": 0.71,    # 5 romantic, 2 rejected
            "adventure": 0.33,   # 1 accepted, 2 rejected
            "foodie": 0.50       # 2 accepted, 2 rejected
        },
        "budget_preference": {
            "medium": 0.60,
            "low": 0.40
        },
        "location_preference": {
            "indoor": 0.50,
            "outdoor": 0.50
        },
        "top_tags": ["intimate", "cozy", "wine"],
        "avoided_tags": ["extreme", "risky"],
        "total_interactions": 8,
        "acceptance_rate": 0.625,
        "confidence": "medium",
        "personality_evolution": "Diverging from stated 'adventurous'...
                                  Trending toward 'romantic'."
    }

Algorithm behavior:
- Identifies category preference divergence
- Begins weighting behavior over questionnaire
- Provides reliability note (medium confidence)
- Recommends categories user actually likes vs stated preferences
    """)


# ============================================================================
# EXAMPLE 3: Power User (15+ interactions)
# ============================================================================
async def example_power_user():
    """
    An engaged user with strong behavioral patterns.
    The algorithm relies primarily on behavior.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Power User (48 interactions)")
    print("=" * 70)

    print("""
Scenario:
- User with 48 interactions over 2 months
- Clear pattern: loves romantic + foodie, avoids extreme sports
- Acceptance rate: 77%

Expected preference structure:
    {
        "category_scores": {
            "romantic": 0.82,
            "foodie": 0.79,
            "cultural": 0.72,
            "creative": 0.68,
            "adventure": 0.35,
            "active": 0.28,
            "fun": 0.45
        },
        "budget_preference": {
            "medium": 0.65,
            "high": 0.25,
            "low": 0.10
        },
        "location_preference": {
            "both": 0.40,
            "indoor": 0.38,
            "outdoor": 0.22
        },
        "top_tags": [
            "romantic",
            "foodie",
            "cozy",
            "intimate",
            "upscale"
        ],
        "avoided_tags": [
            "extreme",
            "nightlife",
            "competitive"
        ],
        "total_interactions": 48,
        "acceptance_rate": 0.77,
        "confidence": "high",
        "personality_evolution": "Diverging from stated 'adventurous'...
                                  Trending toward 'romantic'."
    }

Algorithm behavior:
- High confidence in category scores
- Personality evolution clearly identified
- Recommendations heavily favor romantic + foodie + cultural
- Explicitly avoids extreme sports, nightlife categories
- Budget reflects preference for mid-to-premium experiences
    """)


# ============================================================================
# EXAMPLE 4: Using Moods for Context
# ============================================================================
async def example_mood_context():
    """
    Demonstrating how mood selection influences recommendations.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Mood-Based Recommendation Adjustment")
    print("=" * 70)

    print("\nAvailable moods and their category weightings:")
    for mood, weights in MOOD_WEIGHTS.items():
        print(f"\n  {mood}:")
        for category, weight in weights.items():
            print(f"    - {category}: {weight}x")

    print("""
Scenario: Same user, different moods, same day

Same user profile (romantic + foodie preference) makes different requests:

1. mood="romantic":
   - Weights: romantic 1.5x, relaxing 1.2x, indoor 1.1x
   - Generated ideas: Wine tasting, couples massage, cozy dinner

2. mood="adventurous":
   - Weights: adventure 1.5x, active 1.3x, outdoor 1.2x
   - Generated ideas: Hiking with picnic, kayaking trip, rock climbing

3. mood="foodie":
   - Weights: foodie 1.5x, cultural 1.1x
   - Generated ideas: Food tour, cooking class, gourmet restaurant

Same user, different moods → Different recommendations that still match base preferences
    """)


# ============================================================================
# EXAMPLE 5: Weather Integration
# ============================================================================
async def example_weather_context():
    """
    Demonstrating how weather influences recommendations.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Weather-Based Recommendation Adjustment")
    print("=" * 70)

    print("""
Scenario: New York City user requesting ideas

1. Sunny, 72°F (outdoor-friendly):
   Request: GET /api/recommendations/smart?lat=40.7128&lon=-74.0060

   Weather context in prompt:
   "Weather is nice. Consider outdoor activities."

   Recommendations may include:
   - Central Park picnic
   - Rooftop bar
   - Outdoor wine garden

2. Rainy, 45°F (indoor preferred):
   Request: GET /api/recommendations/smart?lat=40.7128&lon=-74.0060

   Weather context in prompt:
   "Weather is not ideal for outdoor activities. Prioritize indoor options."

   Recommendations may include:
   - Indoor wine tasting
   - Museum visit
   - Cooking class

3. Unknown/unavailable weather:
   System gracefully skips weather context and uses mood/profile only

Weather conditions mapped:
- sunny: outdoor-friendly
- cloudy: mild influence
- rainy: indoor recommended
- snowy: indoor strongly recommended
- unknown: no influence
    """)


# ============================================================================
# EXAMPLE 6: Couple Mode - Partner Compatibility
# ============================================================================
async def example_couple_compatibility():
    """
    Demonstrating partner compatibility analysis.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Couple Mode - Partner Compatibility Analysis")
    print("=" * 70)

    print("""
Scenario: Couple with different interests

Partner A (User 1):
- Preferences: romantic 0.80, foodie 0.75, adventure 0.65
- Budget: mostly medium
- Accepted: "wine night", "cooking class", "hiking"

Partner B (User 2):
- Preferences: adventure 0.85, active 0.80, foodie 0.50
- Budget: mostly low (budget-conscious)
- Accepted: "rock climbing", "hiking", "trail running"

Compatibility Analysis:
{
    "compatibility_score": 72,
    "shared_categories": ["foodie", "adventure"],
    "compromise_categories": ["romantic"],
    "conflict_categories": ["nightlife"],
    "ideal_budget": "medium",
    "ideal_location": "both",
    "recommended_tags": ["hiking", "outdoor", "active"],
    "avoid_tags": ["extreme", "nightlife"],
    "user1_acceptance_rate": 0.75,
    "user2_acceptance_rate": 0.80
}

Interpretation:
- Moderate to good compatibility (72/100)
- Strong agreement on: foodie, adventure activities
- Compromise needed on: romantic gestures (A likes, B neutral)
- Avoid conflicts by: skipping extreme/nightlife ideas
- Sweet spot: medium budget, outdoor foodie activities like "picnic hiking"

Generated recommendations for couple:
✓ Farmers market → cooking together (shared foodie interest)
✓ Hiking with gourmet snacks (both like adventure + food)
✓ Restaurant with outdoor seating (compromise: romantic setting + active exploration)
✗ Nightclub (conflict category)
✗ Extreme rock climbing (too risky for compromise)
    """)


# ============================================================================
# EXAMPLE 7: Personalized Prompt Construction
# ============================================================================
async def example_smart_prompt_construction():
    """
    Demonstrating how smart prompts are constructed.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Smart Prompt Construction")
    print("=" * 70)

    print("""
For a power user (romantic + foodie lover) with mood="romantic":

Constructed prompt sent to AI:

---
You are a creative date night planner specializing in personalized recommendations.

User Profile:
- Personality Type: romantic
- Stated Interests: travel, wine, cooking
- Budget Preference: moderate
- Location Preference: both
- Favorite Activities: wine tasting, cooking, travel

Behavioral Insights (from interaction history):
- Has accepted 77% of date ideas (48 interactions)
- Strong preference for: romantic, foodie, cultural
- Low preference for: active, competitive
- Budget preference trending toward: medium
- Frequently accepted tags: romantic, foodie, cozy, intimate, upscale
- Frequently rejected tags: extreme, nightlife, competitive
- Diverging from stated 'adventurous' preference. Trending toward 'romantic'.

Current Mood: romantic
Context: Want something intimate, meaningful, and connection-focused
Adjust recommendations to match this mood - increase weight for matching categories.

Generate 5 unique and personalized date night ideas:
- Match the user's behavioral preferences
- Vary in categories and experiences
- Include a mix of budgets if the user is flexible
- AVOID these tags: extreme, nightlife, competitive

Return ONLY a valid JSON array (no markdown, no explanation):
[...]
---

This prompt is WAY more effective than generic prompts because:
✓ AI understands actual user behavior (77% acceptance rate!)
✓ Specific constraints (avoid extreme/nightlife)
✓ Context on what changed (trending toward romantic)
✓ Mood modifier (romantic context)
✓ Clear personality evolution
    """)


# ============================================================================
# EXAMPLE 8: API Usage Patterns
# ============================================================================
async def example_api_usage():
    """
    Demonstrating common API usage patterns.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 8: API Usage Patterns")
    print("=" * 70)

    print("""
Pattern 1: First-time user flow
────────────────────────────────
GET /api/recommendations/mood-options
→ Display mood selector to user

GET /api/recommendations/smart?mood=romantic
→ Get initial recommendations based on questionnaire

(User accepts/rejects ideas...)

Pattern 2: Regular user flow
───────────────────────────
GET /api/recommendations/preferences
→ Show user their computed preference profile

GET /api/recommendations/smart
→ Get smart recommendations (uses learned preferences)

Pattern 3: Couple planning
──────────────────────────
GET /api/recommendations/partner-compatibility
→ See compatibility score and ideal date types

GET /api/recommendations/smart?mood=romantic
→ Get recommendations optimized for both partners

Pattern 4: Weather-aware planning
────────────────────────────────
GET /api/recommendations/smart?lat=40.7128&lon=-74.0060&mood=adventure
→ Get recommendations considering weather + mood + preferences

Pattern 5: Mood-based flow
──────────────────────────
1. User selects mood from /api/recommendations/mood-options
2. GET /api/recommendations/smart?mood=foodie
3. Show ideas filtered/weighted for that mood
4. User accepts/rejects (feeds back into preference learning)

Best Practices:
- Always call /api/recommendations/mood-options on first visit
- Show preferences profile after 15+ interactions (high confidence)
- Use partner-compatibility endpoint for couple mode
- Include lat/lon if you have location data
- Don't repeat exact same request multiple times (cache on client)
    """)


# ============================================================================
# EXAMPLE 9: Troubleshooting Guide
# ============================================================================
async def example_troubleshooting():
    """
    Common issues and how the algorithm handles them.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 9: Troubleshooting & Edge Cases")
    print("=" * 70)

    print("""
Issue 1: "Recommendations don't match my personality"
────────────────────────────────────────────────────
User says: "I'm adventurous but you're recommending romantic ideas"

Root cause: Algorithm detected behavior divergence
- Stated personality: "adventurous"
- Actual behavior: Accepting romantic ideas (80% acceptance)
- System is learning real preferences

Solution:
- This is working as intended! System learns actual behavior.
- The personality_evolution field will show: "Diverging from stated
  'adventurous'... Trending toward 'romantic'."
- If recommendation is wrong, user can reject it (feeds back learning)

Issue 2: "All recommendations are the same category"
────────────────────────────────────────────────────
Root cause: User has VERY strong preference for one category

Example: User accepted 95% romantic ideas, 0% adventure
- Category score: romantic 0.95, adventure 0.05
- Algorithm correctly weights toward romantic

Solution:
- User can select different mood (e.g., "adventurous") to get variety
- Or use generic /api/date-ideas endpoint for non-personalized options

Issue 3: "Weather integration isn't working"
────────────────────────────────────────────
Root cause: OPENWEATHER_API_KEY not set or API failure

System behavior: Gracefully falls back to mood/profile-only recommendations

Solution:
- Check OPENWEATHER_API_KEY environment variable is set
- Or provide mood parameter to get contextual recommendations

Issue 4: "Partner compatibility shows 0% score"
───────────────────────────────────────────────
Root cause: Partners have very different preferences in all categories

Example:
- Partner A: romantic 0.80, foodie 0.75
- Partner B: adventure 0.85, active 0.90
- No shared categories above 0.5

Algorithm correctly computed low compatibility (0 shared categories)

Solution:
- Look at "compromise_categories" for potential common ground
- "recommended_tags" might show any minimal overlap
- This is useful info for communication!
- Try discussing different date types

Issue 5: "Low confidence predictions (< 5 interactions)"
────────────────────────────────────────────────────────
Root cause: New user

System behavior: Uses questionnaire data as fallback

Solution:
- This is normal for new users
- System will gain confidence as user accepts/rejects more ideas
- After 15+ interactions, confidence will be "high"
- Recommendations will improve naturally over time

Issue 6: "Divergent personality_evolution but I haven't changed"
────────────────────────────────────────────────────────────────
Root cause: Initial questionnaire didn't accurately capture preferences

Example:
- Stated: "adventurous"
- Actually wants: romantic, cozy experiences

Solution:
- System is learning your real preferences
- This data is valuable for better recommendations
- If questionnaire answers were wrong, you can update profile
    """)


# ============================================================================
# MAIN EXECUTION
# ============================================================================
async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("SMART PREFERENCE ALGORITHM - USAGE EXAMPLES")
    print("=" * 70)

    # Run all examples
    await example_cold_start()
    await example_learning_phase()
    await example_power_user()
    await example_mood_context()
    await example_weather_context()
    await example_couple_compatibility()
    await example_smart_prompt_construction()
    await example_api_usage()
    await example_troubleshooting()

    print("\n" + "=" * 70)
    print("EXAMPLES COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
