# JobSync.ai

JobSync.ai is a job discovery + application tracking stack:

- **Crawler**: pulls roles from ATS platforms (Ashby/Greenhouse/Lever/Workday).
- **Dashboard**: browse jobs, mark applied/submitted, export trackers.
- **RapidApply**: Chrome extension side panel to capture jobs/questions from ATS pages and generate tailored content (cover letters + answers).

## Documentation

- **Project overview (JobSync + RapidApply)**: `JOBSYNC_RAPIDAPPLY.md`
- **Chrome extension notes**: `chrome-extension/README.md`

## Run locally (Docker)

```bash
docker compose up -d --build
```

- Dashboard: `http://localhost:3000`
- Backend: `http://localhost:8000`
- MySQL: `localhost:3307` (host) → `3306` (container)

## Configuration

Create an `.env` in repo root:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=model_name
```

> Generated files (resumes/cover letters/vector stores/logs/exports) live under `data/` and are ignored by git.


