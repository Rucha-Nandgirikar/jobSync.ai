import os
import pickle
from typing import List, Any, Dict, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.rag.embedding import EmbeddingPipeline


class FaissVectorStore:
    """Simple FAISS-based vector store with metadata.

    For now this is per-user, using a separate index directory per user.
    """

    def __init__(
        self,
        persist_dir: str,
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)

        self.index: Optional[faiss.IndexFlatL2] = None
        self.metadata: List[Dict[str, Any]] = []

        self.embedding_model = embedding_model
        self.model = SentenceTransformer(embedding_model)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        print(f"[RAG] Loaded embedding model for store: {embedding_model}")

    # ---------- Build / Update ----------

    def build_from_documents(self, documents: List[Any], base_metadata: Dict[str, Any]) -> None:
        """(Re)build the store from raw LangChain documents.

        base_metadata is merged into each chunk's metadata (e.g. user_id, doc_id).
        """
        print(f"[RAG] Building vector store from {len(documents)} raw documents...")

        emb_pipe = EmbeddingPipeline(
            model_name=self.embedding_model,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        chunks = emb_pipe.chunk_documents(documents)
        embeddings = emb_pipe.embed_chunks(chunks)

        metadatas: List[Dict[str, Any]] = []
        for chunk in chunks:
            meta = dict(base_metadata)
            meta["text"] = chunk.page_content
            metadatas.append(meta)

        self._reset_index()
        self.add_embeddings(np.array(embeddings).astype("float32"), metadatas)
        self.save()
        print(f"[RAG] Vector store built and saved to {self.persist_dir}")

    def _reset_index(self) -> None:
        self.index = None
        self.metadata = []

    def add_embeddings(self, embeddings: np.ndarray, metadatas: List[Dict[str, Any]]) -> None:
        dim = embeddings.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings)
        self.metadata.extend(metadatas)
        print(f"[RAG] Added {embeddings.shape[0]} vectors to Faiss index.")

    # ---------- Persistence ----------

    def _paths(self) -> tuple[str, str]:
        faiss_path = os.path.join(self.persist_dir, "faiss.index")
        meta_path = os.path.join(self.persist_dir, "metadata.pkl")
        return faiss_path, meta_path

    def save(self) -> None:
        if self.index is None:
            return
        faiss_path, meta_path = self._paths()
        faiss.write_index(self.index, faiss_path)
        with open(meta_path, "wb") as f:
            pickle.dump(self.metadata, f)
        print(f"[RAG] Saved Faiss index and metadata to {self.persist_dir}")

    def load(self) -> None:
        faiss_path, meta_path = self._paths()
        if not (os.path.exists(faiss_path) and os.path.exists(meta_path)):
            print(f"[RAG] No existing FAISS index found at {self.persist_dir}")
            return
        self.index = faiss.read_index(faiss_path)
        with open(meta_path, "rb") as f:
            self.metadata = pickle.load(f)
        print(f"[RAG] Loaded Faiss index and metadata from {self.persist_dir}")

    # ---------- Query ----------

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None:
            return []
        D, I = self.index.search(query_embedding, top_k)
        results: List[Dict[str, Any]] = []
        for idx, dist in zip(I[0], D[0]):
            meta = self.metadata[idx] if idx < len(self.metadata) else None
            results.append({"index": int(idx), "distance": float(dist), "metadata": meta})
        return results

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        print(f"[RAG] Querying vector store for: '{query_text}'")
        query_emb = self.model.encode([query_text]).astype("float32")
        return self.search(query_emb, top_k=top_k)




