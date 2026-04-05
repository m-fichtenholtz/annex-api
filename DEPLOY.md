# ANNEX v3 API — Deploy Guide

## Folder Structure
```
annex_v3_api/
├── main.py
├── requirements.txt
├── render.yaml
├── .env.example
├── scraper/
│   ├── __init__.py
│   ├── truepeoplesearch.py
│   └── image_search.py
└── ai/
    ├── __init__.py
    └── extractor.py
```

## Step 1 — Push to GitHub
1. Create a new private GitHub repo (e.g. `annex-api`)
2. Upload all files in this folder to that repo

## Step 2 — Deploy on Render.com (Free)
1. Go to render.com → sign up free
2. New → Web Service → Connect GitHub repo
3. Render auto-detects `render.yaml`
4. Set environment variables (DO NOT put these in code):
   - `GROQ_API_KEY` = your new Groq key
   - `ADMIN_SECRET` = make up a strong random string (e.g. `annex_k9x2mQ7p`)
   - `ALLOWED_ORIGIN` = your cPanel domain (e.g. `https://clarusdeck.institute`)
5. Deploy — Render gives you a URL like `https://annex-api.onrender.com`

## Step 3 — Note your API URL
Save: `https://annex-api.onrender.com`
This is what your cPanel PHP calls.

## Step 4 — Test the API
```bash
curl -X GET https://annex-api.onrender.com/health
# Should return: {"status":"online","service":"ANNEX API v3"}

curl -X POST https://annex-api.onrender.com/scrape/truepeoplesearch \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: YOUR_ADMIN_SECRET" \
  -d '{"name":"John Doe","location":"Phoenix, AZ"}'
```

## Environment Variables Reference
| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key (from console.groq.com) |
| `ADMIN_SECRET` | Shared secret between PHP frontend and this API |
| `ALLOWED_ORIGIN` | Your cPanel domain for CORS |
| `SERPAPI_KEY` | Optional — SerpAPI key for Google image search |

## API Endpoints
| Method | Route | Purpose |
|--------|-------|---------|
| GET | /health | Check if online |
| POST | /scrape/truepeoplesearch | Scrape TPS by name/location |
| POST | /extract | Structure raw text with AI |
| POST | /summarize | Generate dossier narrative |
| POST | /crossref | Cross-reference multiple records |
| POST | /search/image | Reverse image search |
| POST | /search/face | Face match comparison |
| POST | /search/mugshot | Public mugshot search |
| POST | /upload/image | Upload photo file directly |

## Notes
- Render free tier spins down after 15min inactivity — first request after sleep takes ~30 seconds
- Upgrade to Render Starter ($7/mo) to keep it always-on if needed
- TruePeopleSearch may block Render's IP — if so, use a proxy or flag for manual investigation
