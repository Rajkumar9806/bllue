# Smart Algorithm - Deployment Checklist

## Pre-Deployment Verification

### Code Quality
- [ ] All files compile without syntax errors
- [ ] No import errors when running main.py
- [ ] Type hints present throughout
- [ ] Logging configured properly
- [ ] Error handling in place for all functions

**Verification commands:**
```bash
# Check syntax
python3 -m py_compile smart_algorithm.py
python3 -m py_compile main.py

# Check imports
cd /sessions/jolly-elegant-bohr/bllue/backend
python3 -c "from smart_algorithm import compute_user_preferences, build_smart_prompt"
```

### Database Requirements
- [ ] `idea_interactions` table exists with columns:
  - `user_id` (UUID, FK to users)
  - `date_idea_id` (UUID, FK to date_ideas)
  - `action` ('accepted' or 'rejected')
  - `created_at` (TIMESTAMP)
- [ ] `date_ideas` table has `category`, `budget`, `location_type`, `tags` columns
- [ ] `users` table has personality and preference columns
- [ ] Indexes exist on `idea_interactions(user_id, date_idea_id)`

**Verification query:**
```sql
-- Check tables exist
SELECT tablename FROM pg_tables
WHERE tablename IN ('idea_interactions', 'date_ideas', 'users');

-- Check columns
SELECT column_name FROM information_schema.columns
WHERE table_name = 'idea_interactions';
```

### Environment Configuration
- [ ] `DATABASE_URL` set correctly (test before deploy)
- [ ] `ENVIRONMENT` set to 'production' if applicable
- [ ] `AI_PROVIDER` set to preferred provider (gemini/claude/openai)
- [ ] Required API keys set for chosen provider:
  - [ ] `GEMINI_API_KEY` (if using Gemini)
  - [ ] `ANTHROPIC_API_KEY` (if using Claude)
  - [ ] `OPENAI_API_KEY` (if using OpenAI)
- [ ] `JWT_SECRET` configured
- [ ] `OPENWEATHER_API_KEY` set (optional but recommended)

**Environment variable checklist:**
```bash
# Required
echo "DATABASE_URL: $DATABASE_URL"
echo "JWT_SECRET: ${JWT_SECRET:0:20}... (first 20 chars)"
echo "AI_PROVIDER: $AI_PROVIDER"

# Conditional (at least one)
echo "GEMINI_API_KEY: ${GEMINI_API_KEY:0:10}... (set: $([[ -n $GEMINI_API_KEY ]] && echo yes || echo no))"
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}... (set: $([[ -n $ANTHROPIC_API_KEY ]] && echo yes || echo no))"
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}... (set: $([[ -n $OPENAI_API_KEY ]] && echo yes || echo no))"

# Optional
echo "OPENWEATHER_API_KEY: ${OPENWEATHER_API_KEY:0:10}... (set: $([[ -n $OPENWEATHER_API_KEY ]] && echo yes || echo no))"
```

### API Endpoints
- [ ] All 4 new endpoints registered:
  - [ ] `GET /api/recommendations/smart`
  - [ ] `GET /api/recommendations/preferences`
  - [ ] `GET /api/recommendations/mood-options`
  - [ ] `GET /api/recommendations/partner-compatibility`
- [ ] Endpoints appear in FastAPI OpenAPI docs
- [ ] Authentication required for all endpoints (except mood-options if desired)

**Verification:**
```bash
# Start server and check docs
curl http://localhost:8000/docs | grep "smart\|preferences\|mood"
```

### Documentation
- [ ] `SMART_ALGORITHM.md` reviewed
- [ ] `SMART_ALGORITHM_QUICK_REF.md` available to team
- [ ] `IMPLEMENTATION_SUMMARY.md` read and understood
- [ ] Team trained on new features
- [ ] Examples run and understood

---

## Deployment Steps

