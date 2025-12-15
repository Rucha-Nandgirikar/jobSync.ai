import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document

from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate

from app.config import settings
from app.database import execute_query
from app.rag.retriever import get_user_context, get_user_answer_examples
from app.services.rag import extract_text
from app.services.cache import (
    get_cached_job_summary,
    set_cached_job_summary,
    get_cached_selected_resume_lines,
    set_cached_selected_resume_lines,
)

logger = logging.getLogger(__name__)

# Lazy‑initialized shared LLM client
_llm: Optional[ChatOpenAI] = None


def get_llm() -> ChatOpenAI:
    """Get or create a shared ChatOpenAI client.

    Uses OPENAI_API_KEY and OPENAI_MODEL from settings.
    """
    global _llm
    if _llm is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY not configured. Set it in .env file to use LLM features."
            )
        _llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model_name=settings.OPENAI_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    return _llm


def _save_cover_letter_files(
    user_id: Optional[int],
    job: Dict[str, Any],
    resume: Dict[str, Any],
    content: str,
    variant: str,
) -> Dict[str, str]:
    """Save a cover letter as .docx under COVER_LETTERS_DIR.

    Returns a dict with relative paths (from COVER_LETTERS_DIR). If user_id
    is missing or saving fails, returns an empty dict.
    """
    if not user_id:
        return {}

    try:
        base_dir = Path(settings.COVER_LETTERS_DIR)
        user_dir = base_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        job_id = job.get("id", "unknown")
        resume_id = resume.get("id", "unknown")
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        stem = f"job{job_id}_resume{resume_id}_{variant}_{ts}"

        docx_path = user_dir / f"{stem}.docx"

        # Write DOCX
        doc = Document()
        # Naively split on blank lines into paragraphs
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [content]
        for para in paragraphs:
            doc.add_paragraph(para)
        doc.save(docx_path)

        return {
            "docx_path": str(docx_path.relative_to(base_dir)),
        }
    except Exception:
        logger.exception("Failed to save cover letter files")
        return {}


async def _summarize_job_description(job_description: str) -> str:
    """Summarize a raw job description into key bullet points."""
    template = ChatPromptTemplate.from_template(
        """
You are given a job description. Summarize its most important points.

Job Description:
{job_description}

Produce a concise bullet list (at most 10 bullets) capturing:
- core responsibilities
- key technologies / skills required
- relevant domain or product context
- any strong preferences or nice-to-have experience

Use clear, short bullets.
Summary bullets:
"""
    )
    chain = LLMChain(llm=get_llm(), prompt=template)
    summary = await chain.arun(job_description=(job_description or "")[:6000])
    return summary.strip()


async def _select_relevant_resume_sentences(
    job_summary: str, resume_text: str
) -> str:
    """Ask the LLM to pick the most relevant sentences from the resume.

    The result is a text block containing selected sentences or bullets
    that best match the JD summary.
    """
    template = ChatPromptTemplate.from_template(
        """
You are helping select the most relevant parts of a candidate's resume for a job.

Job summary:
{job_summary}

Full resume text:
{resume_text}

From the resume, select the most relevant sentences or bullet points for this job.
Rules:
- Prefer items that directly match the responsibilities, technologies, and domain
  described in the job summary.
- Prefer concrete accomplishments, metrics, and outcomes.
- Include 8–25 lines max.
- Output one sentence or bullet per line. Do not rewrite the content heavily; mostly
  copy existing sentences/bullets, trimming only if necessary.

Selected resume lines:
"""
    )
    chain = LLMChain(llm=get_llm(), prompt=template)
    text = await chain.arun(job_summary=job_summary, resume_text=(resume_text or "")[:8000])
    return text.strip()


async def _select_relevant_resume_sentences_for_question(
    question: str, resume_text: str, user_suggestions: Optional[str] = None
) -> str:
    """Select the most relevant resume lines for a question (JD-free mode)."""
    template = ChatPromptTemplate.from_template(
        """
You are helping select the most relevant parts of a candidate's resume to answer a question.

Application Question:
{question}

Candidate guidance (may be empty):
{user_suggestions}

Full resume text:
{resume_text}

Select the most relevant sentences or bullet points from the resume for answering the question.
Rules:
- Prefer concrete accomplishments, metrics, and outcomes.
- Include 6–20 lines max.
- Output one sentence or bullet per line.
- Do not invent anything not present in the resume.

Selected resume lines:
"""
    )
    chain = LLMChain(llm=get_llm(), prompt=template)
    text = await chain.arun(
        question=question,
        user_suggestions=(user_suggestions or "").strip() or "None.",
        resume_text=(resume_text or "")[:8000],
    )
    return text.strip()


