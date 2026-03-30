"""
vectorstore/faiss_store.py
---------------------------
FAISS vector store implementation for the RAG Course Planning Assistant.

WHY FAISS:
  - Free, open-source, no server required
  - Extremely fast similarity search (tested to ~1M vectors on CPU)
  - Flat L2 / Inner Product indices appropriate for our scale (~200-500 chunks)
  - Easy to persist to disk and reload
  - Battle-tested at Meta for billion-scale production retrieval

INDEX TYPE: IndexFlatIP (Inner Product / Cosine similarity)
  - For normalized vectors, inner product = cosine similarity
  - Exact nearest neighbors (no approximation needed at our scale)
  - For > 100K chunks, would switch to IndexIVFFlat with clustering
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, asdict
from loguru import logger

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.error("FAISS not available. Install with: pip install faiss-cpu")


@dataclass
class SearchResult:
    """A single retrieval result with citation metadata."""
    chunk_id: str
    text: str
    score: float          # Cosine similarity (0-1, higher = more relevant)
    source_url: str
    source_title: str
    doc_type: str
    metadata: Dict[str, Any]

    def citation(self) -> str:
        return f"[{self.source_title}] URL: {self.source_url} | Chunk: {self.chunk_id}"

    def short_citation(self) -> str:
        return f"[{self.doc_type.upper()}] {self.chunk_id} ({self.source_url})"


class FAISSVectorStore:
    """
    FAISS-backed vector store with chunk metadata storage.

    Architecture:
      - FAISS index: stores only the float32 vectors
      - chunk_store: Python list of chunk metadata dicts (parallel to FAISS index)
      - Persisted as: index.faiss + chunks.pkl

    Retrieval:
      - top_k=5 by default (assessment requirement)
      - Uses inner product (= cosine similarity on normalized vectors)
    """

    def __init__(self, index_dir: str = "vectorstore", top_k: int = 5):
        if not FAISS_AVAILABLE:
            raise RuntimeError("FAISS not installed. Run: pip install faiss-cpu")

        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.top_k = top_k
        self.index: Optional[faiss.Index] = None
        self.chunk_store: List[Dict] = []
        self.dimension: Optional[int] = None

    def build(self, chunks, embeddings: np.ndarray):
        """
        Build the FAISS index from chunks and their embeddings.

        Args:
            chunks: List of Chunk objects (from chunker.py)
            embeddings: np.ndarray shape (N, dim), float32, L2-normalized
        """
        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunk count ({len(chunks)}) != embedding count ({len(embeddings)})")

        self.dimension = embeddings.shape[1]
        embeddings = embeddings.astype(np.float32)

        # Build flat inner-product index (= cosine sim for normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings)

        # Store chunk metadata in parallel list
        self.chunk_store = []
        for chunk in chunks:
            self.chunk_store.append({
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "doc_id": chunk.doc_id,
                "source_url": chunk.source_url,
                "source_title": chunk.source_title,
                "doc_type": chunk.doc_type,
                "chunk_index": chunk.chunk_index,
                "metadata": chunk.metadata
            })

        logger.info(
            f"✓ FAISS index built: {self.index.ntotal} vectors, "
            f"dim={self.dimension}, type=IndexFlatIP"
        )

    def save(self):
        """Persist the index and chunk metadata to disk."""
        if self.index is None:
            raise RuntimeError("No index built yet. Call build() first.")

        index_path = self.index_dir / "index.faiss"
        chunks_path = self.index_dir / "chunks.pkl"
        meta_path = self.index_dir / "store_meta.json"

        faiss.write_index(self.index, str(index_path))

        with open(chunks_path, "wb") as f:
            pickle.dump(self.chunk_store, f)

        meta = {
            "total_chunks": len(self.chunk_store),
            "dimension": self.dimension,
            "index_type": "IndexFlatIP",
            "top_k_default": self.top_k
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"✓ Vector store saved to {self.index_dir}/")

    def load(self) -> bool:
        """Load a previously saved index from disk."""
        index_path = self.index_dir / "index.faiss"
        chunks_path = self.index_dir / "chunks.pkl"

        if not index_path.exists() or not chunks_path.exists():
            logger.warning("No saved index found. Build the index first.")
            return False

        self.index = faiss.read_index(str(index_path))
        with open(chunks_path, "rb") as f:
            self.chunk_store = pickle.load(f)

        self.dimension = self.index.d
        logger.info(f"✓ Loaded FAISS index: {self.index.ntotal} vectors, dim={self.dimension}")
        return True

    def search(self, query_embedding: np.ndarray, top_k: Optional[int] = None) -> List[SearchResult]:
        """
        Retrieve top-k most similar chunks.

        Args:
            query_embedding: 1D numpy array, shape (dim,), should be L2-normalized
            top_k: number of results to return (defaults to self.top_k=5)

        Returns:
            List of SearchResult sorted by descending similarity
        """
        if self.index is None:
            raise RuntimeError("No index loaded. Call build() or load() first.")

        k = top_k or self.top_k
        query = query_embedding.astype(np.float32).reshape(1, -1)

        scores, indices = self.index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for empty slots
                continue
            chunk = self.chunk_store[idx]
            results.append(SearchResult(
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                score=float(score),
                source_url=chunk["source_url"],
                source_title=chunk["source_title"],
                doc_type=chunk["doc_type"],
                metadata=chunk["metadata"]
            ))

        return results

    def search_by_text(self, query: str, embedder, top_k: Optional[int] = None) -> List[SearchResult]:
        """Convenience method: embed query then search."""
        query_emb = embedder.embed_query(query)
        return self.search(query_emb, top_k=top_k)

    def get_stats(self) -> Dict:
        """Return store statistics."""
        if self.index is None:
            return {"status": "not loaded"}
        type_counts = {}
        for chunk in self.chunk_store:
            t = chunk["doc_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "chunks_by_type": type_counts,
            "index_type": "IndexFlatIP"
        }
