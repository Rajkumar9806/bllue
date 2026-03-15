# Arrow App — Change Log

All notable changes to this project are documented here.

---

## [Sprint 3/14/26] — 2026-03-15

### Rebrand: bllue → Arrow
- **Status:** Complete
- **Scope:** Full app rename from "bllue" to "Arrow" across entire codebase.
- **Files Changed:** 11 backend Python files, 6 documentation files. All user-facing text, API titles, bundle IDs (`com.arrow.app`), SMS messages, notification channels, deployment configs updated.
- **New App Icon:** Cupid's Arrow + Heart design. Generated at 1024x1024 (App Store), adaptive icon (Android), splash screen (200x200), favicon (48x48). Coral-pink gradient with white heart pierced by diagonal arrow.

### Task 1: Remove Stock Images & Build Image Management Dashboard
- **Status:** Complete
- **Scope:** Replaced hardcoded Unsplash URLs with database-driven images; built a full admin web UI for K & P to manage images per date idea, add/edit/delete ideas with preferences.
- **Files Changed:**
  - `backend/admin.py` — **NEW** (1,224 lines). Admin dashboard with REST API + HTML UI. Endpoints: list/create/update/delete ideas, update images, view stats. Responsive UI with filtering, search, pagination, edit modals, image preview.
  - `backend/main.py` — Imported admin router, added `source`, `updated_at`, `updated_by` columns to `date_ideas` table, mounted admin at `/admin/`.
- **How to access:** Navigate to `http://<host>:8000/admin/`

### Task 2: Add Claude & OpenAI as Switchable AI Providers
- **Status:** Complete
- **Scope:** Integrated Anthropic Claude and OpenAI alongside Gemini; provider is switchable via env var or runtime API.
- **Files Changed:**
  - `backend/ai_providers.py` — **NEW** (251 lines). Modular AI provider system with `GeminiProvider`, `ClaudeProvider`, `OpenAIProvider` classes. Factory pattern, all using raw httpx (no SDKs).
  - `backend/main.py` — Added `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` env vars. Refactored `generate_ai_date_ideas()` and `fetch_trending_date_ideas()` to use provider system. New endpoints: `GET/PUT /api/ai/provider`, `GET /api/ai/providers`.
- **Config:** Set `AI_PROVIDER=claude` or `AI_PROVIDER=openai` in `.env` to switch. Default: `gemini`.

### Task 3: AI Idea Quality Check / Approval Queue
- **Status:** Complete
- **Scope:** AI-generated ideas now land in a pending review queue; K & P can approve/reject before ideas reach users.
- **Files Changed:**
  - `backend/review_queue.py` — **NEW** (981 lines). Review queue with REST API + HTML UI. `idea_reviews` table with status tracking. Endpoints: list queue, approve, reject, generate batch, stats. Card-based UI with reviewer name persistence.
  - `backend/main.py` — Imported review router, added `require_review` parameter to `generate_ai_date_ideas()`, mounted at `/admin/review/`.
- **How to access:** Navigate to `http://<host>:8000/admin/review/`
- **Flow:** Generate ideas -> Queue (pending) -> K/P approve/reject -> Approved ideas move to `date_ideas` table.

### Task 4: Fix Date Button on "Add Special Date"
- **Status:** Complete
- **Root Cause:** The production backend (`main.py` / PostgreSQL) had NO occasions endpoints — they only existed in `server.py` (MongoDB alternative). Frontend was hitting non-existent endpoints.
- **Files Changed:**
  - `backend/main.py` — Added `occasions` table, `OccasionCreate`/`OccasionUpdate`/`Occasion` models, `parse_date_string()` helper (supports 7+ date formats), and 5 new endpoints:
    - `POST /api/occasions/add` — Create occasion
    - `GET /api/occasions` — List user's occasions
    - `GET /api/occasions/upcoming` — Upcoming occasions (next N days)
    - `PUT /api/occasions/{id}` — Update occasion
    - `DELETE /api/occasions/{id}` — Delete occasion
- **Key fix:** Flexible date string parsing accepts ISO, US, EU formats from mobile date pickers.