def _build_role_tag(role: Optional[str]) -> Optional[str]:
    if not role:
        return None
    r = role.lower()
    if any(k in r for k in ["ai", "ml", "machine learning", "genai", "data"]):
        return "ai"
    if "fullstack" in r or "full-stack" in r:
        return "fullstack"
    if any(k in r for k in ["frontend", "front-end", "react", "next.js", "ui"]):
        return "frontends"
    if any(k in r for k in ["backend", "back-end", "api", "microservice", "server"]):
        return "backend"
    if any(k in r for k in ["devops", "platform", "infra", "kubernetes", "aws", "gcp", "azure", "cloud"]):
        return "cloud"
    return None


async def generate_cover_letter(job: Dict[str, Any], resume: Dict[str, Any]) -> Dict[str, Any]:
    """Baseline cover letter generation using JD + resume summary + RAG context.

    This is the existing single‑step pipeline used by /api/generate/cover-letter.
    """
    try:
        job_title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        job_desc = (job.get("description") or "")[:6000]

        # Resume basics
        user_id = resume.get("user_id")
        resume_id = resume.get("id")
        summary_text = (resume.get("experience_summary") or "")[:1500]

        # Add a few raw resume chunks from resume_embeddings for extra project detail
        project_context = ""
        if resume_id is not None:
            chunks_query = """
            SELECT chunk_text
            FROM resume_embeddings
            WHERE resume_id = :resume_id
            ORDER BY chunk_index
            LIMIT 5
            """
            rows = execute_query(chunks_query, {"resume_id": resume_id})
            if rows:
                project_context = "\n".join(
                    (row.get("chunk_text") or "").strip()
                    for row in rows
                    if row.get("chunk_text")
                )

        # RAG context from user knowledge base (projects, deep dives, etc.)
        rag_context = ""
        if user_id is not None:
            role_tag = _build_role_tag(resume.get("role"))
            tags = [role_tag] if role_tag else None
            rag_texts = get_user_context(
                user_id=user_id,
                query=job_desc,
                top_k=5,
                required_tags=tags,
                allowed_doc_types=["kb_doc"],
            )
            if rag_texts:
                rag_context = "\n".join(f"- {t.strip()}" for t in rag_texts if t.strip())

        # Contact / header info from users table
        full_name = ""
        email = ""
        phone = ""
        if user_id is not None:
            user_rows = execute_query(
                "SELECT id, full_name, email, password_hash, created_at, updated_at, username FROM users WHERE id = :id",
                {"id": user_id},
            )
            if user_rows:
                u = user_rows[0]
                full_name = (u.get("full_name") or "").strip()
                email = (u.get("email") or "").strip()
                # phone may not exist depending on schema; ignore if missing
                phone = (u.get("phone") if "phone" in u else "") or ""

        resume_block_lines: List[str] = []
        resume_block_lines.append(f"Resume file: {resume.get('filename', 'N/A')}")
        if summary_text:
            resume_block_lines.append("Experience summary:\n" + summary_text)
        if project_context:
            resume_block_lines.append("Project & detailed experience:\n" + project_context[:2000])
        if rag_context:
            resume_block_lines.append("Additional context from knowledge base:\n" + rag_context)
        resume_block = "\n\n".join(resume_block_lines)

        template = ChatPromptTemplate.from_template(
            """
You are an expert cover letter writer. Write a professional, compelling cover letter for this job application.

Company: {company}
Job Title: {job_title}

Job Description (truncated):
{job_description}

Candidate Profile (resume + projects + extra context):
{resume_block}

Write a cover letter that strictly follows this format:

Header (use the candidate's real information; do NOT invent anything):
- First line: full name (if available).
- Second line: email address (if available).
- Third line: phone number (if available).

Body paragraphs (5 total):
1. Opening: show enthusiasm for the company and role; briefly reference why this role matches the candidate's background.
2. Key experience #1: a strong story from the resume that matches an important job requirement (focus on impact, metrics, and responsibilities).
3. Key experience #2: another complementary story or project (can be from work, internships, or significant side projects) that shows depth and breadth.
4. Skills & alignment: summarize the technical and domain skills that make the candidate a strong fit, including relevant tools, frameworks, and domains from the JD.
5. Closing: confident, appreciative close with a clear interest in next steps.

Rules:
- Do NOT invent employers, job titles, dates, or technologies that are not supported by the context.
- You may merge or lightly edit sentences from the resume text for flow, but do not fabricate.
- Keep the letter to about 3/4 to 1.5 pages of normal prose.

Now write the full cover letter with the header and 5 paragraphs:
"""
        )

        chain = LLMChain(llm=get_llm(), prompt=template)
        result_text = await chain.arun(
            company=company,
            job_title=job_title,
            job_description=job_desc,
            resume_block=resume_block,
        )
        content = result_text.strip()

        files = _save_cover_letter_files(user_id, job, resume, content, variant="basic")

        return {
            "content": content,
            "tokens_used": None,
            "model": settings.OPENAI_MODEL,
            "files_base_dir": settings.COVER_LETTERS_DIR,
            "files": files,
        }
    except Exception:
        logger.exception("Cover letter generation failed")
        raise


