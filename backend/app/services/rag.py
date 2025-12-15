import logging
from typing import List, Dict, Any
from pathlib import Path
import PyPDF2

from app.config import settings

logger = logging.getLogger(__name__)


async def store_resume(user_id: int, filename: str, role: str, content: bytes) -> int:
    """Store resume file and create embeddings for RAG"""
    try:
        from app.database import execute_insert

        # Create resumes directory if not exists
        resumes_dir = Path(settings.RESUMES_DIR) / str(user_id)
        resumes_dir.mkdir(parents=True, exist_ok=True)

        # Save resume file
        file_path = resumes_dir / filename
        file_path.write_bytes(content)

        # Extract text from PDF/TXT
        resume_text = extract_text(file_path)

        # Store metadata
        insert_query = """
        INSERT INTO resumes 
        (user_id, filename, role, file_path, experience_summary)
        VALUES (:user_id, :filename, :role, :file_path, :summary)
        """

        resume_id = execute_insert(
            insert_query,
            {
                "user_id": user_id,
                "filename": filename,
                "role": role,
                "file_path": str(file_path),
                "summary": resume_text[:500],  # Store first 500 chars as summary
            },
        )

        # Create embeddings (placeholder - integrate with Chroma/FAISS)
        await create_embeddings(resume_id, resume_text)

        return resume_id

    except Exception as e:
        logger.error(f"Resume storage error: {e}")
        raise


def extract_text(file_path: Path) -> str:
    """Extract text from PDF or TXT file"""
    try:
        if file_path.suffix.lower() == ".pdf":
            text = ""
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            return text
        else:
            # Assume text file
            return file_path.read_text(encoding="utf-8", errors="ignore")

    except Exception as e:
        logger.warning(f"Text extraction error: {e}")
        return ""


async def create_embeddings(resume_id: int, text: str) -> None:
    """Create and store embeddings for semantic search (resume chunks)"""
    try:
        from app.database import execute_insert

        # Placeholder: Integrate with Chroma or FAISS
        # For now, just store the raw text chunks

        # Split text into chunks (500 chars)
        chunk_size = 500
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

        for idx, chunk in enumerate(chunks):
            if chunk.strip():
                insert_query = """
                INSERT INTO resume_embeddings 
                (resume_id, chunk_index, chunk_text, embedding_vector)
                VALUES (:resume_id, :chunk_index, :chunk_text, NULL)
                """

                execute_insert(
                    insert_query,
                    {
                        "resume_id": resume_id,
                        "chunk_index": idx,
                        "chunk_text": chunk,
                    },
                )

    except Exception as e:
        logger.error(f"Embedding creation error: {e}")


async def search_similar_resumes(user_id: int, query: str) -> List[Dict[str, Any]]:
    """Search for similar resumes using simple text search over stored chunks.

    NOTE: This is an MVP implementation that uses LIKE over resume_embeddings.chunk_text.
    It returns basic resume metadata; use get_resume_context_for_question for full text.
    """
    try:
        from app.database import execute_query

        # Placeholder: Implement vector similarity search with Chroma/FAISS
        # For MVP, use simple text search

        search_query = """
        SELECT DISTINCT r.id, r.filename, r.role
        FROM resumes r
        JOIN resume_embeddings re ON r.id = re.resume_id
        WHERE r.user_id = :user_id
          AND (r.filename LIKE CONCAT('%', :query, '%')
               OR re.chunk_text LIKE CONCAT('%', :query, '%'))
        LIMIT 5
        """

        results = execute_query(
            search_query,
            {
                "user_id": user_id,
                "query": query,
            },
        )

        return results

    except Exception as e:
        logger.error(f"Resume search error: {e}")
        return []


