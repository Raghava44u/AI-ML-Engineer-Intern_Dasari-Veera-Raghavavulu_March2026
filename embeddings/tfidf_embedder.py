"""
embeddings/tfidf_embedder.py
-----------------------------
TF-IDF based fallback embedder for environments without internet access.
Produces sparse-to-dense embeddings that support cosine similarity search.

Used when sentence-transformers model can't be downloaded.
For production, replace with: sentence-transformers/all-MiniLM-L6-v2
"""

import numpy as np
from typing import List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from loguru import logger


class TFIDFEmbedder:
    """
    TF-IDF based embedder. Fits on corpus, transforms queries.
    Supports cosine similarity via L2-normalized vectors.
    
    Note: This is a demonstration fallback. For production:
    - Use sentence-transformers/all-MiniLM-L6-v2 (384-dim dense)
    - Or text-embedding-ada-002 (OpenAI, 1536-dim)
    """

    def __init__(self, max_features: int = 5000):
        self.max_features = max_features
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(1, 2),      # unigrams + bigrams for course code matching
            sublinear_tf=True,       # log normalization
            min_df=1,
            analyzer='word',
            token_pattern=r'(?u)\b\w+\b'  # includes course codes like CS101
        )
        self.fitted = False
        self._dim = max_features

    def fit(self, texts: List[str]):
        """Fit TF-IDF on corpus texts."""
        self.vectorizer.fit(texts)
        self.fitted = True
        self._dim = len(self.vectorizer.vocabulary_)
        logger.info(f"TF-IDF fitted: vocab size = {self._dim}")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Transform texts to normalized dense vectors."""
        if not self.fitted:
            logger.info("Auto-fitting TF-IDF on provided texts...")
            self.fit(texts)
        
        sparse = self.vectorizer.transform(texts)
        dense = sparse.toarray().astype(np.float32)
        # L2 normalize for cosine similarity
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # avoid division by zero
        normalized = dense / norms
        return normalized

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query."""
        return self.embed_texts([query])[0]

    @property
    def dimension(self) -> int:
        return self._dim


class CorpusAwareTFIDFEmbedder:
    """
    Two-pass embedder: fits on full corpus, then embeds corpus + queries.
    This is required because TF-IDF needs the full vocabulary before embedding.
    """

    def __init__(self, max_features: int = 4096):
        self.embedder = TFIDFEmbedder(max_features=max_features)
        self.corpus_embeddings = None
        self.corpus_texts = []

    def fit_and_embed(self, texts: List[str]) -> np.ndarray:
        """Fit on corpus and return embeddings."""
        self.corpus_texts = texts
        self.embedder.fit(texts)
        self.corpus_embeddings = self.embedder.embed_texts(texts)
        logger.info(f"Corpus embedded: {self.corpus_embeddings.shape}")
        return self.corpus_embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a new query (must call fit_and_embed first)."""
        return self.embedder.embed_query(query)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts."""
        return self.embedder.embed_texts(texts)

    @property
    def dimension(self) -> int:
        return self.embedder.dimension
