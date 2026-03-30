"""
agents/pipeline.py - Main orchestration pipeline
Upgraded: hybrid embedder (sentence-transformers + BM25 + RRF)
FIXED: intent detection, empty completed_courses, program queries, out-of-scope detection
"""

import json, pickle, re
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger

from agents.intake_agent import IntakeAgent, StudentProfile
from agents.retriever_agent import RetrieverAgent, RetrievalContext
from agents.planner_agent import PlannerAgent, PlannerOutput
from agents.verifier_agent import VerifierAgent, VerificationResult
from vectorstore.faiss_store import FAISSVectorStore
from ingestion.ingest import run_ingestion
from ingestion.chunker import chunk_documents
from utils.course_utils import extract_course_codes


class CourseAssistantPipeline:
    def __init__(self, data_dir="data", vectorstore_dir="vectorstore", top_k=5):
        self.data_dir = Path(data_dir)
        self.vectorstore_dir = vectorstore_dir
        self.top_k = top_k
        self.embedder = None
        self.vector_store = FAISSVectorStore(index_dir=vectorstore_dir, top_k=top_k)
        self.intake_agent = IntakeAgent()
        self.retriever_agent = None
        self.planner_agent = PlannerAgent()
        self.verifier_agent = VerifierAgent(strict_mode=True)
        self._index_loaded = False

    def build_index(self):
        logger.info("BUILDING RAG INDEX")
        documents = run_ingestion(raw_dir=str(self.data_dir/"raw"), processed_dir=str(self.data_dir/"processed"))
        chunks = chunk_documents(documents)
        logger.info(f"{len(chunks)} chunks created")

        # Try hybrid embedder first, fall back to TF-IDF
        try:
            from embeddings.hybrid_embedder import HybridEmbedder
            self.embedder = HybridEmbedder(
                dense_model="all-MiniLM-L6-v2",
                use_reranker=False  # Set True for production with cross-encoder
            )
            texts = [c.text for c in chunks]
            embeddings = self.embedder.fit_and_embed(texts)
            logger.info(f"✓ Using HYBRID embedder (sentence-transformers + BM25)")
            
            # Save BM25 state for later loading
            bm25_path = Path(self.vectorstore_dir) / "bm25_state.pkl"
            Path(self.vectorstore_dir).mkdir(exist_ok=True)
            with open(bm25_path, "wb") as f:
                pickle.dump({
                    'doc_lengths': self.embedder.bm25.doc_lengths,
                    'avg_dl': self.embedder.bm25.avg_dl,
                    'doc_freqs': self.embedder.bm25.doc_freqs,
                    'term_freqs': self.embedder.bm25.term_freqs,
                    'n_docs': self.embedder.bm25.n_docs,
                    'corpus_texts': self.embedder.corpus_texts,
                }, f)
                
        except Exception as e:
            logger.warning(f"Hybrid embedder failed: {e}. Falling back to TF-IDF.")
            from embeddings.tfidf_embedder import CorpusAwareTFIDFEmbedder
            self.embedder = CorpusAwareTFIDFEmbedder(max_features=2048)
            texts = [c.text for c in chunks]
            embeddings = self.embedder.fit_and_embed(texts)

            vocab_path = Path(self.vectorstore_dir) / "tfidf_vectorizer.pkl"
            Path(self.vectorstore_dir).mkdir(exist_ok=True)
            with open(vocab_path, "wb") as f:
                pickle.dump(self.embedder.embedder.vectorizer, f)

        self.vector_store.build(chunks, embeddings)
        self.vector_store.save()
        self.retriever_agent = RetrieverAgent(self.vector_store, self.embedder, top_k=self.top_k)
        self._index_loaded = True
        stats = self.vector_store.get_stats()
        logger.info(f"Index built: {stats}")
        return stats

    def load_index(self):
        success = self.vector_store.load()
        if success:
            # Try hybrid embedder first
            try:
                from embeddings.hybrid_embedder import HybridEmbedder
                self.embedder = HybridEmbedder(
                    dense_model="all-MiniLM-L6-v2",
                    use_reranker=False
                )
                
                # Restore BM25 state
                bm25_path = Path(self.vectorstore_dir) / "bm25_state.pkl"
                if bm25_path.exists():
                    with open(bm25_path, "rb") as f:
                        bm25_state = pickle.load(f)
                    self.embedder.bm25.doc_lengths = bm25_state['doc_lengths']
                    self.embedder.bm25.avg_dl = bm25_state['avg_dl']
                    self.embedder.bm25.doc_freqs = bm25_state['doc_freqs']
                    self.embedder.bm25.term_freqs = bm25_state['term_freqs']
                    self.embedder.bm25.n_docs = bm25_state['n_docs']
                    self.embedder.bm25.fitted = True
                    self.embedder.corpus_texts = bm25_state.get('corpus_texts', [])
                    logger.info("✓ BM25 state restored")
                    
                logger.info("✓ Loaded hybrid embedder")
            except Exception as e:
                logger.warning(f"Hybrid embedder not available: {e}. Trying TF-IDF...")
                vocab_path = Path(self.vectorstore_dir) / "tfidf_vectorizer.pkl"
                if vocab_path.exists():
                    from embeddings.tfidf_embedder import CorpusAwareTFIDFEmbedder
                    self.embedder = CorpusAwareTFIDFEmbedder(max_features=2048)
                    with open(vocab_path, "rb") as f:
                        self.embedder.embedder.vectorizer = pickle.load(f)
                    self.embedder.embedder.fitted = True
                    self.embedder.embedder._dim = len(self.embedder.embedder.vectorizer.vocabulary_)

            self.retriever_agent = RetrieverAgent(self.vector_store, self.embedder, top_k=self.top_k)
            self._index_loaded = True
        return success

    def run(self, query, student_info, verbose=True):
        if not self._index_loaded:
            raise RuntimeError("Index not loaded.")

        if verbose:
            logger.info(f"QUERY: {query[:80]}")

        # 1. INTAKE
        intake_result = self.intake_agent.process(student_info)
        profile = intake_result["profile"]

        if intake_result["status"] == "needs_clarification":
            return self._format_clarification_response(
                query, intake_result["clarifying_questions"], intake_result["warnings"], profile)

        profile = self.intake_agent.apply_defaults(profile)

        # 2. DETECT INTENT
        intent = self._detect_intent(query)
        codes = extract_course_codes(query)
        
        # Heuristic for target course (same as in PlannerAgent)
        target = codes[0] if codes else ""
        if len(codes) > 1:
            q_low = query.lower()
            for code in codes:
                pattern = rf"(?:before|for|enrolling? in|take|regarding?|about)\s+{re.escape(code)}"
                if re.search(pattern, q_low, re.IGNORECASE):
                    target = code
                    break
            else:
                target = codes[-1]

        # 3. RETRIEVAL (with hybrid search when available)
        if intent == "out_of_scope":
            # Still do retrieval for citations, but use general retrieval
            ctx = self.retriever_agent.retrieve(query, context={"target_program": profile.target_program})
        elif intent == "prereq_check":
            ctx = self.retriever_agent.retrieve_for_course_check(target, profile.completed_courses or [])
        elif intent == "course_plan":
            ctx = self.retriever_agent.retrieve_for_planning(profile.summary(), profile.target_program or "CS")
        elif intent == "prereq_chain":
            ctx = self.retriever_agent.retrieve_for_chain(target, profile.completed_courses or [])
        elif intent == "program_req":
            ctx = self.retriever_agent.retrieve_for_planning(profile.summary(), profile.target_program or "CS")
        else:
            ctx = self.retriever_agent.retrieve(query, context={"target_program": profile.target_program})

        # 4. PLANNING
        if intent == "out_of_scope":
            planner_output = self.planner_agent.handle_out_of_scope(query)
        elif intent == "prereq_check":
            planner_output = self.planner_agent.check_prerequisites(query, profile, ctx)
        elif intent == "prereq_chain":
            planner_output = self.planner_agent.check_prerequisite_chain(query, profile, ctx)
        elif intent == "course_plan":
            planner_output = self.planner_agent.generate_course_plan(profile, ctx)
        elif intent == "program_req":
            planner_output = self.planner_agent.handle_program_query(query, profile, ctx)
        else:
            # General query — try prereq check if course code found, else program query
            if codes:
                planner_output = self.planner_agent.check_prerequisites(query, profile, ctx)
            else:
                planner_output = self.planner_agent.handle_program_query(query, profile, ctx)

        # 5. VERIFICATION
        verification = self.verifier_agent.verify(planner_output, ctx, query)
        final_output = verification.verified_output
        formatted = final_output.format_output()

        if intake_result.get("warnings"):
            formatted += "\n⚠️  PROFILE WARNINGS:\n" + "\n".join(f"  • {w}" for w in intake_result["warnings"])

        return {
            "query": query,
            "formatted_output": formatted,
            "eligibility_decision": final_output.eligibility_decision,
            "recommended_courses": final_output.recommended_courses,
            "citations": final_output.citations,
            "clarifying_questions": final_output.clarifying_questions,
            "verification_passed": verification.passed,
            "verification_issues": verification.issues_found,
            "citation_coverage": verification.citation_coverage,
            "profile": profile,
            "retrieval_context": ctx,
        }

    def _detect_intent(self, query):
        q = query.lower()
        
        # Out of scope detection (MUST come first)
        out_of_scope_keywords = [
            "which professor", "who teaches", "what time", "which section",
            "how many seats", "waitlist", "financial aid", "tuition",
            "room and board", "room number", "cost to audit",
            "deadline for financial", "how much does it cost",
            "scholarship", "housing"
        ]
        if any(kw in q for kw in out_of_scope_keywords):
            return "out_of_scope"
        
        # Program requirements detection (before prereq_check to avoid false positives)
        program_keywords = [
            "core requirements", "degree requirements", "how many units",
            "how many credits required", "graduation requirement",
            "capstone requirement", "count towards", "counts toward",
            "math requirement", "required for course 18",
            "required for the .* major", "program requirements",
            "what are the .* requirements", "elective requirement",
            "concentration", "core courses required"
        ]
        if any(re.search(kw, q) for kw in program_keywords):
            return "program_req"
        
        # Prerequisite chain detection
        chain_keywords = [
            "prerequisite chain", "full chain", "what order",
            "starting from", "in what order", "steps to", "path to",
            "sequence of courses", "chain of courses",
            "what do i need to complete before",
            "what do i need before",
            "need to complete before",
        ]
        if any(kw in q for kw in chain_keywords):
            return "prereq_chain"
        
        # Prereq check: queries about specific course eligibility
        prereq_keywords = [
            "can i take", "can i enroll", "eligible for", "prerequisites for",
            "qualify for", "am i eligible", "am i ready",
            "accessible", "what are the prerequisites",
            "check eligibility", "prerequisite check",
            "is required before", "required before",
            "what do i need to take", "what is required"
        ]
        if any(kw in q for kw in prereq_keywords):
            return "prereq_check"
        
        # Also detect "what do I need before I can take X" → prereq_check (not chain)
        if "need before" in q or "before i can" in q:
            codes = extract_course_codes(query)
            if codes:
                return "prereq_check"
        
        # Course planning
        plan_keywords = [
            "plan", "schedule", "what should i take", "recommend",
            "next semester", "next term", "suggest", "help me plan"
        ]
        if any(kw in q for kw in plan_keywords):
            return "course_plan"
        
        # Implicit prereq check: mentions course codes with "if I" / "I have"
        codes = extract_course_codes(query)
        if codes and any(kw in q for kw in ["if i", "i have", "i took", "i completed", "having taken"]):
            return "prereq_check"
        
        return "general"

    def _format_clarification_response(self, query, questions, warnings, profile):
        lines = ["="*70, "📋 CLARIFICATION NEEDED", "="*70, "",
                 "Answer / Plan: Missing required information.", "",
                 "CLARIFYING QUESTIONS:"]
        for i, q in enumerate(questions, 1):
            lines.append(f"  {i}. {q}")
        lines += ["", "Citations: N/A", "Assumptions / Not in catalog:",
                  "  • No planning performed yet.", "", "="*70]
        return {"query": query, "formatted_output": "\n".join(lines),
                "eligibility_decision": None, "recommended_courses": None,
                "citations": [], "clarifying_questions": questions,
                "verification_passed": None, "verification_issues": [],
                "citation_coverage": 0.0, "profile": profile, "retrieval_context": None}
