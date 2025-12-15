from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.rag.retriever import build_user_knowledge_index

router = APIRouter()


@router.post("/upload-docs")
async def upload_knowledge_docs(
    user_id: int = Form(...),
    doc_type: str = Form("kb_doc"),
    tags: Optional[str] = Form(None),  # comma-separated tags: "ai,frontend"
    files: List[UploadFile] = File(...),
):
    """Upload arbitrary knowledge documents for a user (PDF, DOCX, TXT, etc.).

    Files are stored under ./data/knowledge_base/{user_id}/ and then used
    to (re)build that user's FAISS-based knowledge index.

    You can optionally specify a doc_type and comma-separated tags
    (e.g. "ai", "frontend", "backend", "cloud", "fullstack").
    """
    try:
        kb_root = Path("./data/knowledge_base") / str(user_id)
        kb_root.mkdir(parents=True, exist_ok=True)

        for f in files:
            dest = kb_root / f.filename
            content = await f.read()
            dest.write_bytes(content)

        tag_list = (
            [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        )

        # Rebuild index after upload with metadata
        build_user_knowledge_index(user_id, doc_type=doc_type, tags=tag_list)

        return {
            "status": "success",
            "message": f"Uploaded {len(files)} files and rebuilt knowledge index for user {user_id}.",
            "doc_type": doc_type,
            "tags": tag_list or [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




