"""
embeddings/hybrid_embedder.py
------------------------------
Hybrid embedder: sentence-transformers (dense) + BM25 (sparse) + reranking.

Production-grade upgrade from TF-IDF:
  - Dense: sentence-transformers/all-MiniLM-L6-v2 (384-dim)
  - Sparse: BM25 with Okapi scoring for keyword-level precision
  - Reranking: cross-encoder reranking on candidate set
  - Hybrid fusion: Reciprocal Rank Fusion (RRF) to merge results

WHY HYBRID:
  - Dense embeddings excel at semantic similarity (synonyms, paraphrasing)
  - BM25 excels at exact keyword matching (course codes like CS301, grade letters)
  - RRF fusion gives best of both worlds without needing tuned weights
  - Cross-encoder reranking improves final ordering significantly
"""

import os
import re
import math
import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import Counter
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False
    logger.warning("sentence-transformers not available. Install: pip install sentence-transformers")


class BM25:
    """
    Okapi BM25 implementation for sparse keyword retrieval.
    Complements dense embeddings for exact course-code/grade matching.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_lengths: List[int] = []
        self.avg_dl: float = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.term_freqs: List[Dict[str, int]] = []
        self.n_docs: int = 0
        self.fitted = False

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + punctuation tokenizer that preserves course codes."""
        text = text.upper()
        # Keep MIT-style course codes intact (e.g., 6.1210, 18.06, 6.100A) and legacy (CS301)
        tokens = re.findall(r'\d+\.[A-Z0-9]+(?:\[[A-Z]\])?|[A-Z]{2,4}\d+[A-Z]*|[A-Za-z]+|\d+', text)
        return [t.lower() for t in tokens]

    def fit(self, documents: List[str]):
        """Fit BM25 on corpus."""
        self.n_docs = len(documents)
        self.doc_lengths = []
        self.term_freqs = []
        self.doc_freqs = {}

        for doc in documents:
            tokens = self._tokenize(doc)
            self.doc_lengths.append(len(tokens))
            tf = Counter(tokens)
            self.term_freqs.append(tf)
            for token in set(tokens):
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avg_dl = sum(self.doc_lengths) / max(self.n_docs, 1)
        self.fitted = True
        logger.info(f"BM25 fitted: {self.n_docs} docs, {len(self.doc_freqs)} unique terms")

    def score(self, query: str) -> np.ndarray:
        """Score all documents against a query."""
        if not self.fitted:
            raise RuntimeError("BM25 not fitted. Call fit() first.")

        query_tokens = self._tokenize(query)
        scores = np.zeros(self.n_docs, dtype=np.float32)

        for token in query_tokens:
            if token not in self.doc_freqs:
                continue

            df = self.doc_freqs[token]
            idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1.0)

            for i in range(self.n_docs):
                tf = self.term_freqs[i].get(token, 0)
                if tf == 0:
                    continue
                dl = self.doc_lengths[i]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                scores[i] += idf * numerator / denominator

        return scores

    def get_top_k(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Get top-k document indices and scores."""
        scores = self.score(query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]


class HybridEmbedder:
    """
    Production-grade hybrid embedder combining:
    1. Dense: sentence-transformers (all-MiniLM-L6-v2, 384-dim)
    2. Sparse: BM25 for exact keyword matching
    3. Reranking: cross-encoder for final ordering (optional)
    
    Fusion strategy: Reciprocal Rank Fusion (RRF)
    """

    def __init__(
        self,
        dense_model: str = "all-MiniLM-L6-v2",
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        use_reranker: bool = False,
        rrf_k: int = 60
    ):
        self.rrf_k = rrf_k
        self.use_reranker = use_reranker
        self.bm25 = BM25()
        self.corpus_texts: List[str] = []
        self.corpus_embeddings: Optional[np.ndarray] = None
        self._dense_model = None
        self._reranker = None
        self._dense_model_name = dense_model
        self._reranker_model_name = reranker_model
        self._init_models()

    def _init_models(self):
        """Initialize dense encoder and optional reranker."""
        if SBERT_AVAILABLE:
            try:
                logger.info(f"Loading dense model: {self._dense_model_name}")
                self._dense_model = SentenceTransformer(self._dense_model_name)
                logger.info(f"✓ Dense model loaded: {self._dense_model.get_sentence_embedding_dimension()}-dim")

                if self.use_reranker:
                    try:
                        logger.info(f"Loading reranker: {self._reranker_model_name}")
                        self._reranker = CrossEncoder(self._reranker_model_name)
                        logger.info("✓ Reranker loaded")
                    except Exception as e:
                        logger.warning(f"Could not load reranker: {e}. Proceeding without reranking.")
                        self.use_reranker = False
            except Exception as e:
                logger.warning(f"Could not load dense model: {e}. Falling back to TF-IDF.")
                self._dense_model = None
        else:
            logger.warning("sentence-transformers not available. Using TF-IDF fallback.")

    def fit_and_embed(self, texts: List[str]) -> np.ndarray:
        """Fit BM25 on corpus and generate dense embeddings."""
        self.corpus_texts = texts

        # Fit BM25
        self.bm25.fit(texts)

        # Generate dense embeddings
        if self._dense_model:
            self.corpus_embeddings = self._dense_model.encode(
                texts,
                batch_size=32,
                show_progress_bar=len(texts) > 50,
                normalize_embeddings=True,
                convert_to_numpy=True
            )
            logger.info(f"✓ Corpus embedded (dense): {self.corpus_embeddings.shape}")
        else:
            # TF-IDF fallback
            from embeddings.tfidf_embedder import TFIDFEmbedder
            self._tfidf = TFIDFEmbedder(max_features=2048)
            self._tfidf.fit(texts)
            self.corpus_embeddings = self._tfidf.embed_texts(texts)
            logger.info(f"✓ Corpus embedded (TF-IDF fallback): {self.corpus_embeddings.shape}")

        return self.corpus_embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query using the dense model."""
        if self._dense_model:
            return self._dense_model.encode(
                query, normalize_embeddings=True, convert_to_numpy=True
            )
        else:
            return self._tfidf.embed_query(query)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed multiple texts."""
        if self._dense_model:
            return self._dense_model.encode(
                texts, batch_size=32,
                normalize_embeddings=True, convert_to_numpy=True
            )
        else:
            return self._tfidf.embed_texts(texts)

    def hybrid_search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Hybrid search: combine dense retrieval + BM25 using Reciprocal Rank Fusion.
        
        RRF formula: score(d) = Σ 1/(k + rank_i(d)) for each retrieval system i
        """
        if self.corpus_embeddings is None:
            raise RuntimeError("No corpus. Call fit_and_embed() first.")

        # Dense retrieval
        query_emb = self.embed_query(query)
        dense_scores = np.dot(self.corpus_embeddings, query_emb)
        dense_ranking = np.argsort(dense_scores)[::-1]

        # BM25 retrieval
        bm25_scores = self.bm25.score(query)
        bm25_ranking = np.argsort(bm25_scores)[::-1]

        # Reciprocal Rank Fusion
        rrf_scores: Dict[int, float] = {}
        for rank, idx in enumerate(dense_ranking[:top_k * 3]):
            rrf_scores[int(idx)] = rrf_scores.get(int(idx), 0.0) + 1.0 / (self.rrf_k + rank + 1)
        for rank, idx in enumerate(bm25_ranking[:top_k * 3]):
            rrf_scores[int(idx)] = rrf_scores.get(int(idx), 0.0) + 1.0 / (self.rrf_k + rank + 1)

        # Sort by RRF score
        candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k * 2]

        # Optional reranking
        if self.use_reranker and self._reranker and candidates:
            pairs = [(query, self.corpus_texts[idx]) for idx, _ in candidates]
            rerank_scores = self._reranker.predict(pairs)
            reranked = sorted(
                zip([idx for idx, _ in candidates], rerank_scores),
                key=lambda x: x[1], reverse=True
            )
            return [(idx, float(score)) for idx, score in reranked[:top_k]]

        return [(idx, score) for idx, score in candidates[:top_k]]

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        if self._dense_model:
            return self._dense_model.get_sentence_embedding_dimension()
        return self.corpus_embeddings.shape[1] if self.corpus_embeddings is not None else 384
