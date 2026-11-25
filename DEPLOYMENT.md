# Deployment Information

## Public URL
https://k5-l3a-day14-kimducthang-2a202603702.onrender.com

## Platform
Render (Docker Web Service + Render Key Value / Redis)

## Test Commands

### Health Check
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://k5-l3a-day14-kimducthang-2a202603702.onrender.com/health"
# Expected: 200
```

### Readiness Check
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://k5-l3a-day14-kimducthang-2a202603702.onrender.com/ready"
# Expected: 200
```

### API Test (no key → 401, with X-API-Key → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://k5-l3a-day14-kimducthang-2a202603702.onrender.com/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 401

curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://k5-l3a-day14-kimducthang-2a202603702.onrender.com/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question": "Hello"}'
# Expected: 200
```

## Environment Variables Set
- `PORT` (injected by Render: `10000`)
- `REDIS_URL` (Internal Redis URL from `day14-redis`)
- `AGENT_API_KEY` (configured in Render Dashboard)
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
