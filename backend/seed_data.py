"""
Arrow Backend - Seed Data
Curated date ideas for production
"""

import asyncio
from database import async_session_maker, init_db
from models import DateIdea

# Curated date ideas organized by category
DATE_IDEAS = [
    # 🍽️ Food & Dining
    {
        "title": "Sunset Rooftop Dinner",
        "description": "Book a table at a rooftop restaurant and watch the sunset together while enjoying amazing food and conversation.",
        "category": "dining",
        "budget_estimate": "high",
        "duration": "2-3 hours",
        "location_type": "outdoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["romantic", "dinner", "sunset", "city views"]
    },
    {
        "title": "Progressive Dinner Date",
        "description": "Visit 3-4 restaurants in one night - appetizers at one, main course at another, and dessert somewhere special.",
        "category": "dining",
        "budget_estimate": "high",
        "duration": "4-5 hours",
        "location_type": "both",
        "is_trending": True,
        "tags": ["foodie", "adventure", "exploring"]
    },
    {
        "title": "Cooking Class for Two",
        "description": "Learn to make pasta, sushi, or your favorite cuisine together. Take home new skills and great memories.",
        "category": "dining",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["cooking", "learning", "interactive", "fun"]
    },
    {
        "title": "Food Truck Festival Adventure",
        "description": "Hit up your local food truck park and share bites from different cuisines. Casual, fun, and delicious!",
        "category": "dining",
        "budget_estimate": "low",
        "duration": "2-3 hours",
        "location_type": "outdoor",
        "tags": ["casual", "street food", "variety"]
    },
    {
        "title": "Wine & Cheese Night",
        "description": "Visit a wine bar or set up at home with a selection of wines and artisanal cheeses. Perfect for deep conversations.",
        "category": "dining",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "both",
        "tags": ["romantic", "relaxed", "classy"]
    },
    {
        "title": "Breakfast in Bed Day",
        "description": "Wake up early, make a fancy breakfast together, and spend the morning in bed with coffee and conversation.",
        "category": "dining",
        "budget_estimate": "low",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "tags": ["cozy", "morning", "intimate"]
    },
    
    # 🎨 Creative & Arts
    {
        "title": "Pottery Class Date",
        "description": "Channel your inner Ghost movie moment! Learn to make pottery together and keep your creations.",
        "category": "creative",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["hands-on", "creative", "memorable"]
    },
    {
        "title": "Paint & Sip Night",
        "description": "Join a painting class with wine. No experience needed - just fun, laughter, and creating art together.",
        "category": "creative",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "is_trending": True,
        "tags": ["art", "wine", "social", "fun"]
    },
    {
        "title": "DIY Candle Making",
        "description": "Create custom scented candles together. Choose your scents, colors, and take home your creations.",
        "category": "creative",
        "budget_estimate": "medium",
        "duration": "2 hours",
        "location_type": "indoor",
        "tags": ["crafts", "cozy", "takeaway"]
    },
    {
        "title": "Couples Photography Session",
        "description": "Book a photographer for a fun couples shoot. Golden hour recommended for magical photos!",
        "category": "creative",
        "budget_estimate": "high",
        "duration": "1-2 hours",
        "location_type": "outdoor",
        "tags": ["memories", "photos", "special"]
    },
    {
        "title": "Street Art Walking Tour",
        "description": "Explore murals and graffiti art in your city. Many cities have self-guided tours or apps.",
        "category": "creative",
        "budget_estimate": "free",
        "duration": "2-3 hours",
        "location_type": "outdoor",
        "tags": ["walking", "art", "urban", "free"]
    },
    
    # 🌿 Outdoor & Nature
    {
        "title": "Sunrise Hike & Breakfast",
        "description": "Wake up early for a scenic hike and pack a breakfast picnic to enjoy at the summit.",
        "category": "outdoor",
        "budget_estimate": "low",
        "duration": "4-5 hours",
        "location_type": "outdoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["active", "nature", "morning", "adventure"]
    },
    {
        "title": "Beach Sunset Picnic",
        "description": "Pack a blanket, wine, cheese, and snacks. Find a quiet spot and watch the sunset over the water.",
        "category": "outdoor",
        "budget_estimate": "low",
        "duration": "2-3 hours",
        "location_type": "outdoor",
        "is_trending": True,
        "tags": ["romantic", "beach", "sunset", "picnic"]
    },
    {
        "title": "Stargazing Night",
        "description": "Drive away from city lights, bring blankets and hot cocoa, and spend the night looking at stars.",
        "category": "outdoor",
        "budget_estimate": "low",
        "duration": "3-4 hours",
        "location_type": "outdoor",
        "is_trending": True,
        "tags": ["romantic", "night", "peaceful", "nature"]
    },
    {
        "title": "Kayaking or Paddleboarding",
        "description": "Rent kayaks or paddleboards and explore a lake or calm waters together. Great workout and fun!",
        "category": "outdoor",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "outdoor",
        "tags": ["active", "water", "adventure", "summer"]
    },
    {
        "title": "Botanical Garden Stroll",
        "description": "Wander through beautiful gardens, admire flowers, and find a bench for quiet conversation.",
        "category": "outdoor",
        "budget_estimate": "low",
        "duration": "2-3 hours",
        "location_type": "outdoor",
        "tags": ["peaceful", "flowers", "walking", "beautiful"]
    },
    {
        "title": "Farmers Market Morning",
        "description": "Browse local produce, taste samples, grab coffee, and pick ingredients to cook together later.",
        "category": "outdoor",
        "budget_estimate": "low",
        "duration": "2 hours",
        "location_type": "outdoor",
        "tags": ["morning", "local", "food", "casual"]
    },
    
    # 🎮 Fun & Games
    {
        "title": "Arcade & Pizza Night",
        "description": "Hit up a retro arcade or modern gaming bar. Compete in games, win prizes, and grab pizza after.",
        "category": "games",
        "budget_estimate": "medium",
        "duration": "3-4 hours",
        "location_type": "indoor",
        "is_trending": True,
        "tags": ["fun", "competitive", "nostalgic", "casual"]
    },
    {
        "title": "Escape Room Challenge",
        "description": "Test your teamwork and problem-solving skills. Book a themed room and try to escape together!",
        "category": "games",
        "budget_estimate": "medium",
        "duration": "1-2 hours",
        "location_type": "indoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["teamwork", "puzzles", "exciting", "unique"]
    },
    {
        "title": "Mini Golf & Ice Cream",
        "description": "Classic and adorable! Play a round of mini golf and celebrate with ice cream after.",
        "category": "games",
        "budget_estimate": "low",
        "duration": "2 hours",
        "location_type": "outdoor",
        "tags": ["classic", "fun", "casual", "sweet"]
    },
    {
        "title": "Board Game Café Date",
        "description": "Visit a board game café with hundreds of games to choose from. Order snacks and play for hours.",
        "category": "games",
        "budget_estimate": "low",
        "duration": "2-4 hours",
        "location_type": "indoor",
        "tags": ["cozy", "games", "casual", "rainy day"]
    },
    {
        "title": "Bowling Night",
        "description": "Grab some bowling shoes, order nachos, and have a friendly competition with gutter balls and strikes.",
        "category": "games",
        "budget_estimate": "medium",
        "duration": "2 hours",
        "location_type": "indoor",
        "tags": ["classic", "fun", "competitive"]
    },
    {
        "title": "Trivia Night at a Bar",
        "description": "Team up for pub trivia! Test your knowledge, enjoy drinks, and maybe win some prizes.",
        "category": "games",
        "budget_estimate": "low",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "tags": ["social", "competitive", "drinks", "fun"]
    },
    
    # 🎬 Entertainment
    {
        "title": "Drive-In Movie Night",
        "description": "Find a drive-in theater, bring blankets and snacks, and watch a movie under the stars.",
        "category": "entertainment",
        "budget_estimate": "low",
        "duration": "3-4 hours",
        "location_type": "outdoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["retro", "movies", "cozy", "unique"]
    },
    {
        "title": "Comedy Show Night",
        "description": "Laugh together at a live comedy show. Check local venues for stand-up or improv nights.",
        "category": "entertainment",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "is_trending": True,
        "tags": ["laughter", "live", "fun", "night out"]
    },
    {
        "title": "Concert Date",
        "description": "See your favorite artist or discover someone new. The shared experience creates lasting memories.",
        "category": "entertainment",
        "budget_estimate": "high",
        "duration": "3-4 hours",
        "location_type": "both",
        "is_trending": True,
        "tags": ["music", "live", "energy", "memorable"]
    },
    {
        "title": "Jazz Bar Evening",
        "description": "Find a cozy jazz bar, order classic cocktails, and enjoy live music in an intimate setting.",
        "category": "entertainment",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "tags": ["music", "classy", "romantic", "drinks"]
    },
    {
        "title": "Movie Marathon at Home",
        "description": "Pick a theme (trilogy, director, genre), make popcorn, build a blanket fort, and binge watch.",
        "category": "entertainment",
        "budget_estimate": "free",
        "duration": "4-6 hours",
        "location_type": "indoor",
        "tags": ["cozy", "home", "movies", "lazy day"]
    },
    
    # 💆 Wellness & Relaxation
    {
        "title": "Couples Spa Day",
        "description": "Book side-by-side massages, enjoy the sauna, and spend the day in ultimate relaxation together.",
        "category": "wellness",
        "budget_estimate": "high",
        "duration": "3-4 hours",
        "location_type": "indoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["relaxation", "luxury", "pampering", "romantic"]
    },
    {
        "title": "Yoga in the Park",
        "description": "Find a free outdoor yoga class or bring your own mats. Stretch, breathe, and relax together.",
        "category": "wellness",
        "budget_estimate": "free",
        "duration": "1-2 hours",
        "location_type": "outdoor",
        "tags": ["healthy", "peaceful", "morning", "free"]
    },
    {
        "title": "Hot Springs Visit",
        "description": "Soak in natural hot springs surrounded by nature. Perfect for deep relaxation and conversation.",
        "category": "wellness",
        "budget_estimate": "medium",
        "duration": "3-4 hours",
        "location_type": "outdoor",
        "tags": ["nature", "relaxation", "unique", "romantic"]
    },
    {
        "title": "At-Home Spa Night",
        "description": "Face masks, candles, bath bombs, and massages. Create a spa experience without leaving home.",
        "category": "wellness",
        "budget_estimate": "low",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "tags": ["cozy", "intimate", "relaxation", "budget-friendly"]
    },
    
    # 🚀 Adventure & Unique
    {
        "title": "Hot Air Balloon Ride",
        "description": "Float above the landscape at sunrise. A bucket-list experience that's incredibly romantic.",
        "category": "adventure",
        "budget_estimate": "luxury",
        "duration": "3-4 hours",
        "location_type": "outdoor",
        "is_trending": True,
        "is_featured": True,
        "tags": ["bucket list", "unique", "romantic", "views"]
    },
    {
        "title": "Helicopter City Tour",
        "description": "See your city from above with a scenic helicopter ride. Perfect for special occasions.",
        "category": "adventure",
        "budget_estimate": "luxury",
        "duration": "1-2 hours",
        "location_type": "outdoor",
        "tags": ["luxury", "views", "special", "unforgettable"]
    },
    {
        "title": "Go-Kart Racing",
        "description": "Feel the adrenaline as you race around the track. Loser buys dinner!",
        "category": "adventure",
        "budget_estimate": "medium",
        "duration": "1-2 hours",
        "location_type": "indoor",
        "is_trending": True,
        "tags": ["adrenaline", "competitive", "fun", "exciting"]
    },
    {
        "title": "Rock Climbing Gym",
        "description": "Encourage each other as you climb the walls. Great for building trust and having fun.",
        "category": "adventure",
        "budget_estimate": "medium",
        "duration": "2-3 hours",
        "location_type": "indoor",
        "tags": ["active", "challenge", "teamwork", "fitness"]
    },
    {
        "title": "Spontaneous Road Trip",
        "description": "Pick a direction and drive. Stop at interesting places along the way. Adventure awaits!",
        "category": "adventure",
        "budget_estimate": "medium",
        "duration": "full day",
        "location_type": "outdoor",
        "is_trending": True,
        "tags": ["spontaneous", "adventure", "exploring", "freedom"]
    },
    {
        "title": "Take a Dance Class",
        "description": "Learn salsa, swing, or ballroom dancing together. Awkward at first, romantic by the end!",
        "category": "adventure",
        "budget_estimate": "medium",
        "duration": "1-2 hours",
        "location_type": "indoor",
        "tags": ["dancing", "learning", "romantic", "fun"]
    },
    
    # 🏠 Cozy & Home
    {
        "title": "Backyard Camping",
        "description": "Set up a tent in your backyard, make s'mores, and sleep under the stars without going far.",
        "category": "home",
        "budget_estimate": "low",
        "duration": "overnight",
        "location_type": "outdoor",
        "is_trending": True,
        "tags": ["cozy", "adventure", "budget-friendly", "unique"]
    },
    {
        "title": "Theme Night at Home",
        "description": "Pick a country, cook its cuisine, play its music, and watch a film from there. Travel without leaving!",
        "category": "home",
        "budget_estimate": "low",
        "duration": "4-5 hours",
        "location_type": "indoor",
        "tags": ["creative", "cultural", "cooking", "movies"]
    },
    {
        "title": "Build a Blanket Fort",
        "description": "Never too old for this! Build an epic fort, fill it with snacks, and watch movies inside.",
        "category": "home",
        "budget_estimate": "free",
        "duration": "all day",
        "location_type": "indoor",
        "tags": ["playful", "cozy", "nostalgic", "fun"]
    },
    {
        "title": "Cook a Fancy Dinner Together",
        "description": "Pick a challenging recipe, shop for ingredients, and cook a restaurant-quality meal at home.",
        "category": "home",
        "budget_estimate": "medium",
        "duration": "3-4 hours",
        "location_type": "indoor",
        "tags": ["cooking", "teamwork", "romantic", "delicious"]
    },
    {
        "title": "Game Tournament Night",
        "description": "Set up a bracket with video games, card games, or board games. Keep score and crown a champion!",
        "category": "home",
        "budget_estimate": "free",
        "duration": "3-4 hours",
        "location_type": "indoor",
        "tags": ["competitive", "games", "fun", "cozy"]
    },
]


async def seed_date_ideas():
    """Seed the database with curated date ideas"""
    print("🌱 Seeding date ideas...")
    
    await init_db()
    
    async with async_session_maker() as session:
        # Check if already seeded
        from sqlalchemy import select, func
        count = await session.scalar(select(func.count()).select_from(DateIdea))
        
        if count and count > 0:
            print(f"Database already has {count} date ideas. Skipping seed.")
            return
        
        # Insert all ideas
        for idea_data in DATE_IDEAS:
            idea = DateIdea(**idea_data)
            session.add(idea)
        
        await session.commit()
        print(f"✅ Successfully seeded {len(DATE_IDEAS)} date ideas!")


if __name__ == "__main__":
    asyncio.run(seed_date_ideas())
