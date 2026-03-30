"""
agents/retriever_agent.py - Retriever Agent with hybrid search and chain lookup
Upgraded: hybrid search (BM25 + dense), prerequisite chain retrieval, improved query expansion
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
from vectorstore.faiss_store import FAISSVectorStore, SearchResult
import re
from utils.course_utils import COURSE_REGEX


@dataclass
class RetrievalContext:
    query: str
    results: List[SearchResult]
    citations: List[str]
    sub_queries_used: List[str]

    def to_context_string(self) -> str:
        if not self.results:
            return "No relevant catalog information found."
        sections = ["=== RETRIEVED CATALOG CONTEXT ===\n"]
        for i, r in enumerate(self.results, 1):
            sections.append(
                f"[CHUNK {i}] {r.citation()}\n"
                f"Score: {r.score:.3f}\n"
                f"Content:\n{r.text}\n{'─'*60}"
            )
        return "\n".join(sections)

    def get_citations_list(self):
        return [f"• {r.short_citation()}" for r in self.results]


class RetrieverAgent:
    def __init__(self, vector_store: FAISSVectorStore, embedder, top_k: int = 5):
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self._has_hybrid = hasattr(embedder, 'hybrid_search') and hasattr(embedder, 'bm25') and embedder.bm25.fitted

    def retrieve(self, query: str, context: Optional[Dict] = None) -> RetrievalContext:
        sub_queries = self._expand_query(query, context)
        all_results = self._run_queries(sub_queries)
        top = sorted(all_results.values(), key=lambda x: x.score, reverse=True)[:self.top_k]
        return RetrievalContext(query=query, results=top,
                                citations=[r.citation() for r in top],
                                sub_queries_used=sub_queries)

    def retrieve_for_course_check(self, course_id: str, completed_courses: List[str]) -> RetrievalContext:
        """Direct-lookup retrieval for a specific course with hybrid boosting."""
        queries = []
        if course_id:
            queries += [
                f"COURSE: {course_id}",
                f"{course_id} prerequisites minimum grade requirement",
                f"{course_id} eligibility requirements credits corequisites",
            ]
        # Context on completed courses (limit to most relevant)
        for c in completed_courses[:3]:
            queries.append(f"COURSE: {c}")
        queries.append("prerequisite minimum grade enrollment policy")

        all_results = self._run_queries(queries)

        # Force-include the course's own chunk if it exists in the store
        if course_id:
            from utils.course_utils import normalize_course_id
            target_norm = normalize_course_id(course_id)
            for chunk in self.vector_store.chunk_store:
                chunk_course = chunk["doc_id"].replace("course_", "", 1) if chunk["doc_id"].startswith("course_") else ""
                chunk_norm = normalize_course_id(chunk_course)
                if chunk["doc_id"] == f"course_{course_id}" or chunk_norm == target_norm:
                    synthetic = SearchResult(
                        chunk_id=chunk["chunk_id"],
                        text=chunk["text"],
                        score=1.0,
                        source_url=chunk["source_url"],
                        source_title=chunk["source_title"],
                        doc_type=chunk["doc_type"],
                        metadata=chunk["metadata"]
                    )
                    all_results[chunk["chunk_id"]] = synthetic
                    break

        top = sorted(all_results.values(), key=lambda x: x.score, reverse=True)[:self.top_k]
        return RetrievalContext(
            query=f"Prerequisite check for {course_id}",
            results=top,
            citations=[r.citation() for r in top],
            sub_queries_used=queries
        )

    def retrieve_for_chain(self, course_id: str, completed_courses: List[str]) -> RetrievalContext:
        """
        Retrieve all courses in a prerequisite chain by walking backward through prerequisites.
        Used for multi-hop chain reasoning.
        """
        queries = []
        if course_id:
            queries += [
                f"COURSE: {course_id}",
                f"{course_id} prerequisites prerequisite chain",
            ]

        # Get the target course chunk first
        all_results = self._run_queries(queries)

        # Find all course chunks mentioned as prerequisites and retrieve them too
        collected_codes = set()
        collected_codes.add(course_id)
        
        # Walk through found chunks to discover prerequisite courses
        for _ in range(4):  # max 4 hops
            new_codes = set()
            for result in all_results.values():
                prereq_match = re.search(
                    r'(?:Prereq(?:uisite)?s?):\s*(.+?)(?:\n\s*Units:|\n\s*Credit cannot|\n\s*URL:|\n\s*Lecture:|\n\s*Co-requisite|\n\s*Min|\n\s*Offered|\n\s*Category|\n\s*Learning|$)',
                    result.text, re.IGNORECASE | re.DOTALL
                )
                if prereq_match:
                    prereq_text = prereq_match.group(1)
                    from utils.course_utils import extract_course_codes
                    codes = extract_course_codes(prereq_text)
                    for code in codes:
                        if code not in collected_codes:
                            new_codes.add(code)
                            collected_codes.add(code)

            if not new_codes:
                break

            # Retrieve newly discovered prerequisite courses
            for code in new_codes:
                # Direct chunk lookup first
                for chunk in self.vector_store.chunk_store:
                    if chunk["doc_id"] == f"course_{code}":
                        synthetic = SearchResult(
                            chunk_id=chunk["chunk_id"],
                            text=chunk["text"],
                            score=0.9,
                            source_url=chunk["source_url"],
                            source_title=chunk["source_title"],
                            doc_type=chunk["doc_type"],
                            metadata=chunk["metadata"]
                        )
                        all_results[chunk["chunk_id"]] = synthetic
                        break
                else:
                    # Fallback to vector search
                    logger.debug(f"Direct lookup failed for {code}, using vector search")
                    sub_results = self._run_queries([f"COURSE: {code}"])
                    all_results.update(sub_results)

        # Log retrieved course IDs for debugging
        retrieved_ids = []
        for r in all_results.values():
            m = re.search(f'COURSE: ({COURSE_REGEX})', r.text)
            if m: retrieved_ids.append(m.group(1))
        logger.info(f"RETRIEVED COURSE IDs: {list(set(retrieved_ids))}")

        # Also include degree requirement context
        extra_queries = [
            "prerequisite chain order sequence",
            "program core requirements courses",
        ]
        for eq in extra_queries:
            sub_results = self._run_queries([eq])
            for k, v in sub_results.items():
                if k not in all_results:
                    v.score *= 0.5  # lower priority
                    all_results[k] = v

        # Return more results for chain queries
        chain_top_k = min(self.top_k + 5, len(all_results))
        top = sorted(all_results.values(), key=lambda x: x.score, reverse=True)[:chain_top_k]
        return RetrievalContext(
            query=f"Prerequisite chain for {course_id}",
            results=top,
            citations=[r.citation() for r in top],
            sub_queries_used=queries + [f"COURSE: {c}" for c in collected_codes]
        )

    def retrieve_for_planning(self, profile_summary: str, program: str) -> RetrievalContext:
        queries = [
            f"{program} degree requirements core courses",
            f"{program} elective requirements upper-division",
            "graduation requirements credits GPA",
            "upper division courses prerequisites",
            "core required courses CS major",
            "concentration tracks AI ML systems",
        ]
        all_results = self._run_queries(queries)

        # Also include all course chunks for planning (need to see what's available)
        for chunk in self.vector_store.chunk_store:
            if chunk["doc_type"] == "course" and chunk["chunk_id"] not in all_results:
                all_results[chunk["chunk_id"]] = SearchResult(
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    score=0.3,  # low base score
                    source_url=chunk["source_url"],
                    source_title=chunk["source_title"],
                    doc_type=chunk["doc_type"],
                    metadata=chunk["metadata"]
                )

        # Return more results for planning
        plan_top_k = min(self.top_k + 10, len(all_results))
        top = sorted(all_results.values(), key=lambda x: x.score, reverse=True)[:plan_top_k]
        return RetrievalContext(query=f"Plan for {program}", results=top,
                                citations=[r.citation() for r in top],
                                sub_queries_used=queries)

    def _run_queries(self, queries: List[str]) -> Dict[str, SearchResult]:
        all_results: Dict[str, SearchResult] = {}
        seen = set()
        for q in queries:
            if q in seen:
                continue
            seen.add(q)
            try:
                results = self.vector_store.search_by_text(q, self.embedder, top_k=self.top_k)
                for r in results:
                    if r.chunk_id not in all_results or r.score > all_results[r.chunk_id].score:
                        all_results[r.chunk_id] = r
            except Exception as e:
                logger.warning(f"Query failed '{q}': {e}")
        return all_results

    def _expand_query(self, query: str, context=None) -> List[str]:
        queries = [query]
        q_lower = query.lower()
        from utils.course_utils import extract_course_codes
        codes = extract_course_codes(query)
        for code in codes:
            queries += [f"COURSE: {code}", f"{code} prerequisites credits minimum grade"]
        if any(w in q_lower for w in ["prerequisite","prereq","can i take","eligible","qualify"]):
            queries.append("prerequisite minimum grade enrollment policy")
        if any(w in q_lower for w in ["plan","schedule","recommend","next semester"]):
            queries += ["degree requirements core courses electives", "graduation requirements"]
        if any(w in q_lower for w in ["repeat","repeat policy","retake","failed"]):
            queries.append("course repeat policy grade replacement attempts")
        if any(w in q_lower for w in ["gpa","grade point","academic standing"]):
            queries.append("minimum GPA academic probation CS major")
        if any(w in q_lower for w in ["transfer","transfer credit"]):
            queries.append("credit transfer policy maximum transfer")
        if context and context.get("target_program"):
            queries.append(f"{context['target_program']} requirements")
        seen, unique = set(), []
        for q in queries:
            if q not in seen:
                seen.add(q); unique.append(q)
        return unique[:8]
