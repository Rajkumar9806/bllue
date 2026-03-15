"""
Arrow Admin Dashboard - Image Management System
Provides REST API and web UI for managing date ideas and images
"""
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import HTMLResponse
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

# Global db_pool reference (injected from main.py)
db_pool: Optional[asyncpg.Pool] = None

def set_db_pool(pool: asyncpg.Pool):
    """Set the database pool (called from main.py on startup)"""
    global db_pool
    db_pool = pool

router = APIRouter(prefix="/admin", tags=["admin"])

# ==================== HTML DASHBOARD ====================

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arrow Admin Dashboard</title>
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
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
            background: white;
            padding: 20px 30px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }

        .filter-group {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }

        label {
            font-weight: 500;
            color: #555;
            font-size: 14px;
        }

        select, input[type="text"] {
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
            transition: all 0.3s;
        }

        select:focus, input[type="text"]:focus {
            outline: none;
            border-color: #E04060;
            box-shadow: 0 0 0 3px rgba(224, 64, 96, 0.1);
        }

        .btn-group {
            display: flex;
            gap: 10px;
            margin-left: auto;
            flex-wrap: wrap;
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

        .btn-secondary {
            background: #f0f0f0;
            color: #333;
            border: 1px solid #ddd;
        }

        .btn-secondary:hover {
            background: #e5e5e5;
        }

        .btn-danger {
            background: #ff4444;
            color: white;
        }

        .btn-danger:hover {
            background: #dd3333;
        }

        .table-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            max-height: 70vh;
            overflow-y: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        thead {
            background: #f8f8f8;
            position: sticky;
            top: 0;
            z-index: 10;
        }

        th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #555;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #eee;
        }

        td {
            padding: 15px;
            border-bottom: 1px solid #eee;
            font-size: 14px;
        }

        tbody tr:hover {
            background: #fafafa;
        }

        .idea-thumbnail {
            width: 50px;
            height: 50px;
            border-radius: 4px;
            object-fit: cover;
            cursor: pointer;
        }

        .category-badge {
            display: inline-block;
            background: #f0f0f0;
            color: #333;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }

        .budget-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            color: white;
        }

        .budget-low {
            background: #4CAF50;
        }

        .budget-medium {
            background: #FF9800;
        }

        .budget-high {
            background: #f44336;
        }

        .action-buttons {
            display: flex;
            gap: 8px;
        }

        .btn-sm {
            padding: 6px 12px;
            font-size: 12px;
            border-radius: 4px;
            border: 1px solid #ddd;
            background: white;
            color: #333;
            cursor: pointer;
        }

        .btn-sm:hover {
            background: #f5f5f5;
        }

        .btn-sm.edit {
            border-color: #E04060;
            color: #E04060;
        }

        .btn-sm.delete {
            border-color: #ff4444;
            color: #ff4444;
        }

        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal.show {
            display: flex;
        }

        .modal-content {
            background: white;
            padding: 40px;
            border-radius: 12px;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            border-bottom: 1px solid #eee;
            padding-bottom: 15px;
        }

        .modal-header h2 {
            font-size: 22px;
            color: #1a1a1a;
        }

        .modal-close {
            background: none;
            border: none;
            font-size: 28px;
            cursor: pointer;
            color: #999;
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .modal-close:hover {
            color: #333;
        }

        .form-group {
            margin-bottom: 25px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #333;
        }

        .form-group input,
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
            transition: all 0.3s;
        }

        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }

        .form-group input:focus,
        .form-group textarea:focus,
        .form-group select:focus {
            outline: none;
            border-color: #E04060;
            box-shadow: 0 0 0 3px rgba(224, 64, 96, 0.1);
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .image-preview {
            width: 100%;
            max-width: 300px;
            height: 200px;
            border-radius: 6px;
            object-fit: cover;
            margin-bottom: 15px;
        }

        .modal-footer {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #999;
        }

        .empty-state {
            text-align: center;
            padding: 60px 40px;
            color: #999;
        }

        .empty-state p {
            font-size: 16px;
        }

        .pagination {
            display: flex;
            gap: 10px;
            justify-content: center;
            padding: 20px;
            background: #f8f8f8;
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

        .confirm-dialog {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            z-index: 1001;
            min-width: 400px;
        }

        .confirm-dialog p {
            margin-bottom: 20px;
            font-size: 16px;
            color: #333;
        }

        .confirm-dialog .modal-footer {
            margin-top: 20px;
        }

        .tag-input {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            min-height: 45px;
            align-items: center;
        }

        .tag {
            background: #E04060;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .tag button {
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            padding: 0;
            font-size: 16px;
            line-height: 1;
        }

        .tag-input input {
            border: none;
            padding: 0;
            flex: 1;
            min-width: 100px;
            font-size: 14px;
        }

        .tag-input input:focus {
            outline: none;
        }

        @media (max-width: 1024px) {
            .form-row {
                grid-template-columns: 1fr;
            }

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

            .btn-group {
                margin-left: 0;
                width: 100%;
            }

            .btn-group button {
                flex: 1;
            }

            table {
                font-size: 12px;
            }

            th, td {
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Arrow Admin Dashboard</h1>
            <div class="stats">
                <div class="stat-item">
                    <div class="label">Total Ideas</div>
                    <div class="value" id="totalIdeas">0</div>
                </div>
            </div>
        </header>

        <div class="controls">
            <div class="filter-group">
                <label for="categoryFilter">Category:</label>
                <select id="categoryFilter">
                    <option value="">All Categories</option>
                </select>
            </div>
            <div class="filter-group">
                <label for="searchInput">Search:</label>
                <input type="text" id="searchInput" placeholder="Search by title...">
            </div>
            <div class="btn-group">
                <button class="btn-primary" onclick="openCreateModal()">+ Add New Idea</button>
                <button class="btn-secondary" onclick="loadIdeas()">Refresh</button>
            </div>
        </div>

        <div class="table-container">
            <div id="tableContent">
                <div class="loading">Loading ideas...</div>
            </div>
        </div>
    </div>

    <!-- Edit Modal -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modalTitle">Edit Idea</h2>
                <button class="modal-close" onclick="closeModal('editModal')">&times;</button>
            </div>
            <form id="ideaForm" onsubmit="handleFormSubmit(event)">
                <div class="form-group">
                    <label for="ideaTitle">Title *</label>
                    <input type="text" id="ideaTitle" required>
                </div>

                <div class="form-group">
                    <label for="ideaDescription">Description *</label>
                    <textarea id="ideaDescription" required></textarea>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="ideaCategory">Category *</label>
                        <select id="ideaCategory" required>
                            <option value="romantic">Romantic</option>
                            <option value="adventure">Adventure</option>
                            <option value="foodie">Foodie</option>
                            <option value="creative">Creative</option>
                            <option value="relaxing">Relaxing</option>
                            <option value="fun">Fun</option>
                            <option value="cultural">Cultural</option>
                            <option value="active">Active</option>
                            <option value="entertainment">Entertainment</option>
                            <option value="nightlife">Nightlife</option>
                            <option value="meaningful">Meaningful</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="ideaBudget">Budget *</label>
                        <select id="ideaBudget" required>
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                        </select>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="ideaDuration">Duration *</label>
                        <input type="text" id="ideaDuration" placeholder="e.g., 2-3 hours" required>
                    </div>

                    <div class="form-group">
                        <label for="ideaLocationType">Location Type *</label>
                        <select id="ideaLocationType" required>
                            <option value="indoor">Indoor</option>
                            <option value="outdoor">Outdoor</option>
                            <option value="both">Both</option>
                        </select>
                    </div>
                </div>

                <div class="form-group">
                    <label for="ideaImageUrl">Image URL *</label>
                    <input type="url" id="ideaImageUrl" required>
                    <img id="imagePreview" class="image-preview" style="display: none;">
                </div>

                <div class="form-group">
                    <label for="ideaTags">Tags (press Enter to add)</label>
                    <div class="tag-input" id="tagInput">
                        <input type="text" id="tagInputField" placeholder="Add tags...">
                    </div>
                </div>

                <div class="modal-footer">
                    <button type="button" class="btn-secondary" onclick="closeModal('editModal')">Cancel</button>
                    <button type="submit" class="btn-primary">Save</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Confirm Delete Modal -->
    <div class="modal" id="confirmModal">
        <div class="confirm-dialog">
            <p>Are you sure you want to delete this idea?</p>
            <div class="modal-footer">
                <button class="btn-secondary" onclick="closeModal('confirmModal')">Cancel</button>
                <button class="btn-danger" onclick="confirmDelete()">Delete</button>
            </div>
        </div>
    </div>

    <script>
        let currentEditingId = null;
        let deletePendingId = null;
        let currentPage = 1;
        const itemsPerPage = 20;
        let currentTags = [];

        async function loadCategories() {
            try {
                const response = await fetch('/admin/api/categories');
                const categories = await response.json();
                const select = document.getElementById('categoryFilter');
                categories.forEach(cat => {
                    const option = document.createElement('option');
                    option.value = cat;
                    option.textContent = cat.charAt(0).toUpperCase() + cat.slice(1);
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Error loading categories:', error);
            }
        }

        async function loadIdeas() {
            currentPage = 1;
            renderTable();
        }

        async function renderTable() {
            const container = document.getElementById('tableContent');
            const category = document.getElementById('categoryFilter').value;
            const search = document.getElementById('searchInput').value;
            const offset = (currentPage - 1) * itemsPerPage;

            try {
                const params = new URLSearchParams({
                    category: category,
                    search: search,
                    limit: itemsPerPage,
                    offset: offset
                });

                const response = await fetch(`/admin/api/ideas?${params}`);
                const data = await response.json();
                const ideas = data.ideas || [];
                const total = data.total || 0;

                document.getElementById('totalIdeas').textContent = total;

                if (ideas.length === 0) {
                    container.innerHTML = '<div class="empty-state"><p>No ideas found</p></div>';
                    return;
                }

                let html = '<table><thead><tr><th>Image</th><th>Title</th><th>Category</th><th>Budget</th><th>Location</th><th>Duration</th><th>Image URL</th><th>Actions</th></tr></thead><tbody>';

                ideas.forEach(idea => {
                    const imageUrl = idea.image_url || '';
                    html += `<tr>
                        <td><img src="${escapeHtml(imageUrl)}" alt="Thumbnail" class="idea-thumbnail" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2250%22 height=%2250%22%3E%3Crect fill=%22%23ddd%22 width=%2250%22 height=%2250%22/%3E%3C/svg%3E'" /></td>
                        <td><strong>${escapeHtml(idea.title)}</strong></td>
                        <td><span class="category-badge">${escapeHtml(idea.category)}</span></td>
                        <td><span class="budget-badge budget-${idea.budget}">${idea.budget}</span></td>
                        <td>${escapeHtml(idea.location_type)}</td>
                        <td>${escapeHtml(idea.duration)}</td>
                        <td><a href="${escapeHtml(imageUrl)}" target="_blank" style="color: #E04060; text-decoration: none; font-size: 12px;">View</a></td>
                        <td>
                            <div class="action-buttons">
                                <button class="btn-sm edit" onclick="openEditModal('${idea.id}')">Edit</button>
                                <button class="btn-sm delete" onclick="openDeleteConfirm('${idea.id}')">Delete</button>
                            </div>
                        </td>
                    </tr>`;
                });

                html += '</tbody></table>';
                container.innerHTML = html;

                // Add pagination if needed
                if (total > itemsPerPage) {
                    const totalPages = Math.ceil(total / itemsPerPage);
                    let paginationHtml = '<div class="pagination">';
                    if (currentPage > 1) {
                        paginationHtml += '<button onclick="currentPage--; renderTable()">Previous</button>';
                    }
                    for (let i = 1; i <= totalPages; i++) {
                        paginationHtml += `<button class="${i === currentPage ? 'active' : ''}" onclick="currentPage = ${i}; renderTable()">${i}</button>`;
                    }
                    if (currentPage < totalPages) {
                        paginationHtml += '<button onclick="currentPage++; renderTable()">Next</button>';
                    }
                    paginationHtml += '</div>';
                    container.innerHTML += paginationHtml;
                }
            } catch (error) {
                console.error('Error loading ideas:', error);
                container.innerHTML = '<div class="empty-state"><p>Error loading ideas</p></div>';
            }
        }

        async function openEditModal(ideaId) {
            currentEditingId = ideaId;
            currentTags = [];
            document.getElementById('modalTitle').textContent = 'Edit Idea';

            try {
                const response = await fetch(`/admin/api/ideas/${ideaId}`);
                const idea = await response.json();

                document.getElementById('ideaTitle').value = idea.title;
                document.getElementById('ideaDescription').value = idea.description;
                document.getElementById('ideaCategory').value = idea.category;
                document.getElementById('ideaBudget').value = idea.budget;
                document.getElementById('ideaDuration').value = idea.duration;
                document.getElementById('ideaLocationType').value = idea.location_type;
                document.getElementById('ideaImageUrl').value = idea.image_url || '';

                if (idea.tags && Array.isArray(idea.tags)) {
                    currentTags = [...idea.tags];
                    renderTags();
                }

                if (idea.image_url) {
                    document.getElementById('imagePreview').src = idea.image_url;
                    document.getElementById('imagePreview').style.display = 'block';
                }

                document.getElementById('editModal').classList.add('show');
            } catch (error) {
                console.error('Error loading idea:', error);
                alert('Error loading idea');
            }
        }

        function openCreateModal() {
            currentEditingId = null;
            currentTags = [];
            document.getElementById('modalTitle').textContent = 'Create New Idea';
            document.getElementById('ideaForm').reset();
            document.getElementById('imagePreview').style.display = 'none';
            document.getElementById('tagInputField').value = '';
            renderTags();
            document.getElementById('editModal').classList.add('show');
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('show');
        }

        async function handleFormSubmit(event) {
            event.preventDefault();

            const ideaData = {
                title: document.getElementById('ideaTitle').value,
                description: document.getElementById('ideaDescription').value,
                category: document.getElementById('ideaCategory').value,
                budget: document.getElementById('ideaBudget').value,
                duration: document.getElementById('ideaDuration').value,
                location_type: document.getElementById('ideaLocationType').value,
                image_url: document.getElementById('ideaImageUrl').value,
                tags: currentTags
            };

            try {
                let response;
                if (currentEditingId) {
                    response = await fetch(`/admin/api/ideas/${currentEditingId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(ideaData)
                    });
                } else {
                    response = await fetch('/admin/api/ideas', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(ideaData)
                    });
                }

                if (response.ok) {
                    closeModal('editModal');
                    loadIdeas();
                } else {
                    const error = await response.json();
                    alert('Error: ' + (error.detail || 'Failed to save'));
                }
            } catch (error) {
                console.error('Error saving idea:', error);
                alert('Error saving idea');
            }
        }

        function openDeleteConfirm(ideaId) {
            deletePendingId = ideaId;
            document.getElementById('confirmModal').classList.add('show');
        }

        async function confirmDelete() {
            if (!deletePendingId) return;

            try {
                const response = await fetch(`/admin/api/ideas/${deletePendingId}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    closeModal('confirmModal');
                    loadIdeas();
                } else {
                    alert('Error deleting idea');
                }
            } catch (error) {
                console.error('Error deleting idea:', error);
                alert('Error deleting idea');
            }
        }

        function renderTags() {
            const container = document.getElementById('tagInput');
            const existingTags = container.querySelectorAll('.tag');
            existingTags.forEach(tag => tag.remove());

            const input = container.querySelector('input');
            currentTags.forEach((tag, index) => {
                const tagEl = document.createElement('span');
                tagEl.className = 'tag';
                tagEl.innerHTML = `${escapeHtml(tag)} <button type="button" onclick="removeTag(${index})">&times;</button>`;
                container.insertBefore(tagEl, input);
            });
        }

        function removeTag(index) {
            currentTags.splice(index, 1);
            renderTags();
        }

        // Handle tag input
        document.addEventListener('DOMContentLoaded', function() {
            const tagInput = document.getElementById('tagInputField');
            if (tagInput) {
                tagInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        const value = this.value.trim();
                        if (value && !currentTags.includes(value)) {
                            currentTags.push(value);
                            this.value = '';
                            renderTags();
                        }
                    }
                });
            }

            // Preview image on URL change
            document.getElementById('ideaImageUrl').addEventListener('change', function() {
                if (this.value) {
                    document.getElementById('imagePreview').src = this.value;
                    document.getElementById('imagePreview').style.display = 'block';
                }
            });

            loadCategories();
            loadIdeas();
        });

        // Filter changes
        document.getElementById('categoryFilter').addEventListener('change', loadIdeas);
        document.getElementById('searchInput').addEventListener('input', loadIdeas);

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>"""

# ==================== API ENDPOINTS ====================

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard HTML"""
    return HTML_DASHBOARD

@router.get("/api/ideas")
async def list_ideas(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
):
    """List all date ideas with filters and pagination"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        # Build query
        query = "SELECT * FROM date_ideas WHERE 1=1"
        params = []
        param_count = 0

        if category:
            param_count += 1
            query += f" AND category = ${param_count}"
            params.append(category)

        if search:
            param_count += 1
            query += f" AND (title ILIKE ${param_count} OR description ILIKE ${param_count})"
            search_term = f"%{search}%"
            params.append(search_term)
            params.append(search_term)
            param_count += 1

        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total = await conn.fetchval(count_query, *params)

        # Add pagination
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

@router.get("/api/ideas/{idea_id}")
async def get_idea(idea_id: str):
    """Get a specific date idea"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        idea_uuid = uuid.UUID(idea_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid idea ID")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM date_ideas WHERE id = $1", idea_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")

        idea = dict(row)
        idea['id'] = str(idea['id'])
        return idea

@router.post("/api/ideas")
async def create_idea(idea_data: Dict[str, Any] = Body(...)):
    """Create a new date idea"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Validate required fields
    required_fields = ['title', 'description', 'category', 'budget', 'duration', 'location_type', 'image_url']
    for field in required_fields:
        if field not in idea_data or not idea_data[field]:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    idea_id = uuid.uuid4()
    tags = idea_data.get('tags', [])

    async with db_pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO date_ideas
                (id, title, description, category, budget, duration, location_type, image_url, tags, source, updated_at, updated_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), $11)
            ''', idea_id, idea_data['title'], idea_data['description'], idea_data['category'],
               idea_data['budget'], idea_data['duration'], idea_data['location_type'],
               idea_data['image_url'], tags, 'admin', 'admin_dashboard')

            return {
                "success": True,
                "id": str(idea_id),
                "message": "Idea created successfully"
            }
        except Exception as e:
            logger.error(f"Error creating idea: {e}")
            raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/ideas/{idea_id}")
async def update_idea(idea_id: str, idea_data: Dict[str, Any] = Body(...)):
    """Update a date idea - supports partial updates"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        idea_uuid = uuid.UUID(idea_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid idea ID")

    async with db_pool.acquire() as conn:
        # Check if idea exists and get current data
        existing = await conn.fetchrow("SELECT * FROM date_ideas WHERE id = $1", idea_uuid)
        if not existing:
            raise HTTPException(status_code=404, detail="Idea not found")

        # Merge with existing data - only update fields that are provided
        title = idea_data.get('title', existing['title'])
        description = idea_data.get('description', existing['description'])
        category = idea_data.get('category', existing['category'])
        budget = idea_data.get('budget', existing['budget'])
        duration = idea_data.get('duration', existing.get('duration', ''))
        location_type = idea_data.get('location_type', existing.get('location_type', 'both'))
        image_url = idea_data.get('image_url', existing.get('image_url', ''))
        tags = idea_data.get('tags', existing.get('tags', []))
        location = idea_data.get('location', existing.get('location', ''))

        try:
            await conn.execute('''
                UPDATE date_ideas
                SET title = $1, description = $2, category = $3, budget = $4,
                    duration = $5, location_type = $6, image_url = $7, tags = $8,
                    updated_at = NOW(), updated_by = $9
                WHERE id = $10
            ''', title, description, category, budget, duration, location_type,
               image_url, tags, 'admin_dashboard', idea_uuid)

            return {
                "success": True,
                "message": "Idea updated successfully"
            }
        except Exception as e:
            logger.error(f"Error updating idea: {e}")
            raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api/ideas/{idea_id}")
async def delete_idea(idea_id: str):
    """Delete a date idea"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        idea_uuid = uuid.UUID(idea_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid idea ID")

    async with db_pool.acquire() as conn:
        # Check if idea exists
        existing = await conn.fetchrow("SELECT id FROM date_ideas WHERE id = $1", idea_uuid)
        if not existing:
            raise HTTPException(status_code=404, detail="Idea not found")

        try:
            await conn.execute("DELETE FROM date_ideas WHERE id = $1", idea_uuid)
            return {
                "success": True,
                "message": "Idea deleted successfully"
            }
        except Exception as e:
            logger.error(f"Error deleting idea: {e}")
            raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/categories")
async def list_categories():
    """Get all unique categories"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT category FROM date_ideas ORDER BY category")
        categories = [row['category'] for row in rows if row['category']]
        return categories

