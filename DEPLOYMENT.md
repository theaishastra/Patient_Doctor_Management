# Deployment Guide - Healthcare Portal on Render

This guide walks through deploying the Healthcare Portal to Render.

## Prerequisites

- Render account (free tier available at https://render.com)
- GitHub account (to connect your repo)
- Supabase account and project set up

## Step 1: Push Code to GitHub

```bash
cd d:\health_care
git init
git add .
git commit -m "Initial commit: Healthcare Portal with chat system"
git remote add origin https://github.com/YOUR_USERNAME/health-care.git
git branch -M main
git push -u origin main
```

## Step 2: Create a Render Web Service

1. Go to https://render.com/dashboard
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Fill in the details:
   - **Name:** `healthcare-portal`
   - **Environment:** `Python 3`
   - **Region:** `Oregon` (or your preference)
   - **Plan:** `Free` (or upgrade for better performance)
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && python main.py`
   - **Python Version:** `3.10.13`

## Step 3: Set Environment Variables

In the Render dashboard, under **"Environment"**, add:

```
SUPABASE_URL=https://lycbzpjckxdzuvpmtmsr.supabase.co
SUPABASE_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
ENV=production
HOST=0.0.0.0
```

Get these values from your Supabase project:
- Dashboard → Settings → API
  - `SUPABASE_URL` = Project URL
  - `SUPABASE_KEY` = "anon" public key
  - `SUPABASE_SERVICE_ROLE_KEY` = service_role secret key

## Step 4: Deploy

1. Click **"Create Web Service"**
2. Render will start building and deploying
3. Wait for the "Deployed" status (usually 2-5 minutes)
4. Your app will be available at: `https://healthcare-portal.onrender.com`

## Step 5: Update Frontend API URL (if needed)

If the frontend is making API calls to `http://127.0.0.1:8000`, update it:

**In `frontend/js/api.js`:**
```javascript
const BASE_URL = "https://healthcare-portal.onrender.com"; // Update this
```

Since the frontend and backend are served from the same URL on Render, the API calls should work as-is.

## Step 6: Test the Deployment

1. Go to `https://healthcare-portal.onrender.com`
2. Log in with demo credentials:
   - **Admin:** `admin@medvitals.com` / `Password123!`
   - **Doctor:** `doctor1@medvitals.com` / `Password123!`
   - **Patient:** `patient1@medvitals.com` / `Password123!`
3. Test chat functionality
4. Open DevTools → Network tab and verify no repeated API calls when switching sections

## Troubleshooting

### "Port is already in use"
- This shouldn't happen on Render (it provides a free port)
- Check logs in Render dashboard

### "Frontend directory not found"
- Render is running from root, not from `backend/`
- The build command handles this: `cd backend && python main.py`

### CORS errors
- Update `FRONTEND_URL` environment variable in Render dashboard
- Or update the `CORS` configuration in `main.py`

### Supabase connection fails
- Verify credentials in `.env` match those in Render environment variables
- Check Supabase project is active and not expired
- Verify network/firewall allows Supabase connections

## Continuous Deployment

Render automatically deploys when you push to the `main` branch on GitHub.

To trigger a manual redeploy:
1. Go to Render dashboard
2. Click your service
3. Click **"Manual Deploy"** → **"Deploy latest commit"**

## Production Checklist

- [ ] Environment variables set in Render dashboard
- [ ] Frontend API URL updated (if not using same domain)
- [ ] CORS origins configured correctly
- [ ] Supabase backups enabled
- [ ] Database RLS policies verified
- [ ] Test login, chat, and section switching
- [ ] Monitor Render logs for errors

## Upgrading from Free to Paid

If your app gets traffic and you need more resources:
1. Render dashboard → Click your service
2. Click **"Settings"** → **"Plan"**
3. Select **Pro** ($7/month) or higher
4. Render will keep your URL and data

## Rolling Back

If a deployment breaks:
1. Render dashboard → Click your service
2. Click **"Activity"** tab
3. Find a previous successful deployment
4. Click the deployment and select **"Redeploy"**

Your app will revert to that version in seconds.

## Next Steps

- Set up monitoring (Sentry, DataDog)
- Configure custom domain (Render → Settings → Custom Domain)
- Enable SSL/TLS (automatic with Render)
- Set up email notifications for deployment failures

---

Questions? Check Render docs: https://render.com/docs