async def generate_cover_letter_advanced(job: Dict[str, Any], resume: Dict[str, Any]) -> Dict[str, Any]:
    """Advanced cover letter generation.

    Multi‑step flow:
    1. Summarize the JD.
    2. Extract full resume text, then have the LLM select the most relevant
       sentences/bullets for this JD.
    3. Retrieve RAG context (projects/notes) with tag‑aware filtering.
    4. Build a structured 5‑paragraph letter with contact header.
    """
    try:
        job_title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        job_desc = (job.get("description") or "")[:6000]

        user_id = resume.get("user_id")
        resume_id = resume.get("id")

        # 1) Summarize JD (with Redis cache)
        job_summary = get_cached_job_summary(job_desc)
        if not job_summary:
            job_summary = await _summarize_job_description(job_desc)
            set_cached_job_summary(job_desc, job_summary)

        # 2) Extract full resume text and select relevant sentences (with cache)
        full_resume_text = ""
        file_path = resume.get("file_path")
        if file_path:
            try:
                full_resume_text = extract_text(Path(file_path)) or ""
            except Exception:
                logger.exception("Failed to extract text from resume file: %s", file_path)
        if not full_resume_text:
            full_resume_text = resume.get("experience_summary") or ""

        selected_lines: str = ""
        if resume_id is not None:
            cached_lines = get_cached_selected_resume_lines(job_desc, resume_id)
            if cached_lines:
                selected_lines = cached_lines
        if not selected_lines:
            selected_lines = await _select_relevant_resume_sentences(job_summary, full_resume_text)
            if resume_id is not None:
                set_cached_selected_resume_lines(job_desc, resume_id, selected_lines)

        # 3) RAG context
        rag_context = ""
        if user_id is not None:
            role_tag = _build_role_tag(resume.get("role"))
            tags = [role_tag] if role_tag else None
            rag_texts = get_user_context(
                user_id=user_id,
                query=job_summary,
                top_k=8,
                required_tags=tags,
                allowed_doc_types=["kb_doc"],
            )
            if rag_texts:
                rag_context = "\n".join(f"- {t.strip()}" for t in rag_texts if t.strip())

        # 4) Contact / header info
        full_name = ""
        email = ""
        phone = ""
        if user_id is not None:
            user_rows = execute_query(
                "SELECT id, full_name, email, password_hash, created_at, updated_at, username FROM users WHERE id = :id",
                {"id": user_id},
            )
            if user_rows:
                u = user_rows[0]
                full_name = (u.get("full_name") or "").strip()
                email = (u.get("email") or "").strip()
                phone = (u.get("phone") if "phone" in u else "") or ""

        # Build a compact "selected profile" block
        profile_parts: List[str] = []
        profile_parts.append(f"Resume file: {resume.get('filename', 'N/A')}")
        if selected_lines:
            profile_parts.append("Most relevant resume lines:\n" + selected_lines)
        if rag_context:
            profile_parts.append("Additional context from knowledge base:\n" + rag_context)
        profile_block = "\n\n".join(profile_parts)

        template = ChatPromptTemplate.from_template(
            """
You are an expert career coach and cover letter writer. Create a high‑quality cover letter.

Company: {company}
Job Title: {job_title}

Original Job Description (truncated):
{job_description}

Job Summary (what this role is really about):
{job_summary}

Candidate Profile (curated from resume + extra context):
{profile_block}

Write a polished cover letter with this structure:

Header:
- Line 1: Candidate's real full name, if provided: "{full_name}" (omit the line if empty).
- Line 2: Candidate's real email, if provided: "{email}" (omit the line if empty).
- Line 3: Candidate's real phone number, if provided: "{phone}" (omit the line if empty).

Body paragraphs (exactly 5):
1. Strong opening: reference the company and role by name, show enthusiasm, and connect one or two major strengths from the profile.
2. Deep dive into a key experience or project that directly matches a core responsibility or technology in the job.
3. A second, complementary story (project or role) that demonstrates additional relevant skills or impact.
4. Focused paragraph on skills, tools, and domain knowledge (including relevant items from the JD and profile) that make the candidate a strong match.
5. Confident closing paragraph with a clear call‑to‑action and gratitude.

Rules:
- Use only information you can reasonably infer from the profile and context; do not fabricate employers, degrees, dates, or technologies.
- You may slightly rephrase selected sentences for fluency, but keep the underlying facts.
- Aim for 4–8 sentences per body paragraph.

Write the complete cover letter now, including the header and 5 paragraphs:
"""
        )

        chain = LLMChain(llm=get_llm(), prompt=template)
        result_text = await chain.arun(
            company=company,
            job_title=job_title,
            job_description=job_desc,
            job_summary=job_summary,
            profile_block=profile_block,
            full_name=full_name,
            email=email,
            phone=phone,
        )
        content = result_text.strip()

        files = _save_cover_letter_files(user_id, job, resume, content, variant="advanced")

        return {
            "content": content,
            "tokens_used": None,
            "model": settings.OPENAI_MODEL,
            "job_summary": job_summary,
            "selected_resume_sentences": selected_lines,
            "files_base_dir": settings.COVER_LETTERS_DIR,
            "files": files,
        }
    except Exception:
        logger.exception("Advanced cover letter generation failed")
        raise