### Task 5: Daily/Weekly Featured Date Idea
- **Status:** Complete
- **Scope:** Added "idea of the day" and "idea of the week" feature with both auto-selection and manual curation.
- **Files Changed:**
  - `backend/main.py` — Added `featured_ideas` table (with unique constraint on type+date), 3 new endpoints:
    - `GET /api/date-ideas/daily` — Returns today's featured idea (manual or auto-picked)
    - `GET /api/date-ideas/weekly` — Returns this week's featured idea
    - `POST /api/date-ideas/feature` — Manually set a featured idea for any date
- **Auto-selection:** Deterministic pick based on date seed — same idea shows all day/week without randomness.

### Task 6: Accept/Reject Tracking & User Profile Stats
- **Status:** Complete
- **Scope:** Track user accept/reject interactions on ideas; build preference profile with stats.
- **Files Changed:**
  - `backend/main.py` — Added `idea_interactions` table (unique per user+idea), `IdeaInteraction` model, 4 new endpoints:
    - `POST /api/ideas/accept` — Record acceptance
    - `POST /api/ideas/reject` — Record rejection
    - `GET /api/ideas/interactions` — View interaction history (filterable)
    - `GET /api/ideas/stats` — Preference profile: accepted/rejected counts, acceptance rate, top categories, recent accepts

---

## Summary of New Files

| File | Lines | Purpose |
|------|-------|---------|
| `backend/admin.py` | 1,224 | Image management dashboard (API + UI) |
| `backend/ai_providers.py` | 251 | Modular AI provider system (Gemini/Claude/OpenAI) |
| `backend/review_queue.py` | 981 | Idea approval queue (API + UI) |
| `CHANGELOG.md` | — | This file |

## Summary of Modified Files

| File | Original Lines | New Lines | Changes |
|------|---------------|-----------|---------|
| `backend/main.py` | 981 | 1,641 | +660 lines (6 tasks worth of features) |

## New Database Tables

| Table | Purpose |
|-------|---------|
| `idea_reviews` | AI idea review/approval queue |
| `featured_ideas` | Daily/weekly featured idea selections |
| `idea_interactions` | User accept/reject tracking |
| `occasions` | Special occasion management |

## New API Endpoints (22 total)

| Category | Endpoints |
|----------|-----------|
| Admin Dashboard | 8 endpoints at `/admin/` |
| Review Queue | 7 endpoints at `/admin/review/` |
| AI Provider | 3 endpoints at `/api/ai/` |
| Occasions | 5 endpoints at `/api/occasions/` |
| Featured Ideas | 3 endpoints at `/api/date-ideas/daily`, `/weekly`, `/feature` |
| Idea Interactions | 4 endpoints at `/api/ideas/` |

---

## [Premium Features] — 2026-03-15

### Phase 1: Partner Pairing System
- **Status:** Complete
- **Files Created:** `backend/partner.py` (741 lines)
- **Database Tables:** `partner_connections`, `shared_wishlist`
- **Endpoints (8):**
  - `POST /api/partner/invite` — Generate 6-char invite code (format: XXX-XXX)
  - `POST /api/partner/accept` — Accept invite code, link partners
  - `GET /api/partner/status` — Get current partnership info
  - `DELETE /api/partner/disconnect` — End partnership
  - `POST /api/partner/wishlist/share` — Share idea with partner
  - `GET /api/partner/wishlist` — Get shared wishlist
  - `GET /api/partner/preferences` — Combined preference profile for AI
  - `GET /api/partner/compatibility` — Compatibility report (0-100 score)
- **Features:** Invite code generation, partner linking, shared wishlists, compatibility scoring, combined preference data for AI prompts, prevents self-invite and duplicate partnerships.

### Phase 2: Smart Preference Algorithm
- **Status:** Complete
- **Files Created:** `backend/smart_algorithm.py` (635 lines)
- **Endpoints (4):**
  - `GET /api/recommendations/smart` — AI ideas tuned by behavioral learning (accepts `?mood=`, `?lat=`, `?lon=`)
  - `GET /api/recommendations/preferences` — User's computed preference profile
  - `GET /api/recommendations/mood-options` — Available mood selections
  - `GET /api/recommendations/partner-compatibility` — Couple compatibility analysis