@router.put("/api/ideas/{idea_id}/image")
async def update_idea_image(idea_id: str, image_data: Dict[str, str] = Body(...)):
    """Update just the image URL for an idea"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        idea_uuid = uuid.UUID(idea_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid idea ID")

    image_url = image_data.get('image_url')
    if not image_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    async with db_pool.acquire() as conn:
        # Check if idea exists
        existing = await conn.fetchrow("SELECT id FROM date_ideas WHERE id = $1", idea_uuid)
        if not existing:
            raise HTTPException(status_code=404, detail="Idea not found")

        try:
            await conn.execute(
                "UPDATE date_ideas SET image_url = $1, updated_at = NOW() WHERE id = $2",
                image_url, idea_uuid
            )
            return {
                "success": True,
                "message": "Image updated successfully"
            }
        except Exception as e:
            logger.error(f"Error updating image: {e}")
            raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/stats")
async def get_stats():
    """Get dashboard statistics"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM date_ideas")

        # By category
        category_rows = await conn.fetch(
            "SELECT category, COUNT(*) as count FROM date_ideas GROUP BY category ORDER BY count DESC"
        )
        by_category = {row['category']: row['count'] for row in category_rows}

        # By source
        source_rows = await conn.fetch(
            "SELECT COALESCE(source, 'unknown') as source, COUNT(*) as count FROM date_ideas GROUP BY source"
        )
        by_source = {row['source']: row['count'] for row in source_rows}

        return {
            "total_ideas": total,
            "by_category": by_category,
            "by_source": by_source
        }