### Step 1: Code Deployment
```bash
# Copy new files to server
scp /sessions/jolly-elegant-bohr/bllue/backend/smart_algorithm.py user@server:/path/to/backend/
scp /sessions/jolly-elegant-bohr/bllue/backend/SMART_ALGORITHM*.md user@server:/path/to/backend/

# Update main.py (or merge changes)
scp /sessions/jolly-elegant-bohr/bllue/backend/main.py user@server:/path/to/backend/
```

### Step 2: Dependencies
No new dependencies needed! Uses existing:
- asyncpg (already in requirements)
- httpx (already in requirements)
- fastapi (already in requirements)

Verify in your requirements.txt:
```bash
grep -E "asyncpg|httpx|fastapi" requirements.txt
```

### Step 3: Database Verification
```bash
# Connect to production database
psql $DATABASE_URL

# Verify tables
\dt idea_interactions date_ideas users

# Verify sample data exists
SELECT COUNT(*) FROM idea_interactions;
SELECT COUNT(*) FROM date_ideas;

# Check recent interactions (last 10)
SELECT id, user_id, action, created_at
FROM idea_interactions
ORDER BY created_at DESC
LIMIT 10;
```

### Step 4: Server Startup
```bash
# Start/restart your FastAPI server
# (depends on your deployment setup)

# Verify no startup errors
tail -f /var/log/arrow_api.log | grep -E "ERROR|WARN|smart"

# Check health
curl http://localhost:8000/api/health
```

### Step 5: API Testing
```bash
# Test unauthenticated endpoint (mood options)
curl http://localhost:8000/api/recommendations/mood-options

# For authenticated endpoints, first get a token:
TOKEN=$(curl -X POST http://localhost:8000/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+1234567890"}' | jq -r '.token')

# Then test authenticated endpoints
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/recommendations/preferences

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/recommendations/smart

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/recommendations/partner-compatibility
```

### Step 6: Monitoring
```bash
# Monitor for errors
tail -f /var/log/arrow_api.log | grep "ERROR"

# Check response times
curl -w "@curl-format.txt" -o /dev/null -s \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/recommendations/smart

# Expected response time: 1-2 seconds (includes AI generation)
```

---

## Post-Deployment Verification

### Functionality Tests
- [ ] `/api/recommendations/mood-options` returns all 6 moods
- [ ] `/api/recommendations/smart` returns 5 ideas with AI generation
- [ ] `/api/recommendations/preferences` returns user profile (or fallback)
- [ ] `/api/recommendations/partner-compatibility` works for couple users
- [ ] All endpoints require authentication (except mood-options if configured)
- [ ] Error responses have proper HTTP status codes

### Integration Tests
```bash
# Full workflow test
1. User accepts 5-10 ideas
2. Check preferences endpoint - should show confidence="low" or "medium"
3. Get smart recommendations - should use learned preferences
4. For couples - check partner compatibility score

# Edge case tests
1. New user (0 interactions) - should fallback to questionnaire
2. Power user (20+ interactions) - should use behavioral data
3. Missing partner - should handle gracefully
4. No API key for AI provider - should return 500 with clear error
5. Weather API unavailable - should skip weather, continue normally
```

### Performance Baselines
Document these for monitoring:

| Endpoint | Expected Time | Notes |
|----------|---------------|-------|
| `/recommendations/mood-options` | <100ms | No AI |
| `/recommendations/preferences` | ~100ms | Depends on interaction count |
| `/recommendations/smart` | 1-2s | Includes AI generation |
| `/recommendations/partner-compatibility` | ~200ms | No AI |

Monitor actual times:
```bash
# Log response times for analysis
grep "recommendations" /var/log/arrow_api.log | grep "duration"
```

### User Acceptance
- [ ] Team tested with real users
- [ ] Mood options resonate with users
- [ ] Recommendations improve with interactions
- [ ] Partner compatibility feature works as expected
- [ ] Users see personality evolution insights

---

## Rollback Plan

If issues occur:

