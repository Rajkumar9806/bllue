"""
Arrow AI Idea Review Queue
Moderation system for AI-generated date ideas before reaching users
"""
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import HTMLResponse
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import logging
import json
import httpx

from ai_providers import get_ai_provider, clean_response_text

logger = logging.getLogger(__name__)

# Global db_pool reference (injected from main.py)
db_pool: Optional[asyncpg.Pool] = None
ai_provider_name: str = "gemini"

def set_db_pool(pool: asyncpg.Pool):
    """Set the database pool (called from main.py on startup)"""
    global db_pool
    db_pool = pool

def set_ai_provider(provider: str):
    """Set the AI provider to use"""
    global ai_provider_name
    ai_provider_name = provider

router = APIRouter(prefix="/admin/review", tags=["review_queue"])

# ==================== DATABASE INITIALIZATION ====================

async def init_review_queue_table():
    """Create the idea_reviews table if it doesn't exist"""
    if not db_pool:
        logger.error("Database pool not initialized")
        return

    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS idea_reviews (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                idea_title VARCHAR(255) NOT NULL,
                idea_description TEXT,
                idea_category VARCHAR(50),
                idea_budget VARCHAR(20),
                idea_duration VARCHAR(50),
                idea_location_type VARCHAR(50),
                idea_image_url TEXT,
                idea_tags TEXT[],
                idea_source VARCHAR(50) DEFAULT 'ai-generated',
                ai_provider VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                reviewed_by VARCHAR(255),
                reviewed_at TIMESTAMP,
                rejection_reason TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        ''')
        logger.info("idea_reviews table initialized")

# ==================== HTML REVIEW QUEUE PAGE ====================

HTML_REVIEW_QUEUE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Idea Review Queue</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
            background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%);
            min-height: 100vh;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        header h1 {
            font-size: 28px;
            color: #1a1a1a;
        }

        header .stats {
            display: flex;
            gap: 40px;
            align-items: center;
        }

        .stat-item {
            text-align: right;
        }

        .stat-item .label {
            font-size: 12px;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .stat-item .value {
            font-size: 24px;
            font-weight: 600;
            color: #E04060;
            margin-top: 5px;
        }

        .controls {
            background: white;
            padding: 20px 30px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }

        .filter-tabs {
            display: flex;
            gap: 10px;
            border-bottom: 2px solid #eee;
            padding-bottom: 0;
        }

        .filter-tabs button {
            padding: 12px 20px;
            background: none;
            border: none;
            border-bottom: 3px solid transparent;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            color: #999;
            transition: all 0.3s;
        }

        .filter-tabs button.active {
            color: #E04060;
            border-bottom-color: #E04060;
        }

        .reviewer-input-group {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-left: auto;
            flex-wrap: wrap;
        }

        .reviewer-input-group label {
            font-weight: 500;
            color: #555;
            font-size: 14px;
        }

        .reviewer-input-group input {
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
            width: 150px;
        }

        button {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s;
            font-family: inherit;
        }

        .btn-primary {
            background: #E04060;
            color: white;
        }

        .btn-primary:hover {
            background: #d63150;
            box-shadow: 0 4px 12px rgba(224, 64, 96, 0.3);
        }

        .btn-success {
            background: #4CAF50;
            color: white;
            padding: 8px 16px;
            font-size: 13px;
        }

        .btn-success:hover {
            background: #45a049;
        }

        .btn-danger {
            background: #ff4444;
            color: white;
            padding: 8px 16px;
            font-size: 13px;
        }

        .btn-danger:hover {
            background: #dd3333;
        }

        .cards-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .idea-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: all 0.3s;
        }

        .idea-card:hover {
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }

        .card-image {
            width: 100%;
            height: 180px;
            object-fit: cover;
            background: #f0f0f0;
        }

        .card-content {
            padding: 20px;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 12px;
            gap: 10px;
        }

        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
            flex: 1;
        }

        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            white-space: nowrap;
        }

        .status-pending {
            background: #fff3cd;
            color: #856404;
        }

        .status-approved {
            background: #d4edda;
            color: #155724;
        }

        .status-rejected {
            background: #f8d7da;
            color: #721c24;
        }

        .source-badge {
            display: inline-block;
            background: #e0e0e0;
            color: #555;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .card-description {
            font-size: 14px;
            color: #666;
            line-height: 1.4;
            margin-bottom: 12px;
        }

        .card-meta {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 12px;
            font-size: 12px;
            color: #999;
        }

        .meta-badge {
            background: #f5f5f5;
            padding: 4px 8px;
            border-radius: 4px;
        }

        .card-tags {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-bottom: 12px;
        }

        .tag {
            background: #f0f0f0;
            color: #555;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
        }

        .rejection-reason {
            background: #fff5f5;
            border-left: 3px solid #ff4444;
            padding: 10px 12px;
            margin-bottom: 12px;
            border-radius: 4px;
            font-size: 13px;
            color: #d32f2f;
        }

        .card-actions {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }

        .card-actions button {
            flex: 1;
            padding: 8px 12px;
            font-size: 13px;
        }

        .empty-state {
            text-align: center;
            padding: 60px 40px;
            background: white;
            border-radius: 12px;
            color: #999;
        }

        .empty-state p {
            font-size: 16px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            color: #999;
        }

        .pagination {
            display: flex;
            gap: 10px;
            justify-content: center;
            padding: 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .pagination button {
            padding: 8px 12px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 4px;
            cursor: pointer;
        }

        .pagination button.active {
            background: #E04060;
            color: white;
            border-color: #E04060;
        }

        @media (max-width: 768px) {
            header {
                flex-direction: column;
                text-align: center;
                gap: 20px;
            }

            header .stats {
                width: 100%;
                justify-content: center;
            }

            .controls {
                flex-direction: column;
                align-items: flex-start;
            }

            .reviewer-input-group {
                margin-left: 0;
                width: 100%;
            }

            .filter-tabs {
                width: 100%;
                overflow-x: auto;
            }

            .cards-container {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>AI Idea Review Queue</h1>
            <div class="stats">
                <div class="stat-item">
                    <div class="label">Pending</div>
                    <div class="value" id="pendingCount">0</div>
                </div>
                <div class="stat-item">
                    <div class="label">Approved</div>
                    <div class="value" id="approvedCount">0</div>
                </div>
                <div class="stat-item">
                    <div class="label">Rejected</div>
                    <div class="value" id="rejectedCount">0</div>
                </div>
            </div>
        </header>

        <div class="controls">
            <div class="filter-tabs">
                <button class="active" onclick="setFilter('all')">All</button>
                <button onclick="setFilter('pending')">Pending</button>
                <button onclick="setFilter('approved')">Approved</button>
                <button onclick="setFilter('rejected')">Rejected</button>
            </div>
            <button class="btn-primary" onclick="generateNewIdeas()">Generate New Ideas</button>
            <div class="reviewer-input-group">
                <label for="reviewerName">Reviewer Name:</label>
                <input type="text" id="reviewerName" placeholder="e.g., Kipper" value="">
            </div>
        </div>

        <div id="cardsContainer" class="cards-container">
            <div class="loading">Loading ideas...</div>
        </div>

        <div id="paginationContainer"></div>
    </div>

    <script>
        let currentFilter = 'all';
        let currentPage = 1;
        const itemsPerPage = 12;

        function getReviewerName() {
            let name = document.getElementById('reviewerName').value.trim();
            if (!name) {
                name = localStorage.getItem('reviewerName') || '';
                if (name) {
                    document.getElementById('reviewerName').value = name;
                }
            } else {
                localStorage.setItem('reviewerName', name);
            }
            return name;
        }

        function setFilter(filter) {
            currentFilter = filter;
            currentPage = 1;
            document.querySelectorAll('.filter-tabs button').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            loadQueue();
        }

        async function loadQueue() {
            const container = document.getElementById('cardsContainer');
            const offset = (currentPage - 1) * itemsPerPage;

            try {
                const params = new URLSearchParams({
                    status: currentFilter === 'all' ? '' : currentFilter,
                    limit: itemsPerPage,
                    offset: offset
                });

                const response = await fetch(`/admin/review/api/queue?${params}`);
                const data = await response.json();
                const ideas = data.ideas || [];
                const total = data.total || 0;

                updateStats();

                if (ideas.length === 0) {
                    container.innerHTML = '<div class="empty-state"><p>No ideas found</p></div>';
                    document.getElementById('paginationContainer').innerHTML = '';
                    return;
                }

                let html = '';
                ideas.forEach(idea => {
                    html += createIdeaCard(idea);
                });

                container.innerHTML = html;

                if (total > itemsPerPage) {
                    const totalPages = Math.ceil(total / itemsPerPage);
                    let paginationHtml = '<div class="pagination">';
                    if (currentPage > 1) {
                        paginationHtml += '<button onclick="currentPage--; loadQueue()">Previous</button>';
                    }
                    for (let i = 1; i <= totalPages; i++) {
                        paginationHtml += `<button class="${i === currentPage ? 'active' : ''}" onclick="currentPage = ${i}; loadQueue()">${i}</button>`;
                    }
                    if (currentPage < totalPages) {
                        paginationHtml += '<button onclick="currentPage++; loadQueue()">Next</button>';
                    }
                    paginationHtml += '</div>';
                    document.getElementById('paginationContainer').innerHTML = paginationHtml;
                } else {
                    document.getElementById('paginationContainer').innerHTML = '';
                }
            } catch (error) {
                console.error('Error loading queue:', error);
                container.innerHTML = '<div class="empty-state"><p>Error loading ideas</p></div>';
            }
        }

        function createIdeaCard(idea) {
            const statusClass = `status-${idea.status}`;
            const imageUrl = idea.idea_image_url || 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22180%22%3E%3Crect fill=%22%23ddd%22 width=%22300%22 height=%22180%22/%3E%3C/svg%3E';

            let actionHtml = '';
            if (idea.status === 'pending') {
                actionHtml = `
                    <button class="btn-success" onclick="approveIdea('${idea.id}')">✓ Approve</button>
                    <button class="btn-danger" onclick="rejectIdea('${idea.id}')">✗ Reject</button>
                `;
            }

            let rejectionHtml = '';
            if (idea.rejection_reason) {
                rejectionHtml = `<div class="rejection-reason">Reason: ${escapeHtml(idea.rejection_reason)}</div>`;
            }

            let tagsHtml = '';
            if (idea.idea_tags && idea.idea_tags.length > 0) {
                tagsHtml = '<div class="card-tags">' +
                    idea.idea_tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('') +
                    '</div>';
            }

            return `
                <div class="idea-card">
                    <img src="${escapeHtml(imageUrl)}" alt="Idea" class="card-image" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22180%22%3E%3Crect fill=%22%23ddd%22 width=%22300%22 height=%22180%22/%3E%3C/svg%3E'">
                    <div class="card-content">
                        <div class="card-header">
                            <div class="card-title">${escapeHtml(idea.idea_title)}</div>
                            <span class="status-badge ${statusClass}">${idea.status}</span>
                        </div>
                        <span class="source-badge">${escapeHtml(idea.ai_provider || 'ai')}</span>
                        <div class="card-description">${escapeHtml(idea.idea_description || '')}</div>
                        <div class="card-meta">
                            <span class="meta-badge">${escapeHtml(idea.idea_category || '-')}</span>
                            <span class="meta-badge">${escapeHtml(idea.idea_budget || '-')}</span>
                            <span class="meta-badge">${escapeHtml(idea.idea_duration || '-')}</span>
                        </div>
                        ${tagsHtml}
                        ${rejectionHtml}
                        <div class="card-actions">
                            ${actionHtml}
                        </div>
                    </div>
                </div>
            `;
        }

        async function approveIdea(ideaId) {
            const reviewerName = getReviewerName();
            if (!reviewerName) {
                alert('Please enter your name first');
                return;
            }

            try {
                const response = await fetch(`/admin/review/api/queue/${ideaId}/approve`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reviewed_by: reviewerName })
                });

                if (response.ok) {
                    loadQueue();
                } else {
                    const error = await response.json();
                    alert('Error: ' + (error.detail || 'Failed to approve'));
                }
            } catch (error) {
                console.error('Error approving idea:', error);
                alert('Error approving idea');
            }
        }

        async function rejectIdea(ideaId) {
            const reviewerName = getReviewerName();
            if (!reviewerName) {
                alert('Please enter your name first');
                return;
            }

            const reason = prompt('Enter rejection reason:');
            if (!reason) return;

            try {
                const response = await fetch(`/admin/review/api/queue/${ideaId}/reject`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        reviewed_by: reviewerName,
                        rejection_reason: reason
                    })
                });

                if (response.ok) {
                    loadQueue();
                } else {
                    const error = await response.json();
                    alert('Error: ' + (error.detail || 'Failed to reject'));
                }
            } catch (error) {
                console.error('Error rejecting idea:', error);
                alert('Error rejecting idea');
            }
        }

        async function generateNewIdeas() {
            if (!confirm('Generate 5-10 new AI ideas for review?')) return;

            try {
                const response = await fetch('/admin/review/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ count: 7 })
                });

                if (response.ok) {
                    const data = await response.json();
                    alert(`Generated ${data.count} new ideas for review`);
                    currentPage = 1;
                    currentFilter = 'pending';
                    document.querySelectorAll('.filter-tabs button')[1].click();
                } else {
                    const error = await response.json();
                    alert('Error: ' + (error.detail || 'Failed to generate ideas'));
                }
            } catch (error) {
                console.error('Error generating ideas:', error);
                alert('Error generating ideas');
            }
        }

        async function updateStats() {
            try {
                const response = await fetch('/admin/review/api/stats');
                const stats = await response.json();
                document.getElementById('pendingCount').textContent = stats.pending_count;
                document.getElementById('approvedCount').textContent = stats.approved_count;
                document.getElementById('rejectedCount').textContent = stats.rejected_count;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        document.addEventListener('DOMContentLoaded', function() {
            const savedReviewer = localStorage.getItem('reviewerName');
            if (savedReviewer) {
                document.getElementById('reviewerName').value = savedReviewer;
            }
            loadQueue();
        });
    </script>
</body>
</html>"""

# ==================== API ENDPOINTS ====================

@router.get("/", response_class=HTMLResponse)
async def review_queue_page():
    """Serve the review queue HTML page"""
    return HTML_REVIEW_QUEUE

@router.get("/api/queue")
async def list_queue(
    status: Optional[str] = None,
    limit: int = 12,
    offset: int = 0
):
    """List ideas in the review queue with filters and pagination"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        query = "SELECT * FROM idea_reviews WHERE 1=1"
        params = []
        param_count = 0

        if status and status in ['pending', 'approved', 'rejected']:
            param_count += 1
            query += f" AND status = ${param_count}"
            params.append(status)

        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total = await conn.fetchval(count_query, *params)

        param_count += 1
        query += f" ORDER BY created_at DESC LIMIT ${param_count}"
        params.append(limit)

        param_count += 1
        query += f" OFFSET ${param_count}"
        params.append(offset)

        rows = await conn.fetch(query, *params)
        ideas = []
        for row in rows:
            idea = dict(row)
            idea['id'] = str(idea['id'])
            ideas.append(idea)

        return {
            "ideas": ideas,
            "total": total,
            "limit": limit,
            "offset": offset
        }

@router.get("/api/queue/{item_id}")
async def get_review_item(item_id: str):
    """Get a specific review item"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        item_uuid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM idea_reviews WHERE id = $1", item_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="Review item not found")

        item = dict(row)
        item['id'] = str(item['id'])
        return item

@router.put("/api/queue/{item_id}/approve")
async def approve_idea(item_id: str, data: Dict[str, Any] = Body(...)):
    """Approve an idea and move it to date_ideas table"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        item_uuid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID")

    reviewed_by = data.get('reviewed_by', 'unknown')

    async with db_pool.acquire() as conn:
        # Get the review item
        row = await conn.fetchrow("SELECT * FROM idea_reviews WHERE id = $1", item_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="Review item not found")

        try:
            # Create new idea in date_ideas table
            new_idea_id = uuid.uuid4()
            await conn.execute('''
                INSERT INTO date_ideas
                (id, title, description, category, budget, duration, location_type, image_url, tags, source, updated_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ''', new_idea_id, row['idea_title'], row['idea_description'], row['idea_category'],
               row['idea_budget'], row['idea_duration'], row['idea_location_type'],
               row['idea_image_url'], row['idea_tags'], 'ai-reviewed', reviewed_by)

            # Update the review record
            await conn.execute('''
                UPDATE idea_reviews
                SET status = 'approved', reviewed_by = $1, reviewed_at = NOW()
                WHERE id = $2
            ''', reviewed_by, item_uuid)

            return {
                "success": True,
                "message": "Idea approved and added to date_ideas",
                "idea_id": str(new_idea_id)
            }
        except Exception as e:
            logger.error(f"Error approving idea: {e}")
            raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/queue/{item_id}/reject")
async def reject_idea(item_id: str, data: Dict[str, Any] = Body(...)):
    """Reject an idea"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        item_uuid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID")

    reviewed_by = data.get('reviewed_by', 'unknown')
    rejection_reason = data.get('rejection_reason', '')

    async with db_pool.acquire() as conn:
        # Check if idea exists
        existing = await conn.fetchrow("SELECT id FROM idea_reviews WHERE id = $1", item_uuid)
        if not existing:
            raise HTTPException(status_code=404, detail="Review item not found")

        try:
            await conn.execute('''
                UPDATE idea_reviews
                SET status = 'rejected', reviewed_by = $1, reviewed_at = NOW(), rejection_reason = $2
                WHERE id = $3
            ''', reviewed_by, rejection_reason, item_uuid)

            return {
                "success": True,
                "message": "Idea rejected"
            }
        except Exception as e:
            logger.error(f"Error rejecting idea: {e}")
            raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/generate")
async def generate_ideas_for_review(data: Dict[str, Any] = Body(...)):
    """Generate new AI ideas and put them in the review queue"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    count = data.get('count', 7)
    if count < 1 or count > 20:
        count = 7

    try:
        # Generate ideas using AI provider
        provider = get_ai_provider(ai_provider_name)

        prompt = f"""You are a creative date night planner. Generate {count} unique and creative date night ideas for a review queue.

Generate {count} creative, unique date ideas. Include trendy ideas from social media like Instagram, TikTok.

Return ONLY a valid JSON array with this exact structure (no markdown, no explanation):
[
  {{
    "title": "Date idea title",
    "description": "Detailed 2-3 sentence description",
    "category": "romantic|adventure|foodie|creative|relaxing|fun|cultural|active|entertainment|nightlife|meaningful",
    "budget": "low|medium|high",
    "duration": "duration estimate",
    "location_type": "indoor|outdoor|both",
    "tags": ["tag1", "tag2", "tag3"]
  }}
]"""

        text = await provider.generate(prompt, temperature=0.9, max_tokens=2048)
        text = clean_response_text(text)
        ideas = json.loads(text)

        if not isinstance(ideas, list):
            raise ValueError("AI response was not a list")

        # Insert into review queue
        async with db_pool.acquire() as conn:
            for idea in ideas:
                idea_id = uuid.uuid4()
                await conn.execute('''
                    INSERT INTO idea_reviews
                    (id, idea_title, idea_description, idea_category, idea_budget,
                     idea_duration, idea_location_type, idea_tags, ai_provider, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')
                ''', idea_id, idea.get('title', ''), idea.get('description', ''),
                   idea.get('category', 'fun'), idea.get('budget', 'medium'),
                   idea.get('duration', ''), idea.get('location_type', 'both'),
                   idea.get('tags', []), ai_provider_name)

        return {
            "success": True,
            "count": len(ideas),
            "message": f"Generated {len(ideas)} ideas for review"
        }

    except ValueError as e:
        logger.error(f"AI provider not configured: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse AI response")
    except Exception as e:
        logger.error(f"Error generating ideas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/stats")
async def get_review_stats():
    """Get review queue statistics"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        pending = await conn.fetchval("SELECT COUNT(*) FROM idea_reviews WHERE status = 'pending'")
        approved = await conn.fetchval("SELECT COUNT(*) FROM idea_reviews WHERE status = 'approved'")
        rejected = await conn.fetchval("SELECT COUNT(*) FROM idea_reviews WHERE status = 'rejected'")

        total = pending + approved + rejected
        approval_rate = 0
        if total > 0:
            approval_rate = round((approved / total) * 100, 1)

        return {
            "pending_count": pending,
            "approved_count": approved,
            "rejected_count": rejected,
            "total_count": total,
            "approval_rate": approval_rate
        }
