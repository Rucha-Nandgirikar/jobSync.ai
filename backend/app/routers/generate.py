from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import logging
from typing import Optional

from app.services.llm import generate_cover_letter, generate_cover_letter_advanced
from app.services.rag import store_resume, search_similar_resumes

router = APIRouter()
logger = logging.getLogger(__name__)


class CoverLetterRequest(BaseModel):
    job_id: int
    resume_id: int
    # Legacy/mvp: some clients didn't send this; we don't actually need it here.
    user_id: Optional[int] = None


class ResumeUploadRequest(BaseModel):
    user_id: int
    role: str


@router.post("/cover-letter")
async def generate_cover_letter_endpoint(request: CoverLetterRequest):
    """Generate a cover letter for a job using a resume (single-step RAG pipeline)."""
    try:
        from app.database import execute_query

        # Get job details
        job_query = "SELECT * FROM jobs WHERE id = :job_id"
        job = execute_query(job_query, {"job_id": request.job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get resume details
        resume_query = "SELECT * FROM resumes WHERE id = :resume_id"
        resume = execute_query(resume_query, {"resume_id": request.resume_id})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Generate cover letter
        cover_letter = await generate_cover_letter(job[0], resume[0])

        return {
            "status": "success",
            "data": {
                "cover_letter": cover_letter["content"],
                "tokens_used": cover_letter.get("tokens_used"),
                "model": cover_letter.get("model"),
                "files": cover_letter.get("files") or {},
                "files_base_dir": cover_letter.get("files_base_dir") or None,
            },
        }
    except Exception as e:
        logger.error(f"Cover letter generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cover-letter-advanced")
async def generate_cover_letter_advanced_endpoint(request: CoverLetterRequest):
    """Generate an advanced cover letter using JD summary, resume selection, and RAG."""
    try:
        from app.database import execute_query

        # Get job details
        job_query = "SELECT * FROM jobs WHERE id = :job_id"
        job = execute_query(job_query, {"job_id": request.job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get resume details
        resume_query = "SELECT * FROM resumes WHERE id = :resume_id"
        resume = execute_query(resume_query, {"resume_id": request.resume_id})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Generate advanced cover letter
        result = await generate_cover_letter_advanced(job[0], resume[0])

        return {
            "status": "success",
            "data": {
                "cover_letter": result["content"],
                "tokens_used": result.get("tokens_used"),
                "model": result.get("model"),
                "job_summary": result.get("job_summary"),
                "selected_resume_sentences": result.get("selected_resume_sentences"),
                "files": result.get("files") or {},
                "files_base_dir": result.get("files_base_dir") or None,
            },
        }
    except Exception as e:
        logger.error(f"Advanced cover letter generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resumes/upload")
async def upload_resume(
    user_id: int = Form(...),
    role: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload a resume and store embeddings"""
    try:
        content = await file.read()
        
        # Store resume
        resume_id = await store_resume(
            user_id=user_id,
            filename=file.filename,
            role=role,
            content=content
        )
        
        return {
            "status": "success",
            "data": {
                "resume_id": resume_id,
                "filename": file.filename,
                "role": role
            }
        }
    except Exception as e:
        logger.error(f"Resume upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resumes/search")
async def search_resumes(user_id: int, query: str):
    """Search for similar resumes using semantic search"""
    try:
        results = await search_similar_resumes(user_id, query)
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        logger.error(f"Resume search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resumes")
async def list_resumes(user_id: int):
    """List all resumes for a user"""
    try:
        from app.database import execute_query
        
        query = "SELECT id, filename, role, created_at FROM resumes WHERE user_id = :user_id"
        results = execute_query(query, {"user_id": user_id})
        
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        logger.error(f"List resumes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


