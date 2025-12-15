# JobSync.ai

JobSync.ai is a job discovery + application tracking stack:

- **Crawler**: pulls roles from ATS platforms (Ashby/Greenhouse/Lever/Workday).
- **Dashboard**: browse jobs, mark applied/submitted, export trackers.
- **RapidApply**: Chrome extension side panel to capture jobs/questions from ATS pages and generate tailored content (cover letters + answers).

## AI (LLM + RAG)

JobSync.ai includes an AI pipeline for generating cover letters and answering application questions.

- **LLM**: OpenAI chat model via LangChain `ChatOpenAI` (`OPENAI_MODEL`, default `gpt-5.1`).
- **RAG (retrieval)**:
  - **Chunking**: LangChain `RecursiveCharacterTextSplitter`.
  - **Embeddings**: `sentence-transformers` (default `all-MiniLM-L6-v2`).
  - **Vector store**: per-user **FAISS** indexes:
    - Knowledge base: `data/vector_store/user_<user_id>/`
    - Past answers: `data/vector_store_answers/user_<user_id>/`
- **Caching (optional)**: Redis TTL cache for JD summaries and JD↔resume line selection (soft-fails if Redis is unavailable).
- **JD-free answering**: `/api/questions/answer` supports `ignore_jd: true` to answer using only resume + user suggestions.
- **Cover letter files**: cover letters are saved as **DOCX** under `data/cover_letters/<user_id>/...` and the API returns the relative file path.

### Upload knowledge base documents (optional)

You can upload PDFs/DOCX/TXT as a per-user “knowledge base” and rebuild that user’s FAISS index:

- `POST /api/rag/upload-docs` (multipart form)
  - `user_id` (int)
  - `doc_type` (string, optional)
  - `tags` (comma-separated string, optional)
  - `files` (one or more files)

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
OPENAI_MODEL=gpt-5.1
REDIS_URL=redis://localhost:6379/0
```

> The local `data/` directory is used for runtime artifacts (resumes, cover letters, vector stores, logs, exports, KB docs) and is ignored by git.


