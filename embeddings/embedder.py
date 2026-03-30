"""
embeddings/embedder.py
-----------------------
Embedding generation for the RAG Course Planning Assistant.

MODEL CHOICE: sentence-transformers/all-MiniLM-L6-v2
  - Free, no API key required
  - 384-dimensional dense vectors
  - Strong semantic similarity performance on general text
  - Fast inference (~14k sentences/sec on CPU)
  - 6-layer MiniLM trained on 1B+ sentence pairs

ALTERNATIVE: text-embedding-ada-002 (OpenAI)
  - Better quality but costs ~$0.0001/1K tokens
  - 1536 dimensions
  - Requires API key
  - Use if you have OPENAI_API_KEY set

The module auto-detects which to use based on env config.
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import List, Optional, Union
from dataclasses import dataclass
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False
    logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")

try:
    import openai
    OPENAI_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class EmbeddingConfig:
    """Configuration for embedding model."""
    model_type: str = "sbert"           # "sbert" or "openai"
    sbert_model: str = "all-MiniLM-L6-v2"
    openai_model: str = "text-embedding-ada-002"
    batch_size: int = 32
    normalize: bool = True              # L2-normalize vectors for cosine similarity


class Embedder:
    """
    Generates embeddings for text chunks.
    Supports sentence-transformers (free) and OpenAI (paid, higher quality).
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self._model = None
        self._init_model()

    def _init_model(self):
        """Initialize embedding model."""
        if self.config.model_type == "openai" and OPENAI_AVAILABLE:
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            logger.info(f"Using OpenAI embeddings: {self.config.openai_model}")
        elif SBERT_AVAILABLE:
            self.config.model_type = "sbert"
            logger.info(f"Loading SentenceTransformer: {self.config.sbert_model}")
            self._model = SentenceTransformer(self.config.sbert_model)
            logger.info("✓ SentenceTransformer loaded")
        else:
            raise RuntimeError(
                "No embedding model available. "
                "Install sentence-transformers: pip install sentence-transformers"
            )

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of texts, returning a 2D numpy array of shape (N, dim).
        """
        if not texts:
            return np.array([])

        if self.config.model_type == "sbert":
            return self._embed_sbert(texts)
        elif self.config.model_type == "openai":
            return self._embed_openai(texts)
        else:
            raise ValueError(f"Unknown model_type: {self.config.model_type}")

    def _embed_sbert(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings with SentenceTransformer."""
        embeddings = self._model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=len(texts) > 50,
            normalize_embeddings=self.config.normalize,
            convert_to_numpy=True
        )
        return embeddings

    def _embed_openai(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings with OpenAI API."""
        all_embeddings = []
        batch_size = 100  # OpenAI supports up to 2048 per request

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(
                model=self.config.openai_model,
                input=batch
            )
            batch_embeddings = [e.embedding for e in response.data]
            all_embeddings.extend(batch_embeddings)

        embeddings = np.array(all_embeddings, dtype=np.float32)
        if self.config.normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / (norms + 1e-8)
        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string."""
        return self.embed_texts([query])[0]

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        if self.config.model_type == "sbert":
            return self._model.get_sentence_embedding_dimension()
        elif self.config.model_type == "openai":
            return 1536  # ada-002 dimension
        return 384  # default


def get_embedder(model_type: str = "auto") -> Embedder:
    """
    Factory function: returns appropriate embedder.
    model_type="auto": uses OpenAI if key available, else SBERT
    """
    if model_type == "auto":
        if OPENAI_AVAILABLE:
            config = EmbeddingConfig(model_type="openai")
        else:
            config = EmbeddingConfig(model_type="sbert")
    elif model_type == "openai":
        config = EmbeddingConfig(model_type="openai")
    else:
        config = EmbeddingConfig(model_type="sbert")

    return Embedder(config)
