from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import logging
from typing import Optional, List
from pathlib import Path

from app.config import settings
from app.services.rag import (
    store_answer_snippet,
    search_similar_answer_snippets,
    extract_text,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class AnswerSnippetCreate(BaseModel):
    user_id: int
    answer_text: str
    title: Optional[str] = None
    category: Optional[str] = None
    original_question: Optional[str] = None
    source_type: str = "manual"
    liked_score: Optional[int] = None


@router.post("/answers")
async def create_answer_snippet(payload: AnswerSnippetCreate):
    """Store a curated golden answer snippet for later RAG retrieval."""
    try:
        snippet_id = await store_answer_snippet(
            user_id=payload.user_id,
            answer_text=payload.answer_text,
            title=payload.title,
            category=payload.category,
            original_question=payload.original_question,
            source_type=payload.source_type,
            liked_score=payload.liked_score,
        )
        return {
            "status": "success",
            "data": {"snippet_id": snippet_id},
        }
    except Exception as e:
        logger.error(f"Create answer snippet error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/answers/upload-docs")
async def upload_answer_documents(
    user_id: int = Form(...),
    files: List[UploadFile] = File(...),
):
    """Upload one or more documents containing your own answers.

    For each uploaded file we:
    - Save it under ./data/answer_uploads/{user_id}/
    - Extract plain text using the shared extract_text helper
    - Create an answer_snippets row with source_type='imported'
    - Create answer_embeddings rows and index the full text into the
      per-user FAISS answer store for reuse when answering future questions.
    """
    try:
        base_dir = Path("./data/answer_uploads") / str(user_id)
        base_dir.mkdir(parents=True, exist_ok=True)

        created_snippets: List[int] = []

        for f in files:
            contents = await f.read()
            if not contents:
                continue

            dest_path = base_dir / f.filename
            dest_path.write_bytes(contents)

            text = extract_text(dest_path)
            if not text or not text.strip():
                continue

            snippet_id = await store_answer_snippet(
                user_id=user_id,
                answer_text=text,
                title=f.filename,
                category="uploaded_doc",
                original_question=None,
                source_type="imported",
                liked_score=None,
            )
            created_snippets.append(snippet_id)

        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "uploaded_files": [f.filename for f in files],
                "created_snippet_ids": created_snippets,
            },
        }
    except Exception as e:
        logger.error(f"Upload answer documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/answers/search")
async def search_answer_snippets(user_id: int, query: str):
    """Search stored answer snippets for debugging/inspection."""
    try:
        results = await search_similar_answer_snippets(user_id=user_id, query=query)
        return {
            "status": "success",
            "data": results,
        }
    except Exception as e:
        logger.error(f"Search answer snippets error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