- **Algorithm Features:**
  - Weighted scoring from accept/reject history (category affinity 0.0-1.0)
  - Budget and location pattern analysis
  - Top liked vs avoided tags
  - Personality evolution detection (stated vs actual behavior)
  - Confidence levels: Low (<5 interactions) → Medium (5-15) → High (15+)
  - 6 mood types with weighted category multipliers
  - Weather-aware filtering (OpenWeatherMap integration, graceful fallback)
  - Partner compatibility scoring with shared/compromise/conflict categories
  - Dynamic AI prompt builder that injects behavioral insights

### Phase 3: Date Memory Journal
- **Status:** Complete
- **Files Created:** `backend/journal.py` (1,089 lines)
- **Database Tables:** `date_memories`, `date_milestones`
- **Endpoints (9):**
  - `POST /api/journal/entry` — Create post-date journal entry (rating, mood, notes, photos, cost)
  - `GET /api/journal/entries` — List entries with filters (rating, mood, tag) + pagination
  - `GET /api/journal/entry/{id}` — Get single entry
  - `PUT /api/journal/entry/{id}` — Update entry
  - `DELETE /api/journal/entry/{id}` — Delete entry
  - `GET /api/journal/timeline` — Monthly timeline with per-month stats
  - `GET /api/journal/on-this-day` — "On this day" memories from previous years
  - `GET /api/journal/stats` — Dashboard: total dates, avg rating, spending, streaks, trends
  - `GET /api/journal/milestones` — Earned achievements/badges
- **12 Auto-Awarded Milestones:**
  - First Date, Regular Dater (5), Date Night Pro (10), Half Century (50)
  - Five Stars (first 5-star), Adventurer (3 adventure), Foodie Couple (3 foodie), Creative Souls (3 creative)
  - Budget Friendly (5 under $30), Big Spender (over $200)
  - Streak Week (3 consecutive), Anniversary (entry on occasion date)

---

## [Algorithm v2 + Idea Seeding] — 2026-03-15

