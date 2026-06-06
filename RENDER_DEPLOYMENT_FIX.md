# Render Deployment Configuration Fix

## Problem

The application is experiencing 403 Forbidden and 421 Misdirected Request errors because:
1. Frontend nginx is not configured with the correct backend URL
2. CORS and Host headers are not properly set for split deployment
3. The frontend is trying to proxy to `http://backend:8000` which doesn't exist on Render

## Solution

### Backend Service Configuration

**Environment Variables to Set:**

```env
# Required
DATABASE_URL=<your-postgres-url-from-render>
GROQ_API_KEY=<your-groq-key>

# App Config
APP_ENV=production
PORT=8000
LOG_LEVEL=INFO

# CORS - CRITICAL FOR SPLIT DEPLOYMENT
CORS_ALLOW_ORIGINS=https://nexacore-frontend.onrender.com
FRONTEND_URL=https://nexacore-frontend.onrender.com

# Auth (currently disabled, can enable later)
AUTH_REQUIRED=false

# Integrations
INTEGRATIONS_MODE=demo
HINDSIGHT_BACKEND=local

# Cache (if using Redis, otherwise leave empty)
# REDIS_URL=<your-redis-url>
```

**Service Settings:**
- **Region:** Same as frontend (for lower latency)
- **Instance Type:** At least 512MB RAM
- **Health Check Path:** `/health`
- **Auto-Deploy:** Yes

### Frontend Service Configuration

**Environment Variables to Set:**

```env
# CRITICAL: Point to your backend service
BACKEND_URL=https://<your-backend-service-name>.onrender.com
BACKEND_HOST=<your-backend-service-name>.onrender.com

# Build-time variable
VITE_API_BASE=/api
```

**Example with actual service name:**
```env
BACKEND_URL=https://nexacore-backend.onrender.com
BACKEND_HOST=nexacore-backend.onrender.com
VITE_API_BASE=/api
```

**Service Settings:**
- **Dockerfile Path:** `frontend/Dockerfile`
- **Docker Build Context:** `.` (root directory)
- **Port:** 80
- **Health Check Path:** `/`
- **Auto-Deploy:** Yes

### Deployment Order

1. **Deploy Backend First:**
   - Create the backend web service
   - Set all environment variables listed above
   - Wait for it to be live and note the URL
   - Test: `curl https://your-backend.onrender.com/health`

2. **Deploy Frontend Second:**
   - Create the frontend web service
   - Set `BACKEND_URL` to your actual backend URL
   - Set `BACKEND_HOST` to match the hostname
   - Deploy

3. **Verify:**
   - Visit `https://nexacore-frontend.onrender.com`
   - Open browser console
   - Try to create a session
   - Should work without 403/421 errors

## Quick Verification Commands

Test backend directly:
```bash
curl https://your-backend.onrender.com/health
curl https://your-backend.onrender.com/ready
```

Test frontend nginx proxy:
```bash
curl https://nexacore-frontend.onrender.com/api/health
```

## Common Issues

### Issue 1: Still getting 421 errors
**Cause:** `BACKEND_HOST` doesn't match the actual backend hostname
**Fix:** Ensure `BACKEND_HOST` exactly matches the domain in `BACKEND_URL`

### Issue 2: CORS errors in browser
**Cause:** Backend doesn't allow frontend origin
**Fix:** Set `CORS_ALLOW_ORIGINS` on backend to include frontend URL

### Issue 3: Backend worker timeout
**Cause:** Startup takes > 180s
**Fix:** Already applied in latest commit - increased timeout and made startup more resilient

### Issue 4: 403 Forbidden everywhere
**Cause:** `AUTH_REQUIRED=true` but no API key provided
**Fix:** Either:
- Set `AUTH_REQUIRED=false` on backend (for demo/dev)
- OR set `APP_API_KEY` and send it from frontend

## Architecture Diagram

```
Browser → https://nexacore-frontend.onrender.com
            ↓
         Nginx Container
            ↓
        /api/* requests proxied to
            ↓
         https://nexacore-backend.onrender.com
            ↓
         FastAPI + Gunicorn
            ↓
         PostgreSQL Database
```

## Files Updated in Latest Commit

1. `backend/agent/agent.py` - Made GROQ_API_KEY optional
2. `backend/server.py` - Skip agent warmup if no key, better logging
3. `backend/gunicorn.conf.py` - Increased timeout to 180s
4. `backend/memory/hindsight_client.py` - Better error handling

## Next Steps

1. **Update environment variables** on both Render services as shown above
2. **Redeploy both services** (backend first, then frontend)
3. **Monitor logs** for any remaining issues
4. **Test the application** end-to-end

## Support

If you continue to see issues:
1. Check Render logs for both services
2. Verify environment variables are set correctly
3. Test backend health endpoint directly
4. Check browser network tab for exact error responses
