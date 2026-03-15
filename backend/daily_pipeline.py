"""
Arrow Daily Idea Generation Pipeline

Automated background system that runs on a configurable schedule to keep
the idea database fresh with hundreds of new ideas every day.

Pipeline stages (all run automatically):
1. Ticketmaster Scrape — Pull new concerts, shows, events
2. AI Social Trends — Generate trending local ideas (3 batches, different themes)
3. AI Seasonal/Festive — Generate season-appropriate local events
4. AI Category Variety — Generate ideas across ALL categories
5. AI Themed Batches — Rotating daily themes (Date Night In, Budget Date, etc.)
6. Gap Fill — Detect under-represented categories and fill them
7. Retail Partner Refresh — Deactivate expired partner offers
8. Cleanup — Remove past events, deduplicate
9. Image Audit — Flag any new stock images for review
10. Stats Snapshot — Log daily totals

Runs via BackgroundTasks on startup, then every 24 hours.
Can also be triggered manually via admin API.
"""

import asyncio
import asyncpg
import logging
import json
import uuid
import random
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

db_pool: Optional[asyncpg.Pool] = None
_pipeline_running = False
_last_run: Optional[datetime] = None
_pipeline_task: Optional[asyncio.Task] = None

# Configuration
PIPELINE_CONFIG = {
    "enabled": True,
    "interval_hours": 24,
    "city": "Nashville",

    # How many ideas per source per run
    "ticketmaster_days_ahead": 30,
    "social_trend_batches": 3,
    "social_trend_per_batch": 15,
    "seasonal_count": 10,
    "category_bulk_count": 15,
    "themed_batch_count": 10,
    "gap_fill_per_category": 8,

    # Daily rotating themes (cycles through one per day)
    "daily_themes": [
        "Cheap thrills: creative dates under $20",
        "Adrenaline rush: extreme and active experiences",
        "Cozy night in: zero-effort comfort dates",
        "Foodie crawl: culinary exploration dates",
        "Culture vulture: art, theater, museum dates",
        "Surprise wildcard: weird, unusual, unexpected dates",
        "Romance overload: over-the-top romantic gestures",
        "Double date: ideas for group date nights",
        "Morning date: breakfast and early-day activities",
        "Late night: after-10pm date ideas",
        "Seasonal special: events happening this week only",
        "Local hidden gems: underrated spots locals love",
        "Instagram-worthy: visually stunning date spots",
        "Nostalgia trip: retro and throwback date ideas",
    ],
}

STOCK_DOMAINS = [
    'unsplash.com', 'pexels.com', 'pixabay.com', 'shutterstock.com',
    'istockphoto.com', 'gettyimages.com', 'stock.adobe.com', 'dreamstime.com',
    'depositphotos.com', '123rf.com', 'freepik.com', 'stocksy.com',
]


def set_db_pool(pool: asyncpg.Pool):
    global db_pool
    db_pool = pool


def is_stock_image(url: str) -> bool:
    url_lower = url.lower()
    return any(d in url_lower for d in STOCK_DOMAINS)


# ==================== PIPELINE STAGES ====================

async def stage_ticketmaster(city: str, config: dict) -> Dict[str, int]:
    """Stage 1: Scrape Ticketmaster for live events."""
    try:
        from live_events import scrape_ticketmaster, insert_events_batch
        events = await scrape_ticketmaster(city, config["ticketmaster_days_ahead"])
        result = await insert_events_batch(events)
        logger.info(f"[Pipeline] Ticketmaster: {result['inserted']} inserted, {result['flagged']} flagged")
        return result
    except Exception as e:
        logger.error(f"[Pipeline] Ticketmaster failed: {e}")
        return {"inserted": 0, "flagged": 0, "skipped": 0, "error": str(e)}