### Smart Algorithm v2 — Enhanced Intelligence
- **Status:** Complete
- **File Modified:** `backend/smart_algorithm.py` (635 → ~800 lines, rewritten)
- **New Algorithm Signals:**
  1. **Temporal Intelligence** — Tracks when users accept/reject ideas (time-of-day, day-of-week). Identifies peak receptivity windows (e.g., "user accepts 85% in evenings on weekends"). Adjusts prompt if current time is a low-acceptance slot.
  2. **Feedback Depth** — Post-date journal ratings (1-5 stars) feed back into preferences. A 5-star date's tags get massive weight; a 2-star accepted date is a weak signal. Also tracks "would repeat" favorites.
  3. **Seasonal & Anniversary Awareness** — Detects current season and boosts seasonal tags (e.g., "outdoor" in summer, "cozy" in winter). Scans occasions table and user profile for upcoming anniversaries/birthdays within 14 days. Auto-prompts special-occasion ideas.
  4. **Budget Pacing** — Tracks monthly spending from journal entries. Compares to 3-month average. Recommends budget level based on headroom: plenty → splurge, tight → budget-friendly.
  5. **Repeat & Freshness Decay** — Suppresses ideas similar to dates done in the last 21 days. Detects over-used tags (3+ times recently). Resurfaces forgotten categories not used in 60+ days.
  6. **Energy Level Matching** — New `energy` parameter (low/medium/high). Low energy boosts relaxing/indoor, suppresses adventure/active. High energy does the opposite.
  7. **Surprise Wildcard Factor** — 15-25% chance of injecting one "wildcard" idea from an unexplored category. More likely for users with high acceptance rates (they're open to surprises).
  8. **Recency Weighting** — Recent interactions count more than old ones (exponential decay). Prevents stale preferences from dominating.

### Idea Seeding Engine
- **Status:** Complete
- **File Created:** `backend/idea_seeder.py` (~700 lines)
- **Database Tables:** `user_submitted_ideas`, `seed_jobs`
- **Admin Dashboard:** `http://<host>:8000/admin/seeder/`
- **Seeding Strategies:**
  1. **Curated Packs (9 packs, 76 hand-written ideas):**
     - Free & Fabulous (10 ideas, $0 budget)
     - Luxury Splurge (8 ideas, high-end)
     - Stay Home Dates (10 ideas, indoor)
     - Adventure Seekers (8 ideas, adrenaline)
     - Culture & Connection (8 ideas, arts/learning)
     - Spring Awakening (5 ideas)
     - Summer Heat (5 ideas)
     - Autumn Coziness (5 ideas)
     - Winter Warmth (5 ideas)
  2. **AI Bulk Generation** — Generate 5-50 ideas per batch via any configured AI provider. Supports category, budget, and theme filters.
  3. **Category Gap Analysis** — Auto-detects under-represented categories and generates ideas to fill them.
  4. **User Idea Submissions** — Users can submit ideas; admin reviews and approves into main database.
  5. **Duplicate Detection** — Title-based dedup prevents repeated ideas on bulk insert.
  6. **Job Tracking** — Every seed operation logged with status, counts, and timestamps.

- **Endpoints (13):**
  - `POST /admin/seeder/install-pack` — Install a single curated pack
  - `POST /admin/seeder/install-all-packs` — Install all 9 packs at once
  - `POST /admin/seeder/generate-ai` — AI bulk generate (with filters)
  - `POST /admin/seeder/fill-gaps` — Auto-detect and fill category gaps
  - `GET /admin/seeder/gaps` — View category distribution analysis
  - `GET /admin/seeder/packs` — List available packs
  - `GET /admin/seeder/jobs` — View seed job history
  - `POST /api/ideas/submit` — User submits an idea
  - `GET /admin/seeder/submissions` — View user submissions
  - `POST /admin/seeder/submissions/{id}/approve` — Approve submission
  - `POST /admin/seeder/submissions/{id}/reject` — Reject submission
  - `GET /admin/seeder` — Admin dashboard (HTML UI)

### New Algorithm API Endpoints (7)
- `GET /api/recommendations/energy-options` — Energy level options
- `GET /api/recommendations/temporal` — User's time pattern insights
- `GET /api/recommendations/feedback` — Journal-derived preference insights
- `GET /api/recommendations/seasonal` — Seasonal context + upcoming events
- `GET /api/recommendations/budget` — Monthly budget pacing insights
- `GET /api/recommendations/freshness` — Recently done ideas + suppression
- `GET /api/recommendations/full-profile` — Complete algorithm DNA (all signals combined)

### Updated Endpoint
- `GET /api/recommendations/smart` — Now accepts `?energy=low|medium|high` parameter. Algorithm version upgraded to `smart_v2` with all new signals active.

---

## [Retail Partners + Live Events + Multi-Source Seeding] — 2026-03-15

### Retail Partner System (Revenue Engine)
- **Status:** Complete
- **File Created:** `backend/retail_partners.py` (~700 lines)
- **Database Tables:** `retail_partners`, `retailer_ideas`, `retail_analytics`
- **Revenue Model:** 3-tier system
  - **Free** ($0/mo) — 3 idea listings, basic analytics, no boost
  - **Premium** ($99/mo) — 10 listings, 2x boost in recommendations, standard analytics
  - **Elite** ($249/mo) — 25 listings, 4x boost, full analytics with conversion tracking
- **Key Features:**
  - Partner onboarding with full business profile (address, photos, hours, offers)
  - Tier-based idea boosting in search and recommendations (paid partners appear first)
  - Special offers system ("10% off for Arrow users", "Free dessert for couples")
  - Analytics tracking: views, clicks, bookings, CTR, conversion rate
  - Stock image detection on all partner photos — auto-flags for admin review
  - Admin dashboard at `/admin/retail` with revenue overview
- **Endpoints (15):**
  - `POST /api/retail/onboard` — Partner onboarding
  - `GET /api/retail/partners` — List partners (paid-first sorting)
  - `GET /api/retail/partner/{id}` — Partner profile + linked ideas
  - `PUT /api/retail/partner/{id}` — Update partner
  - `DELETE /api/retail/partner/{id}` — Deactivate partner
  - `POST /api/retail/idea` — Create partner-linked date idea
  - `GET /api/retail/ideas` — Browse partner ideas (boosted)
  - `GET /api/retail/tiers` — Tier pricing info
  - `POST /api/retail/partner/{id}/upgrade` — Upgrade tier
  - `POST /api/retail/analytics/track` — Track view/click/booking
  - `GET /api/retail/analytics/{id}` — Partner analytics (tier-gated)
  - `GET /admin/retail/image-review` — Pending image reviews
  - `POST /admin/retail/image-review/{id}/approve` — Approve images
  - `POST /admin/retail/image-review/{id}/reject` — Reject images
  - `POST /admin/retail/image-review/{id}/update-image` — Admin replaces image
  - `GET /admin/retail` — Admin dashboard

### Live Events & Multi-Source Scraper
- **Status:** Complete
- **File Created:** `backend/live_events.py` (~650 lines)
- **Database Tables:** `live_events`, `scrape_jobs`
- **Data Sources:**
  1. **Ticketmaster API** — Real concerts, comedy shows, theater, sports in Nashville. Auto-maps categories and budget levels. Official event images (not stock).
  2. **AI Social Trends** — AI generates locally-specific trending ideas from TikTok/Instagram culture. Uses REAL Nashville venue names, neighborhoods, restaurants. Explicitly prohibits stock image URLs.
  3. **Seasonal/Festive Local** — AI generates season-appropriate local events (farmers markets, holiday events, festivals, outdoor activities for current month/weather).
- **Image Validation Pipeline:**
  - Every image URL checked against 15 known stock photo domains
  - Stock images auto-flagged as `pending_review`
  - Missing images flagged as `needs_image`
  - Admin can: approve, reject, or replace-and-approve
  - Only `approved` images shown to users
- **City Expansion Ready:** Nashville-first with configs for Austin, Denver. Add new cities by adding to `CITY_CONFIGS` dict.
- **Endpoints (13):**
  - `POST /admin/events/scrape/ticketmaster` — Scrape Ticketmaster
  - `POST /admin/events/scrape/social-trends` — AI social trend generation
  - `POST /admin/events/scrape/seasonal` — AI seasonal event generation
  - `POST /admin/events/scrape/all` — Run all scrapers at once
  - `GET /api/events` — User-facing events feed (approved images only)
  - `GET /admin/events/image-review` — Pending image reviews
  - `POST /admin/events/{id}/approve-image` — Approve
  - `POST /admin/events/{id}/update-image` — Replace + approve
  - `POST /admin/events/{id}/reject-image` — Reject
  - `GET /admin/events/scrape-history` — Scrape job log
  - `GET /admin/events/stats` — Event database statistics

---

## [Daily Pipeline Automation] — 2026-03-15

### Automated Daily Idea Generation Pipeline
- **Status:** Complete (wired into main.py)
- **File Created:** `backend/daily_pipeline.py` (~550 lines)
- **Database Tables:** Uses existing tables (`date_ideas`, `live_events`, `retail_partners`, `scrape_jobs`)
- **Admin Dashboard:** `http://<host>:8000/admin/pipeline`
- **10-Stage Pipeline (runs every 24 hours automatically):**
  1. **Ticketmaster Scrape** — Fetches latest Nashville concerts, shows, and sports events
  2. **Social Trends** (3 batches × 15 ideas = 45) — AI-generated trending date ideas inspired by TikTok/Instagram culture
  3. **Seasonal Local** (10 ideas) — Month/season-appropriate events and activities
  4. **Category Variety** (8 categories × 15 ideas = 120) — Bulk generation across all date categories
  5. **Themed Batch** (10 ideas) — Daily rotating theme from 14-theme library (Mystery Monday, Taco Tuesday, etc.)
  6. **Gap Fill** — Auto-detect under-represented categories and generate to balance
  7. **Retail Refresh** — Deactivate expired partner offers
  8. **Cleanup** — Remove past events from live_events table
  9. **Image Audit** — Re-scan all images for stock photo URLs, flag any new detections
  10. **Stats Snapshot** — Log daily totals and pipeline health metrics
- **Potential Output:** 200+ new ideas per daily run
- **Background Scheduler:** asyncio-based, auto-starts on app boot, configurable interval
- **14 Rotating Daily Themes:** Mystery Monday, Taco Tuesday, Wellness Wednesday, Throwback Thursday, Date Night Friday, Adventure Saturday, Slow Sunday, DIY Date, Cultural Dive, Surprise Date, Outdoor Adventure, Budget Bliss, Luxe Evening, Nostalgia Trip
- **Endpoints (5):**
  - `POST /admin/pipeline/run` — Trigger pipeline manually
  - `GET /admin/pipeline/status` — Current run status + last run details
  - `GET /admin/pipeline/config` — View pipeline configuration
  - `POST /admin/pipeline/config` — Update pipeline configuration
  - `GET /admin/pipeline` — Admin dashboard (HTML UI with controls, config editor, run history)

---

## Complete Project Summary

### All Backend Files

| File | Lines | Purpose |
|------|-------|---------|
| `backend/main.py` | ~2,100 | Core API with all routes |
| `backend/admin.py` | 1,224 | Image management dashboard |
| `backend/journal.py` | 1,089 | Date memory journal |
| `backend/review_queue.py` | 981 | AI idea approval queue |
| `backend/smart_algorithm.py` | ~800 | Preference learning engine v2 |
| `backend/partner.py` | 741 | Partner pairing system |
| `backend/idea_seeder.py` | ~700 | Idea seeding engine + admin UI |
| `backend/retail_partners.py` | ~700 | Retail partner system + revenue |
| `backend/live_events.py` | ~650 | Live events + multi-source scraper |
| `backend/daily_pipeline.py` | ~550 | Automated daily idea generation pipeline |
| `backend/ai_providers.py` | 251 | Multi-model AI system |
| **Total New Code** | **~9,786** | |

### All Backend Files (11 total)

### All Database Tables (18 new)

| Table | Purpose |
|-------|---------|
| `partner_connections` | Partner invite/link tracking |
| `shared_wishlist` | Ideas shared between partners |
| `idea_reviews` | AI idea review/approval queue |
| `featured_ideas` | Daily/weekly featured selections |
| `idea_interactions` | User accept/reject tracking |
| `occasions` | Special occasion management |
| `date_memories` | Journal entries (ratings, notes, photos) |
| `date_milestones` | Achievement/badge tracking |
| `user_submitted_ideas` | User-submitted idea queue |
| `seed_jobs` | Seed operation tracking |
| `retail_partners` | Business profiles + tier + analytics |
| `retailer_ideas` | Partner-linked date ideas |
| `retail_analytics` | View/click/booking tracking |
| `live_events` | Events from all external sources |
| `scrape_jobs` | Source scrape job tracking |

### All API Endpoints (96 new)

| Category | Count | Prefix |
|----------|-------|--------|
| Admin Dashboard | 8 | `/admin/` |
| Review Queue | 7 | `/admin/review/` |
| Idea Seeder | 12 | `/admin/seeder/` |
| Retail Partners | 16 | `/api/retail/` + `/admin/retail/` |
| Live Events | 12 | `/api/events/` + `/admin/events/` |
| Partner Pairing | 8 | `/api/partner/` |
| Journal & Memories | 9 | `/api/journal/` |
| Smart Recommendations | 11 | `/api/recommendations/` |
| Occasions | 5 | `/api/occasions/` |
| Featured Ideas | 3 | `/api/date-ideas/` |
| Idea Interactions | 4 | `/api/ideas/` |
| Daily Pipeline | 5 | `/admin/pipeline/` |
| AI Provider Mgmt | 3 | `/api/ai/` |
| User Idea Submit | 1 | `/api/ideas/submit` |

---

_Changelog maintained as part of the Arrows weekly sprint (3/14/26). All changes by Raj._
