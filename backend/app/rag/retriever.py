from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.document_loader import load_all_documents
from app.rag.vector_store import FaissVectorStore


def _user_store_dir(user_id: int) -> str:
    """Directory for a user's FAISS index (knowledge base)."""
    base = Path("./data/vector_store").resolve()
    return str(base / f"user_{user_id}")


def _user_answer_store_dir(user_id: int) -> str:
    """Directory for a user's FAISS index dedicated to past answers."""
    base = Path("./data/vector_store_answers").resolve()
    return str(base / f"user_{user_id}")


def build_user_knowledge_index(
    user_id: int,
    doc_type: str = "kb_doc",
    tags: Optional[List[str]] = None,
) -> None:
    """(Re)build the FAISS index for a user's knowledge base documents.

    All documents in ./data/knowledge_base/{user_id} are loaded and indexed
    with the given doc_type and tags metadata.
    """
    kb_root = Path("./data/knowledge_base") / str(user_id)
    kb_root.mkdir(parents=True, exist_ok=True)

    docs = load_all_documents(str(kb_root))
    if not docs:
        print(f"[RAG] No documents found for user {user_id} in {kb_root}")
        return

    base_metadata = {
        "user_id": user_id,
        "doc_type": doc_type,
        "tags": tags or [],
    }

    store = FaissVectorStore(persist_dir=_user_store_dir(user_id))
    store.build_from_documents(docs, base_metadata=base_metadata)


def get_user_context(
    user_id: int,
    query: str,
    top_k: int = 5,
    required_tags: Optional[List[str]] = None,
    allowed_doc_types: Optional[List[str]] = None,
) -> List[str]:
    """Return top-k relevant text snippets from the user's knowledge base.

    You can optionally filter by tags and doc_type metadata. Tags are
    matched by intersection: at least one required tag must be present
    in the chunk's metadata.
    """
    store = FaissVectorStore(persist_dir=_user_store_dir(user_id))
    store.load()

    # Over-retrieve then filter to get better results when using metadata
    raw_results = store.query(query, top_k=top_k * 5)

    texts: List[str] = []
    required_tags_set = set(required_tags or [])
    allowed_types_set = set(allowed_doc_types or [])

    for r in raw_results:
        meta = r.get("metadata") or {}
        tags = set(meta.get("tags") or [])
        doc_type = meta.get("doc_type")

        if required_tags_set and not tags.intersection(required_tags_set):
            continue
        if allowed_types_set and doc_type not in allowed_types_set:
            continue

        text = meta.get("text")
        if not text:
            continue

        texts.append(text)
        if len(texts) >= top_k:
            break

    return texts


def add_answer_texts_to_index(
    user_id: int,
    texts: List[str],
    base_metadata: Dict[str, Any],
) -> None:
    """Add one or more answer texts to the user's dedicated answer FAISS index.

    Each text is stored as a single vector with metadata including snippet_id,
    question, answer, application/job ids, etc.
    """
    if not texts:
        return

    store = FaissVectorStore(persist_dir=_user_answer_store_dir(user_id))
    store.load()

    # Embed full texts (answers) directly; answers are typically short.
    embeddings = store.model.encode(texts).astype("float32")

    metadatas: List[Dict[str, Any]] = []
    for text in texts:
        meta = dict(base_metadata)
        # Keep the combined text for retrieval; individual question/answer
        # fields should also be present in base_metadata if needed.
        meta["text"] = text
        metadatas.append(meta)

    store.add_embeddings(embeddings, metadatas)
    store.save()


def get_user_answer_examples(
    user_id: int,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Retrieve top-k previously given answers for use as examples.

    Returns the stored metadata for each match (question, answer, etc.),
    which can be formatted into the LLM prompt.
    """
    store = FaissVectorStore(persist_dir=_user_answer_store_dir(user_id))
    store.load()

    raw_results = store.query(query, top_k=top_k * 5)
    examples: List[Dict[str, Any]] = []

    for r in raw_results:
        meta = r.get("metadata") or {}
        text = meta.get("text")
        if not text:
            continue

        examples.append(meta)
        if len(examples) >= top_k:
            break

    return examples
