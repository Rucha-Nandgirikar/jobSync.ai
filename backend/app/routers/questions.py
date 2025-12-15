from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from typing import List, Optional

from app.services.llm import answer_question
from app.services.rag import store_generated_answer_embedding

router = APIRouter()
logger = logging.getLogger(__name__)


class QuestionAnswerRequest(BaseModel):
    application_id: int
    questions: List[str]
    resume_id: int
    job_id: Optional[int] = None
    user_suggestions: Optional[str] = None
    ignore_jd: bool = False


@router.post("/answer")
async def answer_questions(request: QuestionAnswerRequest):
    """Answer one or more application questions using job + resume context.

    You can optionally pass a `user_suggestions` string (e.g. \"also mention my
    work on the XYZ project\"), which will be provided to the LLM and stored
    with each generated answer.
    """
    try:
        from app.database import execute_query, execute_insert

        # Resolve the user owning this resume once so we can link embeddings.
        resume_rows = execute_query(
            "SELECT user_id, role FROM resumes WHERE id = :id",
            {"id": request.resume_id},
        )
        if not resume_rows:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_meta = resume_rows[0]
        user_id = resume_meta["user_id"]
        role = resume_meta.get("role")

        answers = []
        for question in request.questions:
            # Answer the question with optional user guidance
            answer_text = await answer_question(
                question=question,
                job_id=request.job_id,
                resume_id=request.resume_id,
                user_suggestions=request.user_suggestions,
                ignore_jd=request.ignore_jd,
            )

            # Store answer in database, including the suggestions for traceability
            insert_query = """
            INSERT INTO application_answers 
            (application_id, question, answer, user_suggestions, generated_at)
            VALUES (:app_id, :question, :answer, :user_suggestions, NOW())
            """
            answer_id = execute_insert(
                insert_query,
                {
                    "app_id": request.application_id,
                    "question": question,
                    "answer": answer_text,
                    "user_suggestions": request.user_suggestions,
                },
            )

            # Also push this answer into the per-user answer embeddings + FAISS index.
            try:
                await store_generated_answer_embedding(
                    user_id=user_id,
                    question=question,
                    answer_text=answer_text,
                    job_id=request.job_id,
                    application_id=request.application_id,
                    role=role,
                    answer_id=answer_id,
                )
            except Exception as embed_err:  # pragma: no cover - defensive
                logger.error("Failed to store generated answer embedding: %s", embed_err)

            answers.append(
                {
                    "question": question,
                    "answer": answer_text,
                    "user_suggestions": request.user_suggestions,
                }
            )

        return {
            "status": "success",
            "data": {
                "application_id": request.application_id,
                "answers": answers,
            },
        }
    except Exception as e:
        logger.error(f"Question answering error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/answers/{application_id}")
async def get_answers(application_id: int):
    """Get all answers for an application"""
    try:
        from app.database import execute_query
        
        query = """
        SELECT question, answer, generated_at
        FROM application_answers
        WHERE application_id = :app_id
        ORDER BY generated_at ASC
        """
        
        results = execute_query(query, {"app_id": application_id})
        
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        logger.error(f"Get answers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/answers/{answer_id}")
async def delete_answer(answer_id: int):
    """Delete an answer"""
    try:
        from app.database import execute_delete
        
        query = "DELETE FROM application_answers WHERE id = :answer_id"
        rows = execute_delete(query, {"answer_id": answer_id})
        
        if rows == 0:
            raise HTTPException(status_code=404, detail="Answer not found")
        
        return {
            "status": "success",
            "message": "Answer deleted"
        }
    except Exception as e:
        logger.error(f"Delete answer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