### Option 1: Disable Smart Algorithm (Keep Old System)
```python
# In main.py, comment out new endpoints or route to old system
# Old endpoints still available: /api/date-ideas/ai-personalized

# Or add feature flag:
ENABLE_SMART_ALGORITHM = os.getenv("ENABLE_SMART_ALGORITHM", "true")

@app.get("/api/recommendations/smart")
async def get_smart_recommendations(...):
    if not ENABLE_SMART_ALGORITHM:
        # Fall back to old system
        return await generate_ai_date_ideas(...)
```

### Option 2: Revert to Previous Code
```bash
# Assuming git is used
git revert HEAD
git push
# Restart server
```

### Option 3: Database Rollback
No schema changes were made to database. Only reading from existing tables.
No rollback needed at DB level.

---

## Success Criteria

All of these should be true:

- [ ] Server starts without errors
- [ ] All 4 new endpoints accessible
- [ ] Database queries execute properly
- [ ] AI provider integration works
- [ ] Cold start users get questionnaire fallback
- [ ] Power users (15+) get behavior-driven recommendations
- [ ] Mood selection weights recommendations
- [ ] Partner compatibility scores make sense
- [ ] Weather integration works (or gracefully skips)
- [ ] Logging shows normal operation
- [ ] No SQL errors in logs
- [ ] No AI provider errors (unless API key missing)
- [ ] Response times acceptable (1-2s for smart)
- [ ] Users report better recommendations over time

---

## Common Issues & Solutions

### Issue: "Module smart_algorithm not found"
**Solution:** Ensure smart_algorithm.py is in same directory as main.py

### Issue: "KeyError: 'user_id' in compute_user_preferences"
**Solution:** Verify user exists in database and token is valid

### Issue: "JSON decode error" in smart recommendations
**Solution:**
- Check AI provider is configured correctly
- Verify API key is valid
- Check logs for AI provider error message

### Issue: "Weather not working"
**Solution:**
- This is expected if OPENWEATHER_API_KEY not set
- System gracefully skips weather
- Set env var to enable

### Issue: "Partner compatibility always 0%"
**Solution:**
- This is valid data (partners have no shared preferences)
- Check partner_id is correct
- Check both users have interaction history

### Issue: "Confidence level always 'low'"
**Solution:**
- Users need 5+ interactions to reach 'medium'
- Need 15+ to reach 'high'
- This is expected behavior
- System works correctly, just needs more data

---

## Monitoring Script

Save as `monitor_smart_algorithm.sh`:

```bash
#!/bin/bash

echo "=== Smart Algorithm Monitoring ==="
echo "Time: $(date)"
echo ""

# Check endpoints available
echo "Endpoints:"
curl -s http://localhost:8000/docs | grep -o "smart\|preferences\|mood-options\|partner" | sort -u

echo ""
echo "Recent errors in logs:"
tail -20 /var/log/arrow_api.log | grep "ERROR\|WARN" || echo "No recent errors"

echo ""
echo "Recent interaction count:"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM idea_interactions;"

echo ""
echo "Users with high confidence (15+ interactions):"
psql $DATABASE_URL -c "SELECT user_id, COUNT(*) as interactions FROM idea_interactions GROUP BY user_id HAVING COUNT(*) >= 15 LIMIT 5;"
```

Run with: `bash monitor_smart_algorithm.sh`

---

## Sign-Off

- [ ] Code reviewed by: _______________
- [ ] QA testing completed by: _______________
- [ ] Database verified by: _______________
- [ ] Deployment executed by: _______________
- [ ] Post-deployment verification by: _______________

**Date deployed:** _______________
**Version:** 1.0.0
**Status:** ☐ Successful ☐ Rollback Required

---

## Additional Resources

- Full documentation: `SMART_ALGORITHM.md`
- Quick reference: `SMART_ALGORITHM_QUICK_REF.md`
- Examples: `smart_algorithm_examples.py` (run to see scenarios)
- Implementation summary: `IMPLEMENTATION_SUMMARY.md`

Questions? Check documentation first, then contact dev team.
