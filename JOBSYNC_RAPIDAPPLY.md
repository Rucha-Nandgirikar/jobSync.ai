# JobSync + RapidApply

JobSync is a job crawling + tracking system with a Chrome extension and dashboard. RapidApply is the “apply faster” workflow: capture a job from an ATS page (Ashby/Greenhouse/Lever/Workday), generate tailored cover letters and application answers using your resume/knowledge base, and track submissions without duplicate application records.

## What you can do

- **Crawl jobs** from multiple ATS sources (Ashby, Greenhouse, Lever, Workday).
- **Add new job sources** from the dashboard or API and crawl them on demand.
- **Capture jobs + questions** from ATS pages via a Chrome Extension (Manifest V3 side panel).
- **Generate**:
  - **Cover letters** (saved as `.docx` in `data/cover_letters/<user_id>/...`)
  - **Question answers** (optionally `ignore_jd: true` to use only resume + suggestions)
- **Track applications** (dashboard + extension) without job duplication (Ashby `/application` URL canonicalization).
- **Keep the DB clean** with retention: archive unapplied jobs older than the configured threshold.
- **Export** applications daily to Excel (`data/exports/`).

## Architecture (high level)

- **Frontend**: Next.js dashboard (`frontend/`)
- **Backend**: FastAPI (`backend/app/`)
- **Database**: MySQL (Docker)
- **Cache**: Redis (Docker) for TTL caching (e.g., JD summaries / resume line selection)
- **Extension**: Chrome MV3 (`chrome-extension/`)
  - `content.js` extracts job + questions on ATS pages.
  - `background.js` proxies API calls to the backend to avoid browser CORS/PNA issues.
  - `popup.html`/`popup.js` (also embedded in the side panel) provides the RapidApply UX.

## Quick start (Docker)

### Prereqs
- Docker Desktop (Windows/Mac/Linux)
- OpenAI key (optional, only needed for generation)

### Run

1. Create an `.env` in repo root (recommended):

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.1
```

2. Start the stack:

```bash
docker compose up -d --build
```

3. Open:
- **Dashboard**: `http://localhost:3000`
- **Backend**: `http://localhost:8000`
- **MySQL**: `localhost:3307` (host) → `3306` (container)

> Note: the compose file maps MySQL to **3307** to avoid conflicts with an existing local MySQL on 3306.

## Key APIs

### Crawl
- **POST** `/api/crawl/trigger`
  - Query params:
    - `source_id` (optional) – crawl one source
    - `max_post_age_hours` (optional) – crawl-time filter when `posting_date` is available
- **GET** `/api/crawl/sources` – list job sources
- **POST** `/api/crawl/sources` – add a new job source
- **GET** `/api/crawl/status` – recent crawl runs
- **GET** `/api/crawl/stats` – crawl stats

### Dashboard
- **GET** `/api/dashboard/jobs` – supports filters like `fresh_hours` and `tag=skipped`
- **POST** `/api/dashboard/applications` – create/update an application record
- **GET** `/api/dashboard/stats` – dashboard counters
- **POST** `/api/dashboard/jobs/{job_id}/flag` – flag a job (e.g., skip/not a fit)
- **DELETE** `/api/dashboard/jobs/{job_id}/flag` – unflag

### RapidApply (generation)
- **POST** `/api/generate/cover-letter`
- **POST** `/api/generate/cover-letter-advanced`
  - Response includes `files` with `docx_path` (saved under `data/cover_letters/`)
- **POST** `/api/questions/answer`
  - Set `ignore_jd: true` to generate answers only from resume + user suggestions.

### Chrome extension capture
- **POST** `/api/extension/capture-job` – create/update job record from the active tab (URL canonicalized for Ashby).

## Data retention + exports

- Retention archives old, unapplied jobs into `jobs_archived` (configured by `JOB_RETENTION_DAYS`).
- Daily exports write application trackers to `data/exports/`.

## Repo layout

```
backend/          # FastAPI + crawlers + scheduler + migrations
frontend/         # Next.js dashboard UI
chrome-extension/ # MV3 extension (content script + background proxy + side panel UI)
data/             # Runtime data (resumes, cover letters, vector stores, exports) — ignored by git
```