async def answer_question(
    question: str,
    job_id: Optional[int],
    resume_id: int,
    user_suggestions: Optional[str] = None,
    ignore_jd: bool = False,
) -> str:
    """Answer a custom application question using JD + resume + RAG context.

    This advanced flow:
    1. Summarizes the job description to understand key expectations.
    2. Extracts the full resume text and asks the LLM to select the most
       relevant sentences/bullets for the question and job.
    3. Retrieves additional context from the user's knowledge base (RAG).
    4. Generates a concise, tailored answer that can optionally weave in
       user_provided suggestions such as “please mention project X”.
    """
    try:
        # JD-free mode: answer using ONLY resume + user suggestions.
        if ignore_jd or job_id is None:
            resume_rows = execute_query(
                "SELECT id, user_id, role, filename, file_path, experience_summary "
                "FROM resumes WHERE id = :id",
                {"id": resume_id},
            )
            if not resume_rows:
                raise ValueError("Resume not found")
            r = resume_rows[0]

            full_resume_text = ""
            file_path = r.get("file_path")
            if file_path:
                try:
                    full_resume_text = extract_text(Path(file_path)) or ""
                except Exception:
                    logger.exception("Failed to extract text from resume file: %s", file_path)
            if not full_resume_text:
                full_resume_text = r.get("experience_summary") or ""

            selected_resume_lines = await _select_relevant_resume_sentences_for_question(
                question=question,
                resume_text=full_resume_text,
                user_suggestions=user_suggestions,
            )

            suggestions_block = (user_suggestions or "").strip() or "None provided."

            template = ChatPromptTemplate.from_template(
                """
You are helping a software engineer answer a job application question.

Important: Do NOT use or infer anything from the job description. Use ONLY:
- the selected resume lines
- the candidate's guidance (if any)

Application Question:
{question}

Selected resume lines:
{selected_resume_lines}

Candidate guidance:
{user_suggestions}

Write a concise, professional answer (2–4 sentences) that:
- Directly answers the question.
- Uses only facts supported by the selected resume lines and guidance.
- Includes specific impact/metrics when available.

Answer:
"""
            )
            chain = LLMChain(llm=get_llm(), prompt=template)
            answer = await chain.arun(
                question=question,
                selected_resume_lines=selected_resume_lines or "None found.",
                user_suggestions=suggestions_block,
            )
            return answer.strip()

        # 1) Fetch job context and summarize JD
        job_rows = execute_query(
            "SELECT title, company, description FROM jobs WHERE id = :id",
            {"id": job_id},
        )
        if not job_rows:
            raise ValueError("Job not found")
        job = job_rows[0]
        job_title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        job_desc = (job.get("description") or "")[:4000]

        # JD summary with cache
        job_summary = get_cached_job_summary(job_desc)
        if not job_summary:
            job_summary = await _summarize_job_description(job_desc)
            set_cached_job_summary(job_desc, job_summary)

        # 2) Fetch resume and select relevant sentences
        resume_rows = execute_query(
            "SELECT id, user_id, role, filename, file_path, experience_summary "
            "FROM resumes WHERE id = :id",
            {"id": resume_id},
        )
        if not resume_rows:
            raise ValueError("Resume not found")
        r = resume_rows[0]
        user_id = r.get("user_id")

        full_resume_text = ""
        file_path = r.get("file_path")
        if file_path:
            try:
                full_resume_text = extract_text(Path(file_path)) or ""
            except Exception:
                logger.exception("Failed to extract text from resume file: %s", file_path)
        if not full_resume_text:
            full_resume_text = r.get("experience_summary") or ""

        selected_resume_lines: str = ""
        cached_resume_lines = get_cached_selected_resume_lines(job_desc, resume_id)
        if cached_resume_lines:
            selected_resume_lines = cached_resume_lines
        else:
            selected_resume_lines = await _select_relevant_resume_sentences(
                job_summary, full_resume_text
            )
            set_cached_selected_resume_lines(job_desc, resume_id, selected_resume_lines)

        # 3) RAG context from knowledge base
        rag_context = ""
        if user_id is not None:
            role_tag = _build_role_tag(r.get("role"))
            tags = [role_tag] if role_tag else None
            try:
                rag_texts = get_user_context(
                    user_id=user_id,
                    query=f"{job_title} at {company}\n\n{job_summary}\n\nQuestion: {question}",
                    top_k=5,
                    required_tags=tags,
                    allowed_doc_types=["kb_doc"],
                )
                if rag_texts:
                    rag_context = "\n".join(
                        f"- {t.strip()}" for t in rag_texts if t.strip()
                    )
            except Exception:
                logger.exception("RAG context retrieval failed for answer_question")

        # 4) Retrieve similar past answers from the dedicated answer FAISS index
        previous_answers_block = ""
        if user_id is not None:
            try:
                examples = get_user_answer_examples(
                    user_id=user_id,
                    query=f"{job_title} at {company}\n\n{job_summary}\n\nQuestion: {question}",
                    top_k=3,
                )
                if examples:
                    lines: List[str] = []
                    for ex in examples:
                        prev_q = (ex.get("question") or "").strip()
                        prev_a = (ex.get("answer") or ex.get("text") or "").strip()
                        if not prev_a:
                            continue
                        # Keep things reasonably short for the prompt.
                        if len(prev_a) > 800:
                            prev_a = prev_a[:800] + "..."
                        if len(prev_q) > 400:
                            prev_q = prev_q[:400] + "..."
                        header = f"Q: {prev_q}\n" if prev_q else ""
                        lines.append(f"{header}A: {prev_a}")
                    if lines:
                        previous_answers_block = "\n\n".join(lines)
            except Exception:
                logger.exception("Previous answer example retrieval failed")

        suggestions_block = (user_suggestions or "").strip() or "None provided."

        # 5) Final answer generation
        template = ChatPromptTemplate.from_template(
            """
You are helping a software engineer answer a job application question.

Job: {job_title} at {company}

Job summary (what this role is about):
{job_summary}

Application Question:
{question}

Most relevant lines from the candidate's resume:
{selected_resume_lines}

Additional context from the candidate's projects and achievements:
{rag_context}

Additional guidance from the candidate (may be empty):
{user_suggestions}

Examples of previous answers by this same candidate to related questions
(reuse structure and ideas where appropriate, but do NOT copy sentences
verbatim; always adapt to the current JD and question):
{previous_answers}

Write a concise, professional answer (2–4 sentences) that:
- Directly answers the question.
- Draws on the most relevant experiences and skills from the selected resume lines
  and, where appropriate, the additional context.
- Incorporates the candidate's guidance when it is truthful and helpful
  (for example, mentioning a specific project), but never invents details
  not supported by the resume or context.
- Uses clear, specific language and avoids generic claims.

Answer:
"""
        )

        chain = LLMChain(llm=get_llm(), prompt=template)
        answer = await chain.arun(
            job_title=job_title,
            company=company,
            job_summary=job_summary,
            question=question,
            selected_resume_lines=selected_resume_lines or "None found.",
            rag_context=rag_context or "None found.",
            user_suggestions=suggestions_block,
            previous_answers=previous_answers_block or "None available.",
        )
        return answer.strip()
    except Exception:
        logger.exception("Question answering failed")
        raise
