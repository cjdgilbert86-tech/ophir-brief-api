# Ophir Brief API — Deployment Guide

Four files. Five minutes. No code knowledge required.

---

## What you're deploying

A small private API that sits inside your Railway project alongside your existing Postgres database. It reads your pipeline data and serves it as JSON. Only requests with your secret API key can access it.

---

## Step 1 — Create a GitHub repository

1. Go to https://github.com/new
2. Name it `ophir-brief-api` (private is fine)
3. Click **Create repository**
4. Upload the four files from this folder:
   - `main.py`
   - `requirements.txt`
   - `Procfile`
   - `railway.toml`
   - (You can drag all four into the GitHub file upload screen)
5. Click **Commit changes**

---

## Step 2 — Create a new service in Railway

1. Open your Railway project (the one with your Postgres database)
2. Click **+ New** → **GitHub Repo**
3. Select `ophir-brief-api`
4. Railway will detect Python automatically and start building

---

## Step 3 — Link your Postgres database

Railway needs to tell the new service where your database lives.

1. Click on your new `ophir-brief-api` service
2. Go to **Variables** tab
3. Click **+ Add Variable Reference**
4. Select your Postgres service → choose `DATABASE_URL`
5. This injects the connection string automatically — you never have to paste it manually

---

## Step 4 — Set your API key

Still in the **Variables** tab:

1. Click **+ New Variable**
2. Name: `OPHIR_API_KEY`
3. Value: choose any secret string, e.g. `ophir-brief-2026`
   (Write this down — you'll share it with Claude at the start of each newsletter session)
4. Click **Add**

---

## Step 5 — Get your public URL

1. Click the **Settings** tab on the service
2. Under **Networking**, click **Generate Domain**
3. Copy the URL — it will look like `ophir-brief-api.up.railway.app`

---

## Step 6 — Test it

Open your browser and go to:

```
https://your-url.up.railway.app/health
```

You should see: `{"status":"ok","service":"ophir-brief-api"}`

If you see that, the API is live and connected to your database.

---

## How to use it in Claude

At the start of each newsletter session, tell Claude:

> "Fetch my newsletter data. The endpoint is https://your-url.up.railway.app/newsletter and the API key is [your key]."

Claude will fetch the data and you can go straight into planning the issue.

---

## Endpoints

| Endpoint | Returns |
|---|---|
| `/health` | Status check (no auth needed) |
| `/newsletter` | Everything at once — use this one |
| `/pipeline` | All pipeline deals |
| `/quotes` | Notable founder/investor quotes |
| `/themes` | Themes being tracked |
| `/themes-detail` | Theme entries and evidence |
| `/meetings` | Meeting log |
| `/hypotheses` | Investment hypotheses |

All endpoints except `/health` require the header `x-api-key: [your key]`.