async def get_resume_context_for_question(
    user_id: int, question: str, max_chunks: int = 5
) -> List[Dict[str, Any]]:
    """Return concrete resume chunks relevant to a given question."""
    try:
        from app.database import execute_query

        query = """
        SELECT 
            re.chunk_text,
            r.role,
            r.filename
        FROM resume_embeddings re
        JOIN resumes r ON re.resume_id = r.id
        WHERE r.user_id = :user_id
          AND re.chunk_text LIKE CONCAT('%', :query, '%')
        LIMIT  :limit
        """

        # Some DB drivers don't support named params for LIMIT; fall back to literal if needed.
        # To stay safe, we inline the LIMIT value here.
        query = query.replace(":limit", str(max_chunks))

        results = execute_query(
            query,
            {
                "user_id": user_id,
                "query": question[:200],  # basic truncation
            },
        )

        return results
    except Exception as e:
        logger.error(f"Resume context search error: {e}")
        return []


async def store_answer_snippet(
    user_id: int,
    answer_text: str,
    title: str | None = None,
    category: str | None = None,
    original_question: str | None = None,
    source_type: str = "manual",
    liked_score: int | None = None,
) -> int:
    """Store a curated 'golden' answer snippet and create text chunks for RAG."""
    try:
        from app.database import execute_insert

        insert_query = """
        INSERT INTO answer_snippets 
        (user_id, title, category, source_type, original_question, answer_text, liked_score)
        VALUES (:user_id, :title, :category, :source_type, :original_question, :answer_text, :liked_score)
        """

        snippet_id = execute_insert(
            insert_query,
            {
                "user_id": user_id,
                "title": title,
                "category": category,
                "source_type": source_type,
                "original_question": original_question,
                "answer_text": answer_text,
                "liked_score": liked_score,
            },
        )

        # Also index this curated snippet into the per-user FAISS answer store.
        await create_answer_embeddings(
            snippet_id=snippet_id,
            text=answer_text,
            user_id=user_id,
            question=original_question,
            job_id=None,
            application_id=None,
            role=None,
            source_type=source_type,
        )
        return snippet_id
    except Exception as e:
        logger.error(f"Answer snippet storage error: {e}")
        raise


async def create_answer_embeddings(
    snippet_id: int,
    text: str,
    user_id: int | None = None,
    question: str | None = None,
    job_id: int | None = None,
    application_id: int | None = None,
    role: str | None = None,
    source_type: str | None = None,
) -> None:
    """Create and store text chunks for answer snippets and index them in FAISS.

    The MySQL `answer_embeddings` table stores chunked text as a durable log.
    A separate per-user FAISS index (managed by app.rag.retriever) stores
    dense embeddings for fast similarity search over past answers.
    """
    try:
        from app.database import execute_insert
        from app.rag.retriever import add_answer_texts_to_index

        # Store raw chunks for this snippet in SQL
        chunk_size = 500
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

        for idx, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            insert_query = """
            INSERT INTO answer_embeddings 
            (snippet_id, chunk_index, chunk_text, embedding_vector)
            VALUES (:snippet_id, :chunk_index, :chunk_text, NULL)
            """

            execute_insert(
                insert_query,
                {
                    "snippet_id": snippet_id,
                    "chunk_index": idx,
                    "chunk_text": chunk,
                },
            )

        # Also push a single vector representing the full answer into FAISS,
        # if we know which user this belongs to.
        if user_id is not None:
            combined_text = (
                f"Question: {question}\nAnswer: {text}" if question else text
            )
            base_metadata: Dict[str, Any] = {
                "user_id": user_id,
                "snippet_id": snippet_id,
                "job_id": job_id,
                "application_id": application_id,
                "question": question,
                "answer": text,
                "role": role,
                "source_type": source_type or "snippet",
                # Placeholders for future quality/usage scoring
                "quality_score": 0.0,
                "usage_count": 0,
            }
            add_answer_texts_to_index(
                user_id=user_id,
                texts=[combined_text],
                base_metadata=base_metadata,
            )
    except Exception as e:
        logger.error(f"Answer embedding creation error: {e}")