async def stage_social_trends(city: str, config: dict) -> Dict[str, int]:
    """Stage 2: Generate social-trend ideas in multiple batches."""
    try:
        from live_events import scrape_social_trends, insert_events_batch
        total_inserted = 0
        total_flagged = 0

        for batch in range(config["social_trend_batches"]):
            events = await scrape_social_trends(city, config["social_trend_per_batch"])
            result = await insert_events_batch(events)
            total_inserted += result['inserted']
            total_flagged += result['flagged']
            # Small delay between batches to avoid rate limits
            await asyncio.sleep(2)

        logger.info(f"[Pipeline] Social trends: {total_inserted} inserted across {config['social_trend_batches']} batches")
        return {"inserted": total_inserted, "flagged": total_flagged}
    except Exception as e:
        logger.error(f"[Pipeline] Social trends failed: {e}")
        return {"inserted": 0, "flagged": 0, "error": str(e)}


async def stage_seasonal(city: str, config: dict) -> Dict[str, int]:
    """Stage 3: Generate seasonal/festive local ideas."""
    try:
        from live_events import scrape_seasonal_local, insert_events_batch
        events = await scrape_seasonal_local(city, config["seasonal_count"])
        result = await insert_events_batch(events)
        logger.info(f"[Pipeline] Seasonal: {result['inserted']} inserted")
        return result
    except Exception as e:
        logger.error(f"[Pipeline] Seasonal failed: {e}")
        return {"inserted": 0, "flagged": 0, "error": str(e)}


async def stage_category_variety(config: dict) -> Dict[str, int]:
    """Stage 4: Generate ideas across ALL categories for variety."""
    try:
        from idea_seeder import generate_bulk_ideas, insert_ideas_batch
        categories = ["romantic", "adventure", "foodie", "creative", "relaxing", "fun", "cultural", "active"]
        total_inserted = 0

        for cat in categories:
            ideas = await generate_bulk_ideas(
                category=cat,
                count=config["category_bulk_count"]
            )
            inserted = await insert_ideas_batch(ideas, source=f"daily-pipeline-{cat}")
            total_inserted += inserted
            await asyncio.sleep(1)

        logger.info(f"[Pipeline] Category variety: {total_inserted} inserted across {len(categories)} categories")
        return {"inserted": total_inserted}
    except Exception as e:
        logger.error(f"[Pipeline] Category variety failed: {e}")
        return {"inserted": 0, "error": str(e)}


async def stage_themed_batch(config: dict) -> Dict[str, int]:
    """Stage 5: Generate a themed batch based on daily rotation."""
    try:
        from idea_seeder import generate_bulk_ideas, insert_ideas_batch

        # Pick today's theme based on day-of-year
        day_of_year = datetime.utcnow().timetuple().tm_yday
        themes = config["daily_themes"]
        today_theme = themes[day_of_year % len(themes)]

        ideas = await generate_bulk_ideas(
            theme=today_theme,
            count=config["themed_batch_count"]
        )
        inserted = await insert_ideas_batch(ideas, source="daily-themed")

        logger.info(f"[Pipeline] Themed batch '{today_theme}': {inserted} inserted")
        return {"inserted": inserted, "theme": today_theme}
    except Exception as e:
        logger.error(f"[Pipeline] Themed batch failed: {e}")
        return {"inserted": 0, "error": str(e)}


async def stage_gap_fill(config: dict) -> Dict[str, int]:
    """Stage 6: Detect and fill category gaps."""
    try:
        from idea_seeder import analyze_category_gaps, generate_bulk_ideas, insert_ideas_batch

        gaps = await analyze_category_gaps()
        under = gaps.get("under_represented_categories", []) + gaps.get("missing_categories", [])

        if not under:
            logger.info("[Pipeline] Gap fill: No gaps found")
            return {"inserted": 0, "gaps": []}

        total_inserted = 0
        for cat in under:
            ideas = await generate_bulk_ideas(category=cat, count=config["gap_fill_per_category"])
            inserted = await insert_ideas_batch(ideas, source="daily-gap-fill")
            total_inserted += inserted
            await asyncio.sleep(1)

        logger.info(f"[Pipeline] Gap fill: {total_inserted} inserted for gaps: {under}")
        return {"inserted": total_inserted, "gaps": under}
    except Exception as e:
        logger.error(f"[Pipeline] Gap fill failed: {e}")
        return {"inserted": 0, "error": str(e)}


