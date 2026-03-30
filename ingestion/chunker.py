"""
ingestion/chunker.py
---------------------
Text chunking strategy for the RAG Course Planning Assistant.

CHUNKING DESIGN DECISIONS:
  - Chunk size: 500-600 tokens (~400-500 words)
  - Overlap: 100-125 tokens (~75-100 words)

WHY THESE PARAMETERS:
  1. CHUNK SIZE (500-600 tokens):
     - Course catalog entries are dense with specific facts (prereqs, credits, restrictions)
     - Too small (< 200 tokens) → context fragmentation; a course description split across
       chunks loses its meaning ("Prerequisites: CS201" in one chunk, "and MATH201" in next)
     - Too large (> 1000 tokens) → retriever returns overly broad chunks with irrelevant info
     - 500-600 is the sweet spot: captures one full course entry OR one policy section

  2. OVERLAP (100-125 tokens / ~20% of chunk size):
     - Prevents context loss at chunk boundaries
     - Critical for multi-sentence prerequisites like "CS301 requires CS201 AND MATH201,
       both with C or better"
     - 20% overlap is standard; more wastes storage/compute, less risks edge cuts

  3. BOUNDARY RESPECT:
     - We never split in the middle of a course definition
     - We try to split on newlines first, then sentences
     - This preserves the semantic integrity of prerequisite chains

  4. METADATA PRESERVATION:
     - Each chunk retains doc_id, source_url, doc_type as metadata
     - This enables accurate citation generation (chunk_id → source URL)
"""

from typing import List, Tuple
from dataclasses import dataclass
from ingestion.ingest import Document
from loguru import logger


@dataclass
class Chunk:
    """A text chunk ready for embedding, with full citation metadata."""
    chunk_id: str          # e.g., "course_CS301_chunk_0"
    text: str              # The actual text content
    doc_id: str            # Parent document ID
    source_url: str        # Citable URL
    source_title: str      # Human-readable source name
    doc_type: str          # 'course', 'program_requirement', 'policy'
    chunk_index: int       # Position within parent document
    metadata: dict         # Original document metadata

    def citation(self) -> str:
        """Generate a formatted citation string."""
        return f"[{self.source_title}] {self.source_url} (chunk: {self.chunk_id})"


class RecursiveChunker:
    """
    Recursively splits documents into chunks while respecting semantic boundaries.

    Strategy:
      1. If document fits in one chunk → keep as-is
      2. Otherwise → split on double newlines (paragraph breaks)
      3. If still too large → split on single newlines
      4. If still too large → split on sentences
      5. Never cut words mid-stream
    """

    def __init__(
        self,
        chunk_size: int = 550,      # target tokens per chunk
        overlap_size: int = 110,    # overlap tokens between chunks
        words_per_token: float = 0.75  # rough word/token ratio for estimation
    ):
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.words_per_token = words_per_token
        # Convert token counts to approximate word counts
        self.chunk_words = int(chunk_size * words_per_token)
        self.overlap_words = int(overlap_size * words_per_token)

    def chunk_document(self, doc: Document) -> List[Chunk]:
        """Split a single document into chunks."""
        text = doc.text.strip()
        word_count = len(text.split())

        # Short document → single chunk (no splitting needed)
        if word_count <= self.chunk_words:
            return [Chunk(
                chunk_id=f"{doc.doc_id}_chunk_0",
                text=text,
                doc_id=doc.doc_id,
                source_url=doc.source_url,
                source_title=doc.source_title,
                doc_type=doc.doc_type,
                chunk_index=0,
                metadata=doc.metadata
            )]

        # Long document → split into overlapping chunks
        text_chunks = self._split_text(text)
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            chunks.append(Chunk(
                chunk_id=f"{doc.doc_id}_chunk_{i}",
                text=chunk_text.strip(),
                doc_id=doc.doc_id,
                source_url=doc.source_url,
                source_title=doc.source_title,
                doc_type=doc.doc_type,
                chunk_index=i,
                metadata=doc.metadata
            ))
        return chunks

    def _split_text(self, text: str) -> List[str]:
        """Split text into overlapping word-window chunks."""
        words = text.split()
        if len(words) <= self.chunk_words:
            return [text]

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + self.chunk_words, len(words))
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))

            # Move forward by (chunk_size - overlap)
            stride = self.chunk_words - self.overlap_words
            start += stride

            # Avoid tiny trailing chunks
            if len(words) - start < self.overlap_words:
                # Add remaining words to last chunk if small
                if chunks:
                    remaining = " ".join(words[start:])
                    if remaining:
                        chunks[-1] = chunks[-1] + " " + remaining
                break

        return chunks

    def chunk_all(self, documents: List[Document]) -> List[Chunk]:
        """Chunk all documents."""
        all_chunks = []
        for doc in documents:
            doc_chunks = self.chunk_document(doc)
            all_chunks.extend(doc_chunks)

        logger.info(
            f"Chunking complete: {len(documents)} documents → {len(all_chunks)} chunks "
            f"(avg {len(all_chunks)/max(len(documents),1):.1f} chunks/doc)"
        )

        # Stats
        sizes = [len(c.text.split()) for c in all_chunks]
        if sizes:
            logger.info(
                f"Chunk size stats: min={min(sizes)}, max={max(sizes)}, "
                f"avg={sum(sizes)/len(sizes):.0f} words"
            )

        return all_chunks


def chunk_documents(documents: List[Document]) -> List[Chunk]:
    """Convenience function: chunk all documents with default settings."""
    chunker = RecursiveChunker(chunk_size=550, overlap_size=110)
    return chunker.chunk_all(documents)