async def store_generated_answer_embedding(
    user_id: int,
    question: str,
    answer_text: str,
    job_id: int | None = None,
    application_id: int | None = None,
    role: str | None = None,
    answer_id: int | None = None,
) -> int:
    """Store an automatically generated application answer for later reuse.

    This creates a row in `answer_snippets` with source_type='generated',
    creates chunk rows in `answer_embeddings`, and indexes the full answer
    into the user's FAISS answer index.
    """
    try:
        from app.database import execute_insert

        title = (question or "").strip()
        if title:
            title = title[:255]
        else:
            title = None

        category = f"job_{job_id}" if job_id is not None else None

        insert_query = """
        INSERT INTO answer_snippets 
        (user_id, title, category, source_type, original_question, answer_text, liked_score)
        VALUES (:user_id, :title, :category, :source_type, :original_question, :answer_text, NULL)
        """

        snippet_id = execute_insert(
            insert_query,
            {
                "user_id": user_id,
                "title": title,
                "category": category,
                "source_type": "generated",
                "original_question": question,
                "answer_text": answer_text,
            },
        )

        await create_answer_embeddings(
            snippet_id=snippet_id,
            text=answer_text,
            user_id=user_id,
            question=question,
            job_id=job_id,
            application_id=application_id,
            role=role,
            source_type="generated",
        )

        return snippet_id
    except Exception as e:
        logger.error(f"Generated answer embedding storage error: {e}")
        raise


async def search_similar_answer_snippets(
    user_id: int, query: str, max_results: int = 5
) -> List[Dict[str, Any]]:
    """Search for relevant golden answers using simple text search."""
    try:
        from app.database import execute_query

        sql = """
        SELECT DISTINCT 
            s.id,
            s.title,
            s.category,
            s.original_question,
            s.answer_text,
            s.liked_score
        FROM answer_snippets s
        LEFT JOIN answer_embeddings e ON s.id = e.snippet_id
        WHERE s.user_id = :user_id
          AND (
            s.original_question LIKE CONCAT('%', :query, '%')
            OR s.answer_text       LIKE CONCAT('%', :query, '%')
            OR (e.chunk_text IS NOT NULL AND e.chunk_text LIKE CONCAT('%', :query, '%'))
          )
        ORDER BY COALESCE(s.liked_score, 0) DESC, s.created_at DESC
        LIMIT :limit
        """

        # Inline limit similarly to resume context search
        sql = sql.replace(":limit", str(max_results))

        rows = execute_query(
            sql,
            {
                "user_id": user_id,
                "query": query[:200],
            },
        )

        return rows
    except Exception as e:
        logger.error(f"Answer snippet search error: {e}")
        return []


async def build_combined_rag_context(
    user_id: int, question: str, max_resume_chunks: int = 5, max_snippets: int = 5
) -> Dict[str, Any]:
    """Fetch both resume chunks and golden answers for a question."""
    resume_chunks = await get_resume_context_for_question(
        user_id, question, max_chunks=max_resume_chunks
    )
    answer_snippets = await search_similar_answer_snippets(
        user_id, question, max_results=max_snippets
    )

    def _format_resume_chunks() -> str:
        if not resume_chunks:
            return ""
        lines = []
        for c in resume_chunks:
            role = c.get("role") or ""
            fn = c.get("filename") or ""
            prefix = f"[{role} - {fn}] " if role or fn else ""
            lines.append(f"- {prefix}{c.get('chunk_text', '').strip()}")
        return "\n".join(lines)

    def _format_answer_snippets() -> str:
        if not answer_snippets:
            return ""
        lines = []
        for s in answer_snippets:
            title = s.get("title") or s.get("category") or ""
            header = f"[{title}] " if title else ""
            lines.append(f"- {header}{(s.get('answer_text') or '').strip()}")
        return "\n".join(lines)

    return {
        "resume_context": _format_resume_chunks(),
        "answer_snippet_context": _format_answer_snippets(),
    }

