"""
Smart Preference Algorithm v2 for Arrow Dating App

Analyzes user interaction history (accept/reject) to compute weighted preference
profiles and generate enhanced AI prompts with behavioral insights.

v2 additions:
- Temporal Intelligence (time-of-day, day-of-week patterns)
- Feedback Depth (post-date ratings feed back into algorithm)
- Seasonal & Anniversary Awareness
- Budget Awareness (monthly pacing)
- Repeat & Freshness Decay (suppress overused ideas)
- Energy Level Matching
- Surprise Wildcard Factor
"""

import asyncpg
import logging
import math
import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
import httpx
import os

logger = logging.getLogger(__name__)

# ==================== CONSTANTS ====================

# Mood-to-category weighting mappings
MOOD_WEIGHTS = {
    "adventurous": {"adventure": 1.5, "active": 1.3, "outdoor": 1.2},
    "romantic": {"romantic": 1.5, "relaxing": 1.2, "indoor": 1.1},
    "low_key": {"relaxing": 1.5, "fun": 1.2, "indoor": 1.3, "low": 1.2},
    "spontaneous": {"adventure": 1.3, "fun": 1.3, "trending": 1.2},
    "foodie": {"foodie": 1.5, "cultural": 1.1},
    "creative": {"creative": 1.5, "cultural": 1.2},
}

MOOD_OPTIONS = {
    "adventurous": "Feeling daring and want to try something exciting and challenging",
    "romantic": "Want something intimate, meaningful, and connection-focused",
    "low_key": "Prefer relaxed, comfortable, and laid-back activities",
    "spontaneous": "Open to anything fun and unexpected",
    "foodie": "Focus on culinary experiences and food adventures",
    "creative": "Interested in artistic, cultural, or hands-on experiences",
}

ENERGY_LEVELS = {
    "low": {
        "description": "Tired, want to relax",
        "boost": {"relaxing": 1.5, "indoor": 1.4, "fun": 1.1},
        "suppress": {"adventure": 0.5, "active": 0.4, "outdoor": 0.7}
    },
    "medium": {
        "description": "Normal energy, open to anything",
        "boost": {},
        "suppress": {}
    },
    "high": {
        "description": "Energized and ready for action",
        "boost": {"adventure": 1.4, "active": 1.5, "outdoor": 1.3, "fun": 1.2},
        "suppress": {"relaxing": 0.6, "indoor": 0.7}
    }
}

# Time-of-day slots
TIME_SLOTS = {
    "morning": (6, 12),     # 6am - 12pm
    "afternoon": (12, 17),  # 12pm - 5pm
    "evening": (17, 21),    # 5pm - 9pm
    "night": (21, 6),       # 9pm - 6am
}

# Day-of-week categories
DAY_TYPES = {
    "weekday": [0, 1, 2, 3, 4],   # Mon-Fri
    "weekend": [5, 6],              # Sat-Sun
}

# Budget levels with approximate costs
BUDGET_COSTS = {
    "low": (0, 30),
    "medium": (30, 80),
    "high": (80, 500),
}

# Seasonal date categories
SEASONS = {
    "spring": {"months": [3, 4, 5], "boost": ["outdoor", "nature", "garden", "picnic", "hiking"]},
    "summer": {"months": [6, 7, 8], "boost": ["outdoor", "water", "beach", "adventure", "festival"]},
    "fall": {"months": [9, 10, 11], "boost": ["cozy", "foodie", "cultural", "hiking", "harvest"]},
    "winter": {"months": [12, 1, 2], "boost": ["indoor", "cozy", "romantic", "winter", "holiday"]},
}

# Special dates awareness
SPECIAL_DATES = {
    "valentines": {"month": 2, "day": 14, "days_before": 7, "tags": ["romantic", "special", "luxurious"]},
    "christmas": {"month": 12, "day": 25, "days_before": 14, "tags": ["holiday", "festive", "cozy", "gift"]},
    "new_years": {"month": 1, "day": 1, "days_before": 3, "tags": ["celebration", "nightlife", "special"]},
    "halloween": {"month": 10, "day": 31, "days_before": 7, "tags": ["fun", "costume", "spooky", "creative"]},
}

# Freshness decay: after this many days, a previously-used idea can resurface
FRESHNESS_DECAY_DAYS = 21


# ==================== TEMPORAL INTELLIGENCE ====================

def get_current_time_slot() -> str:
    """Determine current time-of-day slot."""
    hour = datetime.utcnow().hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def get_day_type() -> str:
    """Determine if today is weekday or weekend."""
    return "weekend" if datetime.utcnow().weekday() in DAY_TYPES["weekend"] else "weekday"


def get_current_season() -> str:
    """Get current season based on month."""
    month = datetime.utcnow().month
    for season, info in SEASONS.items():
        if month in info["months"]:
            return season
    return "spring"