async def stage_retail_refresh() -> Dict[str, int]:
    """Stage 7: Deactivate expired retail offers."""
    try:
        now = datetime.utcnow()
        async with db_pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE retailer_ideas SET is_active = FALSE
                WHERE valid_until IS NOT NULL AND valid_until < $1 AND is_active = TRUE
            """, now)
            expired_count = int(result.split()[-1]) if result else 0

        logger.info(f"[Pipeline] Retail refresh: {expired_count} expired offers deactivated")
        return {"expired_deactivated": expired_count}
    except Exception as e:
        logger.error(f"[Pipeline] Retail refresh failed: {e}")
        return {"expired_deactivated": 0, "error": str(e)}


async def stage_cleanup() -> Dict[str, int]:
    """Stage 8: Remove past events and deduplicate."""
    try:
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)

        async with db_pool.acquire() as conn:
            # Deactivate past events
            result = await conn.execute("""
                UPDATE live_events SET is_active = FALSE
                WHERE event_date IS NOT NULL AND event_date < $1 AND is_active = TRUE
            """, yesterday)
            past_count = int(result.split()[-1]) if result else 0

            # Count total active
            total_active = await conn.fetchval("SELECT COUNT(*) FROM date_ideas")
            total_events = await conn.fetchval("SELECT COUNT(*) FROM live_events WHERE is_active = TRUE")

        logger.info(f"[Pipeline] Cleanup: {past_count} past events deactivated. DB: {total_active} ideas, {total_events} events")
        return {"past_deactivated": past_count, "total_ideas": total_active, "total_events": total_events}
    except Exception as e:
        logger.error(f"[Pipeline] Cleanup failed: {e}")
        return {"error": str(e)}


async def stage_image_audit() -> Dict[str, int]:
    """Stage 9: Scan for any stock images that slipped through."""
    try:
        flagged = 0
        async with db_pool.acquire() as conn:
            # Check date_ideas
            rows = await conn.fetch("""
                SELECT id, image_url FROM date_ideas
                WHERE image_url IS NOT NULL AND image_url != ''
            """)
            for row in rows:
                if is_stock_image(row['image_url']):
                    flagged += 1

            # Check live_events with approved status
            rows2 = await conn.fetch("""
                SELECT id, image_url FROM live_events
                WHERE image_status = 'approved' AND image_url IS NOT NULL AND image_url != ''
            """)
            for row in rows2:
                if is_stock_image(row['image_url']):
                    await conn.execute(
                        "UPDATE live_events SET image_status = 'pending_review' WHERE id = $1",
                        row['id']
                    )
                    flagged += 1

            # Check retailer_ideas
            rows3 = await conn.fetch("""
                SELECT id, photos FROM retailer_ideas
                WHERE image_status = 'approved' AND photos IS NOT NULL
            """)
            for row in rows3:
                for photo in (row['photos'] or []):
                    if is_stock_image(photo):
                        await conn.execute(
                            "UPDATE retailer_ideas SET image_status = 'pending_review' WHERE id = $1",
                            row['id']
                        )
                        flagged += 1
                        break

        logger.info(f"[Pipeline] Image audit: {flagged} stock images flagged")
        return {"stock_images_flagged": flagged}
    except Exception as e:
        logger.error(f"[Pipeline] Image audit failed: {e}")
        return {"error": str(e)}


async def stage_stats_snapshot() -> Dict[str, Any]:
    """Stage 10: Log daily totals."""
    try:
        async with db_pool.acquire() as conn:
            stats = {
                "total_date_ideas": await conn.fetchval("SELECT COUNT(*) FROM date_ideas"),
                "total_live_events": await conn.fetchval("SELECT COUNT(*) FROM live_events WHERE is_active = TRUE"),
                "total_retail_partners": await conn.fetchval("SELECT COUNT(*) FROM retail_partners WHERE is_active = TRUE"),
                "total_retailer_ideas": await conn.fetchval("SELECT COUNT(*) FROM retailer_ideas WHERE is_active = TRUE"),
                "pending_image_reviews": (
                    await conn.fetchval("SELECT COUNT(*) FROM live_events WHERE image_status IN ('pending_review', 'needs_image')") +
                    await conn.fetchval("SELECT COUNT(*) FROM retailer_ideas WHERE image_status IN ('pending_review', 'needs_image')")
                ),
                "ideas_by_source": {},
            }

            source_rows = await conn.fetch("SELECT COALESCE(source, 'unknown') as source, COUNT(*) as c FROM date_ideas GROUP BY source")
            stats["ideas_by_source"] = {r['source']: r['c'] for r in source_rows}

        logger.info(f"[Pipeline] Stats: {stats['total_date_ideas']} ideas, {stats['total_live_events']} events, {stats['total_retail_partners']} partners")
        return stats
    except Exception as e:
        logger.error(f"[Pipeline] Stats failed: {e}")
        return {"error": str(e)}


# ==================== PIPELINE RUNNER ====================

async def run_pipeline(city: str = None) -> Dict[str, Any]:
    """Run the full daily pipeline. Returns a summary of all stages."""
    global _pipeline_running, _last_run

    if _pipeline_running:
        return {"error": "Pipeline already running", "last_run": str(_last_run)}

    _pipeline_running = True
    config = PIPELINE_CONFIG.copy()
    if city:
        config["city"] = city
    target_city = config["city"]

    start_time = datetime.utcnow()
    logger.info(f"[Pipeline] Starting daily pipeline for {target_city}...")

    results = {}

    # Log job
    job_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO seed_jobs (id, job_type, status, details)
            VALUES ($1, 'daily-pipeline', 'running', $2)
        ''', job_id, json.dumps({"city": target_city, "started": start_time.isoformat()}))

    try:
        # Run all stages sequentially
        results["1_ticketmaster"] = await stage_ticketmaster(target_city, config)
        results["2_social_trends"] = await stage_social_trends(target_city, config)
        results["3_seasonal"] = await stage_seasonal(target_city, config)
        results["4_category_variety"] = await stage_category_variety(config)
        results["5_themed_batch"] = await stage_themed_batch(config)
        results["6_gap_fill"] = await stage_gap_fill(config)
        results["7_retail_refresh"] = await stage_retail_refresh()
        results["8_cleanup"] = await stage_cleanup()
        results["9_image_audit"] = await stage_image_audit()
        results["10_stats"] = await stage_stats_snapshot()

        # Calculate totals
        total_inserted = sum(
            r.get("inserted", 0) for r in results.values() if isinstance(r, dict)
        )
        total_flagged = sum(
            r.get("flagged", 0) + r.get("stock_images_flagged", 0)
            for r in results.values() if isinstance(r, dict)
        )

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        # Update job
        async with db_pool.acquire() as conn:
            await conn.execute('''
                UPDATE seed_jobs SET status = 'completed', ideas_generated = $1, ideas_inserted = $2,
                details = $3, completed_at = NOW() WHERE id = $4
            ''', total_inserted, total_inserted, json.dumps({
                "city": target_city,
                "elapsed_seconds": round(elapsed, 1),
                "stages": {k: str(v) for k, v in results.items()},
            }), job_id)

        _last_run = datetime.utcnow()
        logger.info(f"[Pipeline] Complete! {total_inserted} ideas added, {total_flagged} flagged. Took {elapsed:.1f}s")

        return {
            "success": True,
            "city": target_city,
            "total_inserted": total_inserted,
            "total_flagged": total_flagged,
            "elapsed_seconds": round(elapsed, 1),
            "stages": results
        }

    except Exception as e:
        logger.error(f"[Pipeline] Fatal error: {e}")
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE seed_jobs SET status = 'failed', details = $1, completed_at = NOW() WHERE id = $2",
                json.dumps({"error": str(e)}), job_id
            )
        return {"error": str(e)}

    finally:
        _pipeline_running = False


# ==================== BACKGROUND SCHEDULER ====================

async def _pipeline_loop():
    """Background loop that runs the pipeline every N hours."""
    interval = PIPELINE_CONFIG.get("interval_hours", 24) * 3600

    # Wait 60s after startup before first run (let everything initialize)
    await asyncio.sleep(60)

    while True:
        if PIPELINE_CONFIG.get("enabled", True):
            try:
                logger.info("[Pipeline] Scheduled run starting...")
                await run_pipeline()
            except Exception as e:
                logger.error(f"[Pipeline] Scheduled run failed: {e}")

        await asyncio.sleep(interval)


def start_pipeline_scheduler():
    """Start the background pipeline scheduler. Call from app startup."""
    global _pipeline_task
    if _pipeline_task is None or _pipeline_task.done():
        _pipeline_task = asyncio.create_task(_pipeline_loop())
        logger.info(f"[Pipeline] Scheduler started (every {PIPELINE_CONFIG['interval_hours']}h)")


def stop_pipeline_scheduler():
    """Stop the background scheduler. Call from app shutdown."""
    global _pipeline_task
    if _pipeline_task and not _pipeline_task.done():
        _pipeline_task.cancel()
        logger.info("[Pipeline] Scheduler stopped")


# ==================== API ENDPOINTS ====================

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.post("/admin/pipeline/run")
async def trigger_pipeline(city: str = "Nashville"):
    """Manually trigger the daily pipeline."""
    if _pipeline_running:
        return {"error": "Pipeline already running. Please wait.", "last_run": str(_last_run)}

    # Run in background so the API responds immediately
    asyncio.create_task(run_pipeline(city))
    return {"success": True, "message": f"Pipeline started for {city}. Check /admin/pipeline/status for progress."}


@router.get("/admin/pipeline/status")
async def pipeline_status():
    """Get current pipeline status."""
    async with db_pool.acquire() as conn:
        last_job = await conn.fetchrow("""
            SELECT * FROM seed_jobs WHERE job_type = 'daily-pipeline'
            ORDER BY started_at DESC LIMIT 1
        """)

        recent_jobs = await conn.fetch("""
            SELECT id, job_type, status, ideas_inserted, started_at, completed_at
            FROM seed_jobs WHERE job_type = 'daily-pipeline'
            ORDER BY started_at DESC LIMIT 7
        """)

    last = None
    if last_job:
        last = dict(last_job)
        last['id'] = str(last['id'])

    history = []
    for j in recent_jobs:
        item = dict(j)
        item['id'] = str(item['id'])
        history.append(item)

    return {
        "is_running": _pipeline_running,
        "last_run": str(_last_run) if _last_run else None,
        "enabled": PIPELINE_CONFIG.get("enabled", True),
        "interval_hours": PIPELINE_CONFIG.get("interval_hours", 24),
        "city": PIPELINE_CONFIG.get("city", "Nashville"),
        "last_job": last,
        "recent_runs": history
    }


@router.post("/admin/pipeline/config")
async def update_pipeline_config(
    enabled: Optional[bool] = None,
    interval_hours: Optional[int] = None,
    city: Optional[str] = None,
    social_trend_batches: Optional[int] = None,
    category_bulk_count: Optional[int] = None,
):
    """Update pipeline configuration."""
    if enabled is not None:
        PIPELINE_CONFIG["enabled"] = enabled
    if interval_hours is not None:
        PIPELINE_CONFIG["interval_hours"] = max(1, min(168, interval_hours))
    if city is not None:
        PIPELINE_CONFIG["city"] = city
    if social_trend_batches is not None:
        PIPELINE_CONFIG["social_trend_batches"] = max(1, min(10, social_trend_batches))
    if category_bulk_count is not None:
        PIPELINE_CONFIG["category_bulk_count"] = max(5, min(50, category_bulk_count))

    return {"success": True, "config": PIPELINE_CONFIG}


@router.get("/admin/pipeline/config")
async def get_pipeline_config():
    """Get current pipeline configuration."""
    return {"config": PIPELINE_CONFIG}


@router.get("/admin/pipeline", response_class=HTMLResponse)
async def pipeline_dashboard():
    """Pipeline admin dashboard."""
    status = await pipeline_status()
    config = PIPELINE_CONFIG

    # Recent runs table
    runs_html = ""
    for run in status.get("recent_runs", []):
        st = run.get('status', 'unknown')
        color = "#4CAF50" if st == "completed" else "#E83858" if st == "failed" else "#FFD700"
        runs_html += f"""<tr>
            <td style="color:{color}">{st.upper()}</td>
            <td>{run.get('ideas_inserted', 0)}</td>
            <td>{str(run.get('started_at', ''))[:19]}</td>
            <td>{str(run.get('completed_at', ''))[:19] if run.get('completed_at') else '—'}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Arrow — Daily Pipeline</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'Inter',sans-serif;background:#0f0f13;color:#e0e0e0;padding:24px;}}
  h1{{font-size:28px;color:#fff;margin-bottom:4px;}}
  h2{{font-size:16px;color:#888;margin-bottom:24px;font-weight:400;}}
  h3{{font-size:14px;color:#E83858;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:32px;}}
  .stat{{background:#1a1a22;border-radius:12px;padding:20px;text-align:center;}}
  .stat .num{{font-size:32px;font-weight:700;color:#E83858;}}
  .stat .label{{font-size:11px;color:#888;margin-top:4px;text-transform:uppercase;letter-spacing:1px;}}
  .stat.on .num{{color:#4CAF50;}}
  .stat.off .num{{color:#E83858;}}
  .section{{background:#1a1a22;border-radius:12px;padding:24px;margin-bottom:24px;}}
  table{{width:100%;border-collapse:collapse;}}
  th{{text-align:left;font-size:11px;color:#888;text-transform:uppercase;padding:8px;border-bottom:1px solid #2a2a35;}}
  td{{padding:8px;font-size:13px;border-bottom:1px solid #1f1f28;}}
  .btn{{background:#E83858;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;}}
  .btn:hover{{background:#d02e4c;}}
  .btn:disabled{{background:#555;cursor:not-allowed;}}
  .btn-outline{{background:transparent;border:1px solid #E83858;color:#E83858;}}
  .actions{{display:flex;gap:12px;margin-bottom:20px;}}
  #status{{margin-top:12px;padding:10px;background:#161620;border-radius:8px;font-size:13px;color:#aaa;}}
  .config-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;}}
  .config-item{{display:flex;flex-direction:column;gap:4px;}}
  .config-item label{{font-size:11px;color:#888;text-transform:uppercase;}}
  .config-item input,.config-item select{{background:#2a2a35;border:1px solid #333;color:#fff;padding:8px;border-radius:6px;}}
</style></head><body>

<h1>Daily Idea Pipeline</h1>
<h2>Automated idea generation — {config['city']}</h2>

<div class="stats">
  <div class="stat {'on' if config['enabled'] else 'off'}">
    <div class="num">{'ON' if config['enabled'] else 'OFF'}</div><div class="label">Pipeline Status</div>
  </div>
  <div class="stat"><div class="num">{config['interval_hours']}h</div><div class="label">Run Interval</div></div>
  <div class="stat"><div class="num">{'YES' if _pipeline_running else 'NO'}</div><div class="label">Currently Running</div></div>
  <div class="stat"><div class="num">{len(config['daily_themes'])}</div><div class="label">Theme Rotation</div></div>
</div>

<div class="section">
  <h3>Controls</h3>
  <div class="actions">
    <button onclick="runNow()" class="btn" {'disabled' if _pipeline_running else ''}>
      {'Running...' if _pipeline_running else 'Run Pipeline Now'}
    </button>
    <button onclick="togglePipeline()" class="btn btn-outline">
      {'Disable' if config['enabled'] else 'Enable'} Auto-Run
    </button>
    <button onclick="checkStatus()" class="btn btn-outline">Refresh Status</button>
  </div>
  <div id="status">Last run: {str(_last_run)[:19] if _last_run else 'Never'}</div>
</div>

<div class="section">
  <h3>Configuration</h3>
  <div class="config-grid">
    <div class="config-item"><label>City</label><input id="cfg-city" value="{config['city']}"></div>
    <div class="config-item"><label>Interval (hours)</label><input id="cfg-interval" type="number" value="{config['interval_hours']}" min="1" max="168"></div>
    <div class="config-item"><label>Social Trend Batches</label><input id="cfg-batches" type="number" value="{config['social_trend_batches']}" min="1" max="10"></div>
    <div class="config-item"><label>Ideas per Category</label><input id="cfg-cat-count" type="number" value="{config['category_bulk_count']}" min="5" max="50"></div>
  </div>
  <button onclick="saveConfig()" class="btn" style="margin-top:12px;">Save Config</button>
</div>

<div class="section">
  <h3>Recent Runs</h3>
  <table>
    <tr><th>Status</th><th>Ideas Added</th><th>Started</th><th>Completed</th></tr>
    {runs_html if runs_html else '<tr><td colspan="4" style="color:#666">No runs yet</td></tr>'}
  </table>
</div>

<div class="section">
  <h3>Today's Theme</h3>
  <p style="font-size:14px;color:#ccc;">
    {config['daily_themes'][datetime.utcnow().timetuple().tm_yday % len(config['daily_themes'])]}
  </p>
  <p style="font-size:11px;color:#666;margin-top:8px;">Rotates daily through {len(config['daily_themes'])} themes</p>
</div>

<div class="section">
  <h3>Pipeline Stages (10 steps per run)</h3>
  <ol style="font-size:13px;color:#aaa;line-height:2;padding-left:20px;">
    <li>Ticketmaster — Pull concerts, shows, events</li>
    <li>Social Trends — AI-generated trending local ideas ({config['social_trend_batches']} batches × {config['social_trend_per_batch']})</li>
    <li>Seasonal/Festive — Month-appropriate local events</li>
    <li>Category Variety — {config['category_bulk_count']} ideas × 8 categories</li>
    <li>Themed Batch — Daily rotating theme ({config['themed_batch_count']} ideas)</li>
    <li>Gap Fill — Auto-detect and fill underserved categories</li>
    <li>Retail Refresh — Deactivate expired partner offers</li>
    <li>Cleanup — Remove past events, dedup</li>
    <li>Image Audit — Flag stock images for review</li>
    <li>Stats Snapshot — Log totals</li>
  </ol>
</div>

<script>
async function runNow() {{
  document.getElementById('status').textContent = 'Starting pipeline...';
  const city = document.getElementById('cfg-city').value;
  const r = await fetch('/admin/pipeline/run?city='+encodeURIComponent(city), {{method:'POST'}});
  const d = await r.json();
  document.getElementById('status').textContent = d.message || d.error || JSON.stringify(d);
}}

async function togglePipeline() {{
  const enabled = {'false' if config['enabled'] else 'true'};
  await fetch('/admin/pipeline/config?enabled='+enabled, {{method:'POST'}});
  location.reload();
}}

async function checkStatus() {{
  const r = await fetch('/admin/pipeline/status');
  const d = await r.json();
  document.getElementById('status').textContent = 'Running: '+d.is_running+' | Last: '+(d.last_run||'Never');
}}

async function saveConfig() {{
  const city = document.getElementById('cfg-city').value;
  const interval = document.getElementById('cfg-interval').value;
  const batches = document.getElementById('cfg-batches').value;
  const catCount = document.getElementById('cfg-cat-count').value;
  await fetch(`/admin/pipeline/config?city=${{city}}&interval_hours=${{interval}}&social_trend_batches=${{batches}}&category_bulk_count=${{catCount}}`, {{method:'POST'}});
  document.getElementById('status').textContent = 'Config saved!';
}}
</script>
</body></html>"""

    return HTMLResponse(content=html)