async def compute_temporal_preferences(user_id: str, pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Analyze WHEN the user accepts ideas to find time-of-day and day-of-week patterns.

    Returns:
    - time_slot_scores: {morning: 0.8, evening: 0.6, ...}
    - day_type_scores: {weekday: 0.3, weekend: 0.9}
    - peak_activity_time: 'evening'
    - peak_activity_day: 'weekend'
    """
    async with pool.acquire() as conn:
        interactions = await conn.fetch("""
            SELECT action, created_at
            FROM idea_interactions
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 200
        """, user_id)

    if not interactions:
        return {"time_slot_scores": {}, "day_type_scores": {}, "peak_activity_time": None, "peak_activity_day": None}

    time_stats = {"morning": {"accepted": 0, "total": 0}, "afternoon": {"accepted": 0, "total": 0},
                  "evening": {"accepted": 0, "total": 0}, "night": {"accepted": 0, "total": 0}}
    day_stats = {"weekday": {"accepted": 0, "total": 0}, "weekend": {"accepted": 0, "total": 0}}

    for row in interactions:
        ts = row['created_at']
        if not ts:
            continue

        # Time slot
        hour = ts.hour
        if 6 <= hour < 12:
            slot = "morning"
        elif 12 <= hour < 17:
            slot = "afternoon"
        elif 17 <= hour < 21:
            slot = "evening"
        else:
            slot = "night"

        time_stats[slot]["total"] += 1
        if row['action'] == 'accepted':
            time_stats[slot]["accepted"] += 1

        # Day type
        dt = "weekend" if ts.weekday() in DAY_TYPES["weekend"] else "weekday"
        day_stats[dt]["total"] += 1
        if row['action'] == 'accepted':
            day_stats[dt]["accepted"] += 1

    # Compute scores
    time_slot_scores = {}
    for slot, stats in time_stats.items():
        if stats["total"] > 0:
            time_slot_scores[slot] = round(stats["accepted"] / stats["total"], 2)

    day_type_scores = {}
    for dt, stats in day_stats.items():
        if stats["total"] > 0:
            day_type_scores[dt] = round(stats["accepted"] / stats["total"], 2)

    peak_time = max(time_slot_scores, key=time_slot_scores.get) if time_slot_scores else None
    peak_day = max(day_type_scores, key=day_type_scores.get) if day_type_scores else None

    return {
        "time_slot_scores": time_slot_scores,
        "day_type_scores": day_type_scores,
        "peak_activity_time": peak_time,
        "peak_activity_day": peak_day
    }


# ==================== FEEDBACK DEPTH ====================

async def compute_feedback_enhanced_preferences(user_id: str, pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Incorporate post-date journal ratings back into the preference algorithm.

    A date idea that was accepted AND rated 5 stars is a STRONG positive signal.
    A date idea that was accepted but rated 2 stars is a WEAK positive (or even negative).

    Returns:
    - rating_weighted_categories: {category: weighted_score}
    - avg_rating: average journal rating
    - high_rated_tags: tags from 4-5 star dates
    - low_rated_tags: tags from 1-2 star dates
    - would_repeat_categories: categories user would repeat
    """
    async with pool.acquire() as conn:
        # Join journal entries with date ideas to get rated experiences
        rated_dates = await conn.fetch("""
            SELECT
                dm.rating,
                dm.mood,
                dm.would_repeat,
                dm.total_cost,
                dm.tags,
                dm.title
            FROM date_memories dm
            WHERE dm.user_id = $1 AND dm.rating IS NOT NULL
            ORDER BY dm.date_date DESC
            LIMIT 100
        """, user_id)

    if not rated_dates:
        return {
            "rating_weighted_categories": {},
            "avg_rating": None,
            "high_rated_tags": [],
            "low_rated_tags": [],
            "would_repeat_categories": [],
            "total_rated_dates": 0
        }

    # Aggregate
    total_rating = 0
    rating_count = 0
    tag_ratings = {}  # tag -> [list of ratings]
    would_repeat_tags = []

    for row in rated_dates:
        rating = row['rating']
        total_rating += rating
        rating_count += 1

        tags = row.get('tags') or []
        for tag in tags:
            if tag not in tag_ratings:
                tag_ratings[tag] = []
            tag_ratings[tag].append(rating)

        if row.get('would_repeat') and tags:
            would_repeat_tags.extend(tags)

    avg_rating = round(total_rating / rating_count, 1) if rating_count > 0 else None

    # High-rated tags (avg >= 4)
    high_rated_tags = sorted(
        [tag for tag, ratings in tag_ratings.items() if sum(ratings) / len(ratings) >= 4.0],
        key=lambda t: sum(tag_ratings[t]) / len(tag_ratings[t]),
        reverse=True
    )[:8]

    # Low-rated tags (avg <= 2)
    low_rated_tags = sorted(
        [tag for tag, ratings in tag_ratings.items() if sum(ratings) / len(ratings) <= 2.0],
        key=lambda t: sum(tag_ratings[t]) / len(tag_ratings[t])
    )[:5]

    # Would-repeat frequency
    repeat_freq = {}
    for tag in would_repeat_tags:
        repeat_freq[tag] = repeat_freq.get(tag, 0) + 1
    would_repeat_top = sorted(repeat_freq.keys(), key=lambda t: repeat_freq[t], reverse=True)[:5]

    return {
        "rating_weighted_categories": {tag: round(sum(r) / len(r), 1) for tag, r in tag_ratings.items()},
        "avg_rating": avg_rating,
        "high_rated_tags": high_rated_tags,
        "low_rated_tags": low_rated_tags,
        "would_repeat_categories": would_repeat_top,
        "total_rated_dates": rating_count
    }


# ==================== SEASONAL & ANNIVERSARY AWARENESS ====================

def get_seasonal_context() -> Dict[str, Any]:
    """
    Compute seasonal and special-date awareness.

    Returns which season it is, any upcoming special dates, and seasonal tag boosts.
    """
    today = datetime.utcnow()
    month = today.month
    day = today.day

    # Current season
    season = get_current_season()
    seasonal_boosts = SEASONS[season]["boost"]

    # Check for upcoming special dates
    upcoming_specials = []
    for name, info in SPECIAL_DATES.items():
        special_date = date(today.year, info["month"], info["day"])
        # If the special date has passed this year, check next year
        if special_date < today.date():
            special_date = date(today.year + 1, info["month"], info["day"])

        days_until = (special_date - today.date()).days
        if days_until <= info["days_before"]:
            upcoming_specials.append({
                "name": name,
                "date": str(special_date),
                "days_until": days_until,
                "boost_tags": info["tags"]
            })

    return {
        "season": season,
        "seasonal_boosts": seasonal_boosts,
        "upcoming_specials": upcoming_specials,
        "month": month,
        "day_of_year": today.timetuple().tm_yday
    }


async def get_anniversary_context(user_id: str, pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Check if the user has any upcoming anniversaries or partner birthdays
    from their occasions table.
    """
    today = datetime.utcnow()
    window = today + timedelta(days=14)  # 2-week lookahead

    async with pool.acquire() as conn:
        upcoming = await conn.fetch("""
            SELECT person_name, occasion_type, date, notes
            FROM occasions
            WHERE user_id = $1
            ORDER BY date ASC
        """, user_id)

    # Check anniversary_date from user profile
    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT anniversary_date, partner_name, partner_dob FROM users WHERE id = $1",
            user_id
        )

    relevant = []

    # Check occasions table
    for row in upcoming:
        occ_date = row['date']
        if occ_date:
            # Normalize to this year for recurring events
            try:
                this_year_date = occ_date.replace(year=today.year)
                if this_year_date < today:
                    this_year_date = occ_date.replace(year=today.year + 1)
                days_until = (this_year_date - today).days
                if 0 <= days_until <= 14:
                    relevant.append({
                        "person": row['person_name'],
                        "type": row['occasion_type'],
                        "days_until": days_until,
                        "notes": row.get('notes')
                    })
            except (ValueError, TypeError):
                pass

    # Check user profile dates
    if user_row:
        for field, label in [("anniversary_date", "anniversary"), ("partner_dob", "partner_birthday")]:
            val = user_row.get(field)
            if val:
                try:
                    parsed = datetime.strptime(val, "%Y-%m-%d") if isinstance(val, str) else val
                    this_year = parsed.replace(year=today.year)
                    if this_year < today:
                        this_year = parsed.replace(year=today.year + 1)
                    days_until = (this_year - today).days
                    if 0 <= days_until <= 14:
                        relevant.append({
                            "person": user_row.get("partner_name", "Partner"),
                            "type": label,
                            "days_until": days_until
                        })
                except (ValueError, TypeError):
                    pass

    return {
        "upcoming_events": relevant,
        "has_upcoming": len(relevant) > 0
    }


# ==================== BUDGET AWARENESS ====================

async def compute_budget_context(user_id: str, pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Track spending patterns from journal entries to pace budget across the month.

    Returns:
    - month_spent: total this month
    - avg_monthly_spend: average over past 3 months
    - budget_headroom: 'plenty' | 'moderate' | 'tight'
    - recommended_budget: 'low' | 'medium' | 'high'
    """
    today = datetime.utcnow()
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    three_months_ago = month_start - timedelta(days=90)

    async with pool.acquire() as conn:
        # This month's spending from journal
        month_spent = await conn.fetchval("""
            SELECT COALESCE(SUM(total_cost), 0)
            FROM date_memories
            WHERE user_id = $1 AND date_date >= $2
        """, user_id, month_start) or 0

        # Past 3 months average
        past_spending = await conn.fetch("""
            SELECT
                EXTRACT(MONTH FROM date_date) as m,
                SUM(total_cost) as total
            FROM date_memories
            WHERE user_id = $1 AND date_date >= $2 AND total_cost IS NOT NULL
            GROUP BY EXTRACT(MONTH FROM date_date)
        """, user_id, three_months_ago)

    month_totals = [float(row['total']) for row in past_spending if row['total']]
    avg_monthly = round(sum(month_totals) / len(month_totals), 2) if month_totals else 0

    # Days remaining in month
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    days_remaining = (next_month - today).days

    # Determine budget headroom
    month_spent_float = float(month_spent)
    if avg_monthly > 0:
        spend_ratio = month_spent_float / avg_monthly
        if spend_ratio < 0.5:
            headroom = "plenty"
            recommended = "high" if days_remaining > 10 else "medium"
        elif spend_ratio < 0.8:
            headroom = "moderate"
            recommended = "medium"
        else:
            headroom = "tight"
            recommended = "low"
    else:
        headroom = "unknown"
        recommended = "medium"

    return {
        "month_spent": month_spent_float,
        "avg_monthly_spend": avg_monthly,
        "budget_headroom": headroom,
        "recommended_budget": recommended,
        "days_remaining_in_month": days_remaining
    }


# ==================== FRESHNESS DECAY ====================

async def get_freshness_context(user_id: str, pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Track recently used ideas to prevent repetition.

    Ideas used in the last FRESHNESS_DECAY_DAYS are suppressed.
    Ideas used > FRESHNESS_DECAY_DAYS ago can resurface.

    Returns:
    - recently_done: [titles of recent dates]
    - recently_done_categories: {category: count}
    - suppress_categories: categories used 3+ times recently
    - boost_novel_categories: categories not used in 30+ days
    """
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DECAY_DAYS)
    long_ago = datetime.utcnow() - timedelta(days=60)

    async with pool.acquire() as conn:
        # Recently done dates (from journal)
        recent = await conn.fetch("""
            SELECT title, tags, date_date
            FROM date_memories
            WHERE user_id = $1 AND date_date >= $2
            ORDER BY date_date DESC
        """, user_id, cutoff)

        # All-time categories for novelty detection
        all_time_cats = await conn.fetch("""
            SELECT DISTINCT unnest(tags) as tag, MAX(date_date) as last_used
            FROM date_memories
            WHERE user_id = $1
            GROUP BY tag
        """, user_id)

    recently_done = [row['title'] for row in recent]

    # Count recent categories/tags
    recent_tags = {}
    for row in recent:
        for tag in (row.get('tags') or []):
            recent_tags[tag] = recent_tags.get(tag, 0) + 1

    # Suppress categories used 3+ times recently
    suppress = [tag for tag, count in recent_tags.items() if count >= 3]

    # Boost categories not used in 60+ days
    novel = []
    for row in all_time_cats:
        if row['last_used'] and row['last_used'] < long_ago:
            novel.append(row['tag'])

    return {
        "recently_done": recently_done[:10],
        "recently_done_tags": recent_tags,
        "suppress_tags": suppress,
        "boost_novel_tags": novel[:5],
        "freshness_window_days": FRESHNESS_DECAY_DAYS
    }


# ==================== WILDCARD / SURPRISE FACTOR ====================

def should_inject_wildcard(acceptance_rate: float, total_interactions: int) -> bool:
    """
    Decide whether to inject a wildcard "surprise" idea.

    More likely if:
    - User has a high acceptance rate (they're open to things)
    - User has enough history for us to detect patterns
    - Random chance (roughly 1 in 5 batches)
    """
    if total_interactions < 10:
        return False

    # Higher acceptance rate -> more likely to accept wildcards
    wildcard_chance = 0.15 + (acceptance_rate * 0.1)  # 15-25% base chance
    return random.random() < wildcard_chance


def get_wildcard_prompt_addition(avoided_tags: List[str], top_tags: List[str]) -> str:
    """
    Generate a prompt addition that pushes ONE idea outside the user's comfort zone.
    """
    # Categories the user doesn't usually pick
    all_categories = ["romantic", "adventure", "foodie", "creative", "relaxing", "fun", "cultural", "active"]
    explored = set(top_tags)
    unexplored = [c for c in all_categories if c not in explored and c not in avoided_tags]

    if unexplored:
        surprise_cat = random.choice(unexplored)
        return f"""
WILDCARD: Include exactly 1 surprise idea from the '{surprise_cat}' category that this user
has NOT tried before. Make it intriguing and approachable — the goal is to expand their horizons
without being off-putting. Mark this idea with "wildcard": true in the JSON."""
    return ""


# ==================== CORE PREFERENCE COMPUTATION ====================

async def compute_user_preferences(user_id: str, pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Analyze user's accept/reject history to build a weighted preference profile.

    Returns a comprehensive preference profile including:
    - Category affinities (romantic, adventure, foodie, etc.)
    - Budget distribution
    - Location preferences
    - Most-liked and most-rejected tags
    - Comparison of stated vs actual preferences
    - Overall acceptance rate and interaction count
    """

    async with pool.acquire() as conn:
        # Get user's profile for comparison
        user_row = await conn.fetchrow(
            "SELECT personality_type, interests, budget_range, indoor_outdoor_preference, favorite_activities FROM users WHERE id = $1",
            user_id
        )

        if not user_row:
            logger.warning(f"User {user_id} not found")
            return {
                "error": "User not found",
                "category_scores": {},
                "budget_preference": {},
                "location_preference": {},
                "top_tags": [],
                "avoided_tags": [],
                "total_interactions": 0,
                "acceptance_rate": 0.0,
                "personality_evolution": "Unable to compute - user not found",
                "confidence": "low"
            }

        # Get interaction history with idea details
        interactions = await conn.fetch("""
            SELECT
                ii.action,
                ii.created_at,
                di.category,
                di.budget,
                di.location_type,
                di.tags
            FROM idea_interactions ii
            LEFT JOIN date_ideas di ON ii.date_idea_id = di.id
            WHERE ii.user_id = $1
            ORDER BY ii.created_at DESC
        """, user_id)

        if not interactions:
            # Fallback to questionnaire data with low confidence
            return {
                "category_scores": {},
                "budget_preference": {},
                "location_preference": {},
                "top_tags": list(user_row.get('favorite_activities') or []),
                "avoided_tags": [],
                "total_interactions": 0,
                "acceptance_rate": 0.0,
                "personality_evolution": "No interaction history yet. Using questionnaire data.",
                "confidence": "low",
                "note": "Fallback to questionnaire data - user has < 5 interactions"
            }

        total = len(interactions)
        accepts = sum(1 for i in interactions if i['action'] == 'accepted')
        acceptance_rate = accepts / total if total > 0 else 0.0

        # Compute category scores with recency weighting
        # More recent interactions count more (exponential decay)
        category_stats = {}
        for idx, interaction in enumerate(interactions):
            category = interaction.get('category')
            if not category:
                continue

            # Recency weight: most recent = 1.0, oldest = 0.5
            recency_weight = 0.5 + 0.5 * math.exp(-idx / max(total, 1) * 2)

            if category not in category_stats:
                category_stats[category] = {"accepted": 0.0, "rejected": 0.0}

            if interaction['action'] == 'accepted':
                category_stats[category]['accepted'] += recency_weight
            else:
                category_stats[category]['rejected'] += recency_weight

        # Convert to affinity scores (0.0 to 1.0)
        category_scores = {}
        for category, stats in category_stats.items():
            total_cat = stats['accepted'] + stats['rejected']
            if total_cat > 0:
                category_scores[category] = round(stats['accepted'] / total_cat, 2)

        # Compute budget preference
        budget_stats = {}
        for interaction in interactions:
            budget = interaction.get('budget', 'medium')
            if budget not in budget_stats:
                budget_stats[budget] = {"accepted": 0, "rejected": 0}

            if interaction['action'] == 'accepted':
                budget_stats[budget]['accepted'] += 1
            else:
                budget_stats[budget]['rejected'] += 1

        budget_preference = {}
        for budget, stats in budget_stats.items():
            total_budget = stats['accepted'] + stats['rejected']
            if total_budget > 0:
                budget_preference[budget] = round(stats['accepted'] / total_budget, 2)

        # Compute location preference
        location_stats = {}
        for interaction in interactions:
            location = interaction.get('location_type', 'both')
            if location not in location_stats:
                location_stats[location] = {"accepted": 0, "rejected": 0}

            if interaction['action'] == 'accepted':
                location_stats[location]['accepted'] += 1
            else:
                location_stats[location]['rejected'] += 1

        location_preference = {}
        for location, stats in location_stats.items():
            total_loc = stats['accepted'] + stats['rejected']
            if total_loc > 0:
                location_preference[location] = round(stats['accepted'] / total_loc, 2)

        # Extract tags from accepted and rejected ideas
        liked_tags = {}
        rejected_tags = {}

        for interaction in interactions:
            tags = interaction.get('tags') or []
            for tag in tags:
                if interaction['action'] == 'accepted':
                    liked_tags[tag] = liked_tags.get(tag, 0) + 1
                else:
                    rejected_tags[tag] = rejected_tags.get(tag, 0) + 1

        # Top tags (accepted more than rejected)
        top_tags = sorted(
            [tag for tag in liked_tags if liked_tags.get(tag, 0) > rejected_tags.get(tag, 0)],
            key=lambda t: liked_tags.get(t, 0),
            reverse=True
        )[:5]

        # Avoided tags (rejected more than accepted)
        avoided_tags = sorted(
            [tag for tag in rejected_tags if rejected_tags.get(tag, 0) > liked_tags.get(tag, 0)],
            key=lambda t: rejected_tags.get(t, 0),
            reverse=True
        )[:3]

        # Determine confidence level
        if total < 5:
            confidence = "low"
        elif total < 15:
            confidence = "medium"
        else:
            confidence = "high"

        # Generate personality evolution insight
        stated_interests = set(user_row.get('interests') or [])
        top_category = max(category_scores, key=category_scores.get) if category_scores else None
        stated_personality = user_row.get('personality_type', 'unknown')

        personality_evolution = ""
        if top_category and top_category.lower() != stated_personality.lower():
            personality_evolution = f"Diverging from stated '{stated_personality}' preference. Trending toward '{top_category}'."
        elif top_category:
            personality_evolution = f"Consistent with stated '{stated_personality}' preference. Strong affinity for {top_category}."
        else:
            personality_evolution = "Behavior emerging from interaction history."

        return {
            "category_scores": category_scores,
            "budget_preference": budget_preference,
            "location_preference": location_preference,
            "top_tags": top_tags,
            "avoided_tags": avoided_tags,
            "total_interactions": total,
            "acceptance_rate": round(acceptance_rate, 2),
            "personality_evolution": personality_evolution,
            "confidence": confidence,
            "stated_personality": stated_personality,
            "interaction_summary": f"Accepted {accepts}/{total} ideas ({int(acceptance_rate * 100)}%)"
        }


# ==================== PARTNER COMPATIBILITY ====================

async def compute_partner_compatibility(
    user_id: str,
    partner_id: str,
    pool: asyncpg.Pool
) -> Dict[str, Any]:
    """
    Compare two users' preferences and find overlap.
    """

    async with pool.acquire() as conn:
        # Get preferences for both users
        user1_prefs = await compute_user_preferences(user_id, pool)
        user2_prefs = await compute_user_preferences(partner_id, pool)

        # Compare category scores
        user1_cats = user1_prefs.get('category_scores', {})
        user2_cats = user2_prefs.get('category_scores', {})

        shared_categories = []
        compromise_categories = []
        conflict_categories = []

        all_categories = set(user1_cats.keys()) | set(user2_cats.keys())

        for category in all_categories:
            score1 = user1_cats.get(category, 0)
            score2 = user2_cats.get(category, 0)

            if score1 > 0.5 and score2 > 0.5:
                shared_categories.append(category)
            elif (score1 > 0.5 and 0.3 <= score2 <= 0.5) or (score2 > 0.5 and 0.3 <= score1 <= 0.5):
                compromise_categories.append(category)
            elif (score1 > 0.6 and score2 < 0.3) or (score2 > 0.6 and score1 < 0.3):
                conflict_categories.append(category)

        # Determine ideal budget
        budget1 = user1_prefs.get('budget_preference', {})
        budget2 = user2_prefs.get('budget_preference', {})
        ideal_budget = 'medium'

        if budget1 and budget2:
            common_budgets = set(budget1.keys()) & set(budget2.keys())
            if common_budgets:
                ideal_budget = max(common_budgets, key=lambda b: (budget1[b] + budget2[b]) / 2)

        # Determine ideal location
        loc1 = user1_prefs.get('location_preference', {})
        loc2 = user2_prefs.get('location_preference', {})
        ideal_location = 'both'

        if loc1 and loc2:
            common_locs = set(loc1.keys()) & set(loc2.keys())
            if common_locs:
                ideal_location = max(common_locs, key=lambda l: (loc1[l] + loc2[l]) / 2)

        # Recommended tags
        user1_tags = set(user1_prefs.get('top_tags', []))
        user2_tags = set(user2_prefs.get('top_tags', []))
        recommended_tags = list(user1_tags & user2_tags)

        # Avoid tags
        user1_avoided = set(user1_prefs.get('avoided_tags', []))
        user2_avoided = set(user2_prefs.get('avoided_tags', []))
        avoid_tags = list(user1_avoided | user2_avoided)

        # Calculate compatibility score (0-100)
        compatibility_score = 50

        if shared_categories:
            compatibility_score += min(len(shared_categories) * 10, 30)

        if user1_prefs.get('acceptance_rate', 0) + user2_prefs.get('acceptance_rate', 0) > 1.2:
            compatibility_score += 10

        if conflict_categories:
            compatibility_score -= len(conflict_categories) * 5

        compatibility_score = max(0, min(100, compatibility_score))

        return {
            "compatibility_score": int(compatibility_score),
            "shared_categories": shared_categories,
            "compromise_categories": compromise_categories,
            "conflict_categories": conflict_categories,
            "ideal_budget": ideal_budget,
            "ideal_location": ideal_location,
            "recommended_tags": recommended_tags,
            "avoid_tags": avoid_tags,
            "user1_acceptance_rate": user1_prefs.get('acceptance_rate', 0),
            "user2_acceptance_rate": user2_prefs.get('acceptance_rate', 0)
        }


# ==================== WEATHER ====================

async def get_current_weather(
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> Dict[str, Any]:
    """Get current weather from OpenWeatherMap API."""

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key or lat is None or lon is None:
        return {
            "temp_f": None,
            "condition": "unknown",
            "is_outdoor_friendly": None,
            "description": "Weather data unavailable"
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "appid": api_key, "units": "imperial"}
            )

            if response.status_code != 200:
                return {"temp_f": None, "condition": "unknown", "is_outdoor_friendly": None, "description": "Weather API unavailable"}

            data = response.json()
            temp_f = data.get('main', {}).get('temp')
            main_weather = data.get('weather', [{}])[0].get('main', 'Unknown').lower()
            description = data.get('weather', [{}])[0].get('description', 'Unknown')

            condition = 'unknown'
            if 'clear' in main_weather or 'sunny' in main_weather:
                condition = 'sunny'
            elif 'rain' in main_weather:
                condition = 'rainy'
            elif 'cloud' in main_weather:
                condition = 'cloudy'
            elif 'snow' in main_weather:
                condition = 'snowy'

            is_outdoor_friendly = condition in ['sunny', 'cloudy'] and 50 <= temp_f <= 85

            return {
                "temp_f": temp_f,
                "condition": condition,
                "is_outdoor_friendly": is_outdoor_friendly,
                "description": f"{description}, {temp_f}°F"
            }

    except Exception as e:
        logger.warning(f"Weather API error: {e}")
        return {"temp_f": None, "condition": "unknown", "is_outdoor_friendly": None, "description": "Weather lookup failed"}


# ==================== ENHANCED PROMPT BUILDER ====================

async def build_smart_prompt(
    user_id: str,
    pool: asyncpg.Pool,
    partner_id: Optional[str] = None,
    mood: Optional[str] = None,
    energy: Optional[str] = None,
    weather: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build a dynamically-tuned AI prompt based on real user behavior.

    v2: Now incorporates temporal patterns, journal feedback, seasonal awareness,
    budget pacing, freshness decay, energy level, and wildcard injection.
    """

    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT personality_type, interests, budget_range, indoor_outdoor_preference, favorite_activities FROM users WHERE id = $1",
            user_id
        )

        if not user_row:
            return "Generate 5 unique and creative date night ideas suitable for couples."

    # === GATHER ALL SIGNALS ===
    user_prefs = await compute_user_preferences(user_id, pool)
    temporal = await compute_temporal_preferences(user_id, pool)
    feedback = await compute_feedback_enhanced_preferences(user_id, pool)
    seasonal = get_seasonal_context()
    anniversary = await get_anniversary_context(user_id, pool)
    budget_ctx = await compute_budget_context(user_id, pool)
    freshness = await get_freshness_context(user_id, pool)

    # Start building prompt
    prompt_parts = [
        "You are a creative date night planner specializing in personalized recommendations.",
        "Use ALL the context below to generate highly relevant, surprising, and delightful ideas."
    ]

    # === STANDARD PERSONALITY DATA ===
    prompt_parts.append("\n## User Profile")
    prompt_parts.append(f"- Personality Type: {user_row.get('personality_type') or 'romantic'}")
    prompt_parts.append(f"- Stated Interests: {', '.join(user_row.get('interests') or ['adventure', 'food'])}")
    prompt_parts.append(f"- Budget Preference: {user_row.get('budget_range') or 'moderate'}")
    prompt_parts.append(f"- Location Preference: {user_row.get('indoor_outdoor_preference') or 'both'}")

    # === BEHAVIORAL INSIGHTS ===
    if user_prefs.get('total_interactions', 0) >= 5:
        acceptance_rate = user_prefs.get('acceptance_rate', 0)
        interaction_count = user_prefs.get('total_interactions', 0)

        prompt_parts.append("\n## Behavioral Insights (from interaction history)")
        prompt_parts.append(f"- Accepted {int(acceptance_rate * 100)}% of {interaction_count} ideas")

        cat_scores = user_prefs.get('category_scores', {})
        if cat_scores:
            liked_cats = [cat for cat, score in sorted(cat_scores.items(), key=lambda x: x[1], reverse=True) if score > 0.5][:3]
            disliked_cats = [cat for cat, score in cat_scores.items() if score < 0.3]
            if liked_cats:
                prompt_parts.append(f"- Strong preference for: {', '.join(liked_cats)}")
            if disliked_cats:
                prompt_parts.append(f"- Low preference for: {', '.join(disliked_cats)}")

        budget_pref = user_prefs.get('budget_preference', {})
        if budget_pref:
            top_budget = max(budget_pref, key=budget_pref.get)
            prompt_parts.append(f"- Budget trending: {top_budget}")

        top_tags = user_prefs.get('top_tags', [])
        avoided_tags = user_prefs.get('avoided_tags', [])
        if top_tags:
            prompt_parts.append(f"- Favorite tags: {', '.join(top_tags)}")
        if avoided_tags:
            prompt_parts.append(f"- Rejected tags: {', '.join(avoided_tags)}")

        evolution = user_prefs.get('personality_evolution', '')
        if evolution:
            prompt_parts.append(f"- {evolution}")
    else:
        prompt_parts.append("\nNote: Limited interaction history. Use questionnaire data as baseline.")

    # === TEMPORAL INTELLIGENCE ===
    current_slot = get_current_time_slot()
    current_day = get_day_type()
    prompt_parts.append(f"\n## Temporal Context")
    prompt_parts.append(f"- Current time: {current_slot} on a {current_day}")

    if temporal.get('peak_activity_time'):
        prompt_parts.append(f"- User is most receptive during: {temporal['peak_activity_time']} on {temporal.get('peak_activity_day', 'any day')}")

    time_scores = temporal.get('time_slot_scores', {})
    if current_slot in time_scores:
        slot_rate = time_scores[current_slot]
        if slot_rate > 0.7:
            prompt_parts.append(f"- This is a HIGH-acceptance time slot ({int(slot_rate*100)}% accept rate)")
        elif slot_rate < 0.3:
            prompt_parts.append(f"- This is a LOW-acceptance time slot — suggest easy, appealing ideas")

    # === FEEDBACK DEPTH (Journal Ratings) ===
    if feedback.get('total_rated_dates', 0) > 0:
        prompt_parts.append(f"\n## Post-Date Feedback ({feedback['total_rated_dates']} rated dates)")
        if feedback.get('avg_rating'):
            prompt_parts.append(f"- Average date rating: {feedback['avg_rating']}/5")
        if feedback.get('high_rated_tags'):
            prompt_parts.append(f"- Tags from 4-5 star dates: {', '.join(feedback['high_rated_tags'][:5])}")
        if feedback.get('low_rated_tags'):
            prompt_parts.append(f"- Tags from 1-2 star dates (AVOID): {', '.join(feedback['low_rated_tags'][:3])}")
        if feedback.get('would_repeat_categories'):
            prompt_parts.append(f"- Would-repeat favorites: {', '.join(feedback['would_repeat_categories'][:3])}")

    # === SEASONAL & ANNIVERSARY AWARENESS ===
    prompt_parts.append(f"\n## Seasonal Context")
    prompt_parts.append(f"- Season: {seasonal['season'].capitalize()}")
    if seasonal.get('seasonal_boosts'):
        prompt_parts.append(f"- Seasonal boost tags: {', '.join(seasonal['seasonal_boosts'])}")

    if seasonal.get('upcoming_specials'):
        for special in seasonal['upcoming_specials']:
            prompt_parts.append(f"- UPCOMING: {special['name'].replace('_', ' ').title()} in {special['days_until']} days! Incorporate {', '.join(special['boost_tags'])} themes.")

    if anniversary.get('has_upcoming'):
        for event in anniversary['upcoming_events']:
            prompt_parts.append(f"- SPECIAL: {event['person']}'s {event['type']} in {event['days_until']} days! Make at least 1 idea special for this occasion.")

    # === BUDGET AWARENESS ===
    prompt_parts.append(f"\n## Budget Context")
    prompt_parts.append(f"- Month spent so far: ${budget_ctx['month_spent']:.0f}")
    if budget_ctx.get('avg_monthly_spend'):
        prompt_parts.append(f"- Average monthly: ${budget_ctx['avg_monthly_spend']:.0f}")
    prompt_parts.append(f"- Budget headroom: {budget_ctx['budget_headroom']}")
    prompt_parts.append(f"- Recommended budget level: {budget_ctx['recommended_budget']}")

    # === FRESHNESS DECAY ===
    if freshness.get('recently_done'):
        prompt_parts.append(f"\n## Freshness (avoid repetition)")
        prompt_parts.append(f"- Recently done ({FRESHNESS_DECAY_DAYS}d): {', '.join(freshness['recently_done'][:5])}")
        prompt_parts.append("- DO NOT suggest anything similar to these recent dates")

    if freshness.get('suppress_tags'):
        prompt_parts.append(f"- Over-used tags to suppress: {', '.join(freshness['suppress_tags'])}")

    if freshness.get('boost_novel_tags'):
        prompt_parts.append(f"- Haven't tried in 60+ days (consider resurfacing): {', '.join(freshness['boost_novel_tags'])}")

    # === PARTNER COMPATIBILITY ===
    if partner_id:
        compat = await compute_partner_compatibility(user_id, partner_id, pool)

        prompt_parts.append(f"\n## Couple Mode - Compatibility: {compat.get('compatibility_score')}/100")

        shared = compat.get('shared_categories', [])
        if shared:
            prompt_parts.append(f"- Shared preferences: {', '.join(shared)}")

        conflicts = compat.get('conflict_categories', [])
        if conflicts:
            prompt_parts.append(f"- Avoid conflicts: {', '.join(conflicts)}")

    # === MOOD MODIFIER ===
    if mood and mood.lower() in MOOD_WEIGHTS:
        prompt_parts.append(f"\n## Current Mood: {mood}")
        mood_desc = MOOD_OPTIONS.get(mood.lower(), "")
        if mood_desc:
            prompt_parts.append(f"Context: {mood_desc}")

    # === ENERGY LEVEL ===
    if energy and energy.lower() in ENERGY_LEVELS:
        energy_info = ENERGY_LEVELS[energy.lower()]
        prompt_parts.append(f"\n## Energy Level: {energy.upper()} — {energy_info['description']}")
        if energy_info.get('boost'):
            prompt_parts.append(f"- Boost categories: {', '.join(energy_info['boost'].keys())}")
        if energy_info.get('suppress'):
            prompt_parts.append(f"- Suppress categories: {', '.join(energy_info['suppress'].keys())}")

    # === WEATHER CONTEXT ===
    if weather and weather.get('condition') != 'unknown':
        prompt_parts.append(f"\n## Weather: {weather.get('description', 'Unknown')}")
        if not weather.get('is_outdoor_friendly'):
            prompt_parts.append("Weather not ideal for outdoor. Prioritize indoor.")
        else:
            prompt_parts.append("Nice weather. Consider outdoor activities.")

    # === WILDCARD INJECTION ===
    wildcard_prompt = ""
    if should_inject_wildcard(
        user_prefs.get('acceptance_rate', 0),
        user_prefs.get('total_interactions', 0)
    ):
        wildcard_prompt = get_wildcard_prompt_addition(
            user_prefs.get('avoided_tags', []),
            user_prefs.get('top_tags', [])
        )

    # === GENERATION INSTRUCTIONS ===
    prompt_parts.append("\n## Generate 5 date ideas following these rules:")
    prompt_parts.append("1. Match behavioral preferences and current context")
    prompt_parts.append("2. Respect budget headroom")
    prompt_parts.append("3. Avoid recently-done ideas and over-used tags")
    prompt_parts.append("4. Include seasonal/anniversary-appropriate ideas if applicable")
    prompt_parts.append("5. Match energy level and time of day")

    if avoided_tags:
        prompt_parts.append(f"6. NEVER use these tags: {', '.join(avoided_tags)}")
    if feedback.get('low_rated_tags'):
        prompt_parts.append(f"7. AVOID low-rated tags: {', '.join(feedback['low_rated_tags'])}")

    if wildcard_prompt:
        prompt_parts.append(wildcard_prompt)

    prompt_parts.append("""
Return ONLY a valid JSON array (no markdown, no explanation):
[
  {
    "title": "Date idea title",
    "description": "Detailed 2-3 sentence description",
    "category": "romantic|adventure|foodie|creative|relaxing|fun|cultural|active",
    "budget": "low|medium|high",
    "estimated_cost": 25,
    "duration": "duration estimate",
    "location_type": "indoor|outdoor|both",
    "best_time": "morning|afternoon|evening|night",
    "tags": ["tag1", "tag2", "tag3"],
    "source": "ai-generated",
    "why_personalized": "Brief explanation of why this matches the user's profile",
    "wildcard": false
  }
]""")

    return "\n".join(prompt_parts)
