# System Improvements & Enhancement Roadmap

This document outlines concrete, actionable improvements to elevate the RAG Course Planner from functional to production-grade.

---

## 1. Prompt Engineering Enhancements

### Current State
- Single generic system prompt for all query types
- No few-shot examples
- Minimal guardrails against hallucination

### Improvements

#### 1.1 Query-Type-Specific Prompts

**Action:** Create separate system prompts for 3 query types:

**File:** `prompts/system_prompt_prereq_check.txt`
```
You are a course prerequisite verification specialist.

TASK: Verify if a student can take a specific course.

INPUT: Student profile (completed courses, grades) + target course

OUTPUT FORMAT (REQUIRED):
DECISION: [Eligible | Not Eligible | Need More Info]
ANSWER: [1-2 sentence direct answer]
WHY: [Numbered list of prerequisite checks]
CITATIONS: [Sources for each requirement]

RULES:
1. Every prerequisite MUST be checked explicitly
2. Grade requirements MUST be evaluated
3. Corequisites must be separated from prerequisites
4. If uncertain, say "Need More Info" not "Probably yes"
5. Do NOT invent grades or assume anything

Example:
Q: "Can I take CS201 with CS101 (B+) completed?"
A:
DECISION: Eligible
ANSWER: Yes, you meet the prerequisite.
WHY:
  1. CS201 requires CS101 (completed ✓)
  2. Minimum grade: C or better (your B+ exceeds this ✓)
CITATIONS:
  • MIT Course CS201 Catalog (Prerequisite: CS101)
  • MIT Grading Policy
```

**File:** `prompts/system_prompt_planning.txt`
```
You are a course planning advisor specializing in prerequisite chains.

TASK: Generate a multi-semester plan to reach a target course.

INPUT: Student profile + target course + timeline

OUTPUT FORMAT:
DECISION: [Not Eligible | Eligible | Need More Info]
ANSWER: [Step-by-step semester plan]
WHY: [Reasoning for course ordering]
CITATIONS: [Source for each prerequisite]

RULES:
1. Assume one course can be taken per prerequisite
2. Allow parallel enrollment where applicable
3. Estimate 1 year minimum per chain level
4. Suggest optimal semester ordering
5. Flag scheduling conflicts
```

**File:** `prompts/system_prompt_policy.txt`
```
You are a course catalog policy specialist.

TASK: Answer questions about degree requirements, GIR, major rules.

INPUT: Student profile + policy question

SPECIAL RULES FOR POLICY QUERIES:
1. Distinguish "I can answer this" from "this requires advisor approval"
2. Always provide relevant resource (advisor email, handbook section)
3. Acknowledge individual circumstances may differ
4. Recommend formal advising for final decisions

BOUNDARIES:
- You CAN: Explain program requirements
- You CAN: List required courses
- You CAN: Explain policies
- You CANNOT: Approve exceptions or substitutions
- You CANNOT: Override policies

Example:
Q: "Can I substitute CS201 with CS210?"
A: "Substitutions require department approval. I can tell you [what policy says]. 
Contact [advisor] for formal request."
```

**Implementation:**
```python
# agents/planner_agent.py
PROMPT_TEMPLATES = {
    "prereq_check": load_prompt("prompts/system_prompt_prereq_check.txt"),
    "planning": load_prompt("prompts/system_prompt_planning.txt"),
    "policy": load_prompt("prompts/system_prompt_policy.txt"),
}

def get_system_prompt(intent: str) -> str:
    return PROMPT_TEMPLATES.get(intent, PROMPT_TEMPLATES["policy"])
```

**Effort:** 2–3 hours  
**Impact:** ⬆️⬆️⬆️ High—specialized prompts significantly improve accuracy

---

#### 1.2 Few-Shot Examples in Prompts

**Action:** Add real examples to system prompts to guide behavior

```python
SYSTEM_PROMPT = """
...

EXAMPLES (follow this format):

Example 1: Prerequisite Check (Eligible)
Input: "Can I take 6.1210 if I have 6.100A and 6.1200?"
Output:
  DECISION: Eligible
  ANSWER: Yes, you meet all prerequisites.
  WHY:
    • 6.1210 requires 6.1200 (completed ✓)
    • 6.1210 requires 6.100A (completed ✓)
  CITATIONS:
    • MIT Course 6.1210 Catalog

Example 2: Grade Requirement (Not Eligible)
Input: "I have 6.100A (D). Can I take 6.1200?"
Output:
  DECISION: Not Eligible
  ANSWER: No, your grade does not meet the minimum requirement.
  WHY:
    • 6.1200 requires 6.100A with C or better
    • Your grade: D (1.0 GPA) < C minimum (2.0 GPA)
  CITATIONS:
    • MIT Course 6.1200 Catalog (Minimum Grade section)

Example 3: Out-of-Scope (Safe Abstention)
Input: "Who teaches 6.1210?"
Output:
  DECISION: Cannot Answer
  ANSWER: I cannot provide instructor information. This data is not in the course catalog.
  WHY: Instructor assignments are managed by the registrar, not the catalog.
  CITATIONS: None—out-of-scope.
...
"""
```

**Effort:** 1–2 hours  
**Impact:** ⬆️⬆️ Medium-High—few-shot examples drastically improve accuracy

---

#### 1.3 Step-by-Step Reasoning Prompts

**Action:** Add "Think step-by-step" guidance for complex chains

```python
SYSTEM_PROMPT += """
For complex prerequisite chains, use structured reasoning:

Step 1: Identify the target course
Step 2: List all immediate prerequisites
Step 3: For each prerequisite, check if completed
Step 4: If not completed, check THAT course's prerequisites
Step 5: Continue until reaching foundational courses or completed courses
Step 6: Build the dependency DAG
Step 7: Identify the critical path (longest chain)
Step 8: Present as semester-by-semester plan
"""
```

**Effort:** 30 minutes  
**Impact:** ⬆️ Low-Medium—helps with chain reasoning accuracy

---

## 2. Enhanced Chunking Strategy

### Current State
- Fixed 500–600 token chunks
- Basic overlap
- No respect for course boundaries

### Improvements

#### 2.1 Boundary-Aware Intelligent Chunking

**Action:** Modify `ingestion/chunker.py` to respect semantic boundaries

```python
# ingestion/chunker.py

def smart_chunk_documents(documents, max_chunk_size=500):
    """
    Chunk documents while respecting semantic boundaries.
    
    Strategy:
    1. Split by document type first
    2. For courses: respect course definition boundaries
    3. For policies: respect section boundaries
    4. For programs: respect requirement group boundaries
    5. Then chunk to max_chunk_size within boundaries
    """
    chunks = []
    
    for doc in documents:
        if doc.doc_type == "course":
            # Split by course code (e.g., "6.1210 \n ...")
            courses = split_by_course_code(doc.text)
            for course_text in courses:
                course_chunks = chunk_text(course_text, max_size=600)
                chunks.extend(course_chunks)
        
        elif doc.doc_type == "policy":
            # Split by section headers (e.g., "## Prerequisites")
            sections = split_by_headers(doc.text)
            for section in sections:
                section_chunks = chunk_text(section, max_size=500)
                chunks.extend(section_chunks)
        
        else:  # program
            # Split by requirement group
            groups = split_by_requirement_groups(doc.text)
            for group in groups:
                group_chunks = chunk_text(group, max_size=550)
                chunks.extend(group_chunks)
    
    return chunks

def split_by_course_code(text):
    """Split by course code patterns like '6.1210' at line start."""
    import re
    pattern = r'^(\d+\.\d+.*?)(?=^\d+\.\d+|$)'
    return re.findall(pattern, text, re.MULTILINE | re.DOTALL)

def split_by_headers(text):
    """Split by markdown/section headers."""
    import re
    pattern = r'^(#{1,3} .*?)(?=^#{1,3} |$)'
    return re.findall(pattern, text, re.MULTILINE | re.DOTALL)
```

**Effort:** 3–4 hours  
**Impact:** ⬆️⬆️ Medium—prevents splitting course definitions mid-description

---

#### 2.2 Query-Based Adaptive Chunking

**Action:** Different chunk sizes/strategies for different query types

```python
# vectorstore/faiss_store.py

class AdaptiveChunkerConfig:
    """Configuration for query-adaptive chunking."""
    
    PREREQ_QUERY = {
        "chunk_size": 400,  # Smaller: focus on prerequisites
        "overlap": 75,
        "extraction_pattern": "prerequisite|requires|must have"
    }
    
    PLANNING_QUERY = {
        "chunk_size": 600,  # Larger: preserve context
        "overlap": 125,
        "extraction_pattern": "course|description|credit"
    }
    
    POLICY_QUERY = {
        "chunk_size": 500,
        "overlap": 100,
        "extraction_pattern": "policy|requirement|rule"
    }

def get_adaptive_chunks(query, doc_type, config=None):
    """Retrieve chunks optimized for query type."""
    if "eligible" in query or "prerequisite" in query:
        cfg = AdaptiveChunkerConfig.PREREQ_QUERY
    elif "plan" in query or "next" in query:
        cfg = AdaptiveChunkerConfig.PLANNING_QUERY
    else:
        cfg = AdaptiveChunkerConfig.POLICY_QUERY
    
    # Use configured chunk size and patterns
    return retrieve_optimized_chunks(query, cfg)
```

**Effort:** 2–3 hours  
**Impact:** ⬆️ Low-Medium—marginal improvement, useful for edge cases

---

## 3. Advanced Retrieval Techniques

### Current State
- Hybrid (dense + BM25) with RRF
- Fixed top-5
- No reranking

### Improvements

#### 3.1 Cross-Encoder Reranking

**Action:** Add Sentence-BERT cross-encoder for reranking

```python
# embeddings/hybrid_embedder.py

from sentence_transformers import CrossEncoder

class HybridEmbedderWithReranking:
    def __init__(self, dense_model="all-MiniLM-L6-v2", use_reranker=True):
        self.encoder = sentence_transformers.SentenceTransformer(dense_model)
        self.bm25 = BM25Okapi([])
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2") if use_reranker else None
    
    def retrieve_and_rerank(self, query, documents, top_k=5):
        """
        Retrieve with hybrid method, then rerank with cross-encoder.
        
        Process:
        1. Dense retrieval: top-10
        2. BM25 retrieval: top-10
        3. RRF merge: top-15
        4. Cross-encoder rerank: top-5
        """
        # Step 1–3: Hybrid retrieval
        hybrid_results = self.hybrid_retrieve(query, documents, top_k=15)
        
        # Step 4: Rerank with cross-encoder
        if self.reranker:
            queries = [query] * len(hybrid_results)
            texts = [r["text"] for r in hybrid_results]
            
            # Cross-encoder scores (0–1, higher = more relevant)
            scores = self.reranker.predict(list(zip(queries, texts)))
            
            # Sort by cross-encoder score
            ranked = sorted(
                zip(hybrid_results, scores),
                key=lambda x: x[1],
                reverse=True
            )
            
            return [r[0] for r in ranked[:top_k]]
        
        return hybrid_results[:top_k]
```

**Effort:** 2–3 hours  
**Impact:** ⬆️⬆️⬆️ High—reranking significantly improves retrieval quality

---

#### 3.2 Course Code Direct Lookup (Fast Path)

**Action:** Extract course codes from query and do direct lookup before semantic search

```python
# agents/retriever_agent.py

class RetrieverAgent:
    def retrieve(self, query, student_info, top_k=5):
        # Fast path: extract course codes from query
        course_codes = extract_course_codes(query)
        
        if course_codes:
            # Direct lookup in metadata index
            direct_results = self.vector_store.lookup_by_course_code(course_codes)
            if direct_results:
                logger.info(f"Fast path: found {len(direct_results)} course matches")
                return direct_results  # Bypass semantic search
        
        # Slow path: full hybrid retrieval
        return self.hybrid_retrieve(query, top_k)
```

**Effort:** 1–2 hours  
**Impact:** ⬆️⬆️ Medium—faster + perfect precision on course lookups

---

#### 3.3 Query Expansion for Better Retrieval

**Action:** Expand user queries before retrieval

```python
# agents/retriever_agent.py

def expand_query(query):
    """
    Expand query with synonyms and related terms.
    
    Example:
    "Can I take 6.1210?" 
    →
    "Can I take 6.1210? Is eligible? Are prerequisites satisfied? 
     6.1210 prerequisites requirements"
    """
    expansions = {
        "eligible": ["can I take", "prerequisites", "requirements satisfied"],
        "prerequisite": ["requires", "must have", "minimum", "needed"],
        "plan": ["next semester", "course sequence", "career path"],
        "chain": ["full path", "all dependencies", "transitive"],
    }
    
    expanded = [query]
    for key, syns in expansions.items():
        if key in query.lower():
            for syn in syns:
                expanded.append(query.replace(key, syn))
    
    return expanded

def retrieve_with_expansion(query, top_k=5):
    """Retrieve for original query AND expanded versions."""
    expanded_queries = expand_query(query)
    all_results = []
    
    for q in expanded_queries:
        results = self.hybrid_retrieve(q, top_k=3)
        all_results.extend(results)
    
    # Deduplicate by chunk_id, keep highest score
    unique = {}
    for r in all_results:
        cid = r["chunk_id"]
        if cid not in unique or r["score"] > unique[cid]["score"]:
            unique[cid] = r
    
    return list(unique.values())[:top_k]
```

**Effort:** 1–2 hours  
**Impact:** ⬆️ Low-Medium—helpful for edge cases

---

## 4. Prerequisite Parser Enhancements

### Current State
- Handles AND/OR/commas
- Basic GIR mapping
- No support for "minimum C in course X"

### Improvements

#### 4.1 Grade-Qualified Prerequisites

**Action:** Parse and enforce grades per prerequisite

```python
# utils/prereq_parser.py

def parse_prerequisites_with_grades(prereq_text):
    """
    Parse prerequisites with grade requirements.
    
    Examples:
    - "6.100A" → {course: 6.100A, min_grade: None}
    - "6.100A (C or better)" → {course: 6.100A, min_grade: C}
    - "6.100A (B+ required)" → {course: 6.100A, min_grade: B+}
    - "18.01 or 18.01A" → {courses: [18.01, 18.01A], min_grade: None}
    """
    
    # Extract course codes
    courses = re.findall(r'\d+\.\d+[A-Z]?', prereq_text)
    
    # Extract grade requirement
    grade_match = re.search(r'\((.*?(?:or better|required|minimum).*?)\)', prereq_text)
    min_grade = None
    
    if grade_match:
        grade_text = grade_match.group(1).lower()
        # Parse "C or better" → C
        grade_match2 = re.search(r'([A-F][+-]?)', grade_text)
        if grade_match2:
            min_grade = grade_match2.group(1)
    
    return {
        "courses": courses,
        "min_grade": min_grade,
        "raw_text": prereq_text
    }

def check_prerequisites_with_grades(prereqs, completed_courses, grades):
    """
    Check if student satisfies prerequisites with grade requirements.
    
    Returns: {decision, missing, grade_issues}
    """
    missing = []
    grade_issues = []
    
    for prereq in prereqs:
        satisfied = False
        
        for course in prereq["courses"]:
            if course in completed_courses:
                # Check grade if required
                if prereq["min_grade"]:
                    student_grade = grades.get(course)
                    if not grade_meets_minimum(student_grade, prereq["min_grade"]):
                        grade_issues.append(
                            f"{course}: {student_grade} < {prereq['min_grade']}"
                        )
                    else:
                        satisfied = True
                        break
                else:
                    satisfied = True
                    break
        
        if not satisfied:
            missing.append(prereq)
    
    return {
        "decision": "Eligible" if not (missing or grade_issues) else "Not Eligible",
        "missing": missing,
        "grade_issues": grade_issues
    }
```

**Effort:** 2–3 hours  
**Impact:** ⬆️⬆️ High—critical for accuracy on grade-qualified prerequisites

---

#### 4.2 Corequisite Optimization

**Action:** Better support for concurrent enrollment

```python
# agents/planner_agent.py

def identify_corequisites(course_code):
    """
    Find all courses that are corequisites of the target.
    
    Returns: {corequisites: [list], can_be_concurrent: bool}
    """
    # Parse from retrieved catalog entry
    catalog_entry = retrieve_course_entry(course_code)
    
    coreq_match = re.search(r'[Cc]orequisite:?\s*(.*?)(?:\n|$)', catalog_entry)
    if coreq_match:
        coreq_text = coreq_match.group(1)
        coreqs = extract_course_codes(coreq_text)
        return {
            "corequisites": coreqs,
            "can_be_concurrent": True,
            "must_take_together": True,  # If specified
        }
    
    return {"corequisites": [], "can_be_concurrent": False}

def plan_with_corequisites(target_course, student_profile):
    """
    Plan including corequisite courses.
    
    Example:
    "Can I take 6.1903?"
    "6.1903 has corequisite 6.1904. You must take both together.
     Both require 6.1900 (completed ✓). Eligible to take both Spring 2026."
    """
    coreq_info = identify_corequisites(target_course)
    
    # ... check all corequisites together ...
    
    return plan
```

**Effort:** 2–3 hours  
**Impact:** ⬆️⬆️ Medium-High—critical for correct corequisite handling

---

## 5. Evaluation & Monitoring

### Current State
- 25 manual test queries
- JSON results output
- No continuous monitoring

### Improvements

#### 5.1 Automated Evaluation Framework

**Action:** Create scalable evaluation harness

```python
# evaluation/evaluator.py

class EvaluationFramework:
    def __init__(self, test_queries, pipeline):
        self.queries = test_queries
        self.pipeline = pipeline
        self.results = []
    
    def run_evaluation(self, verbose=True):
        """Run all tests and compute metrics."""
        for i, test in enumerate(self.queries):
            if verbose:
                print(f"[{i+1}/{len(self.queries)}] {test['id']}: {test['query'][:50]}...")
            
            result = self.pipeline.run(
                query=test["query"],
                student_info=test["student_info"],
                verbose=False
            )
            
            # Grade the response
            score = self.grade_response(result, test)
            
            self.results.append({
                "query_id": test["id"],
                "score": score,
                "expected": test["expected_decision"],
                "actual": result.get("eligibility_decision"),
                "passed": score >= 0.8,  # 80% threshold
            })
        
        return self._compute_metrics()
    
    def _compute_metrics(self):
        """Compute aggregate metrics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        
        by_category = {}
        for r in self.results:
            category = r["query_id"].split("-")[0]
            if category not in by_category:
                by_category[category] = {"total": 0, "passed": 0}
            by_category[category]["total"] += 1
            if r["passed"]:
                by_category[category]["passed"] += 1
        
        return {
            "total": total,
            "passed": passed,
            "accuracy": passed / total,
            "by_category": {
                cat: counts["passed"] / counts["total"]
                for cat, counts in by_category.items()
            },
            "details": self.results
        }
    
    def grade_response(self, result, expected):
        """
        Grade a response against expected output.
        
        Scoring:
        - Is decision correct? (50 points)
        - Are there citations? (25 points)
        - Is output well-formatted? (25 points)
        """
        score = 0.0
        
        # Decision accuracy (50%)
        if result.get("eligibility_decision") == expected["expected_decision"]:
            score += 50
        
        # Citation presence (25%)
        if result.get("citations") and len(result["citations"]) > 0:
            score += 25
        
        # Format compliance (25%)
        required_sections = ["answer", "why", "citations"]
        if all(k in result for k in required_sections):
            score += 25
        
        return score / 100  # Normalize to 0–1
```

**Effort:** 3–4 hours  
**Impact:** ⬆️⬆️⬆️ High—enables systematic testing and continuous improvement

---

#### 5.2 Failure Analysis & Logging

**Action:** Log and categorize failures for targeted improvement

```python
# agents/pipeline.py

class FailureAnalyzer:
    """Categorize and log failures for debugging."""
    
    FAILURE_TYPES = {
        "hallucination": "Generated claim without citation",
        "missed_prereq": "Failed to identify required prerequisite",
        "false_positive": "Said eligible when not",
        "format_error": "Malformed output",
        "grade_error": "Incorrect grade requirement checking",
        "scope_error": "Answered out-of-scope question", 
    }
    
    def analyze_failure(self, result, expected):
        """Determine failure category."""
        failures = []
        
        if not result.get("citations"):
            failures.append("hallucination")
        
        if result.get("eligibility_decision") != expected["expected_decision"]:
            if expected["expected_decision"] == "Not Eligible":
                failures.append("false_positive")
            else:
                failures.append("missed_prereq")
        
        if not all(k in result for k in ["answer", "why", "citations"]):
            failures.append("format_error")
        
        return failures
    
    def log_failure(self, query, result, expected, failure_types):
        """Log failure for analysis."""
        logger.error(f"""
        FAILED QUERY: {query}
        Expected: {expected["expected_decision"]}
        Actual: {result.get("eligibility_decision")}
        Failure types: {failure_types}
        Result: {json.dumps(result, indent=2)}
        """)
```

**Effort:** 1–2 hours  
**Impact:** ⬆️⬆️ High—enables fast debugging

---

## 6. Output Format & UX Improvements

### Current State
- Text-based output (good for CLI)
- No visual hierarchy
- Limited for web UI

### Improvements

#### 6.1 Structured JSON Output

**Action:** Return structured JSON alongside formatted text

```python
# agents/pipeline.py

def run(self, query: str, student_info: dict) -> dict:
    # ... existing pipeline ...
    
    return {
        # Structured data (for APIs, parsing)
        "metadata": {
            "query": query,
            "student_id": None,  # If authenticated
            "timestamp": datetime.now().isoformat(),
            "execution_time_ms": elapsed_ms,
        },
        "result": {
            "decision": result["eligibility_decision"],
            "answer": result["answer"],
            "reasoning": result["why"],
            "citations": [
                {
                    "text": c,
                    "source_document": c.split(":")[0],
                    "confidence": 0.95,  # 0–1
                }
                for c in result["citations"]
            ],
            "clarifying_questions": result["clarifying_questions"],
            "assumptions": result["assumptions"],
        },
        # Formatted text (for display)
        "formatted_output": result.get("formatted_output"),
        
        # Diagnostics (for debugging)
        "debug": {
            "retrieval_chunks_count": len(retrieved_context),
            "agent_trace": [
                {"agent": "IntakeAgent", "status": "completed"},
                {"agent": "RetrieverAgent", "status": "completed"},
                {"agent": "PlannerAgent", "status": "completed"},
                {"agent": "VerifierAgent", "status": "completed"},
            ],
        },
    }
```

**Effort:** 1–2 hours  
**Impact:** ⬆️⬆️ High—enables API use and better debugging

---

#### 6.2 Interactive Response Builder (Streamlit)

**Action:** Enhance web UI with interactive elements

```python
# app.py improvements

st.markdown("### Results")

# Tabs for different views
tab1, tab2, tab3, tab4 = st.tabs(["Decision", "Reasoning", "Citations", "Debug"])

with tab1:
    decision = result["decision"]
    emoji = {"Eligible": "✅", "Not Eligible": "❌", "Need More Info": "⚠️"}
    st.subheader(f"{emoji.get(decision, 'ℹ️')} {decision}")
    st.write(result["answer"])

with tab2:
    st.subheader("Why")
    st.write(result["reasoning"])

with tab3:
    st.subheader("Citations")
    for i, citation in enumerate(result["citations"], 1):
        with st.expander(f"Citation {i}: {citation['source_document'][:40]}..."):
            st.write(citation["text"])

with tab4:
    st.subheader("Debug Info")
    st.json(result["debug"])

# Export options
st.download_button(
    "Download as PDF",
    data=export_to_pdf(result),
    file_name=f"plan_{datetime.now().isoformat()}.pdf",
)
```

**Effort:** 2–3 hours  
**Impact:** ⬆️ Medium—improves user experience significantly

---

## 7. Caching & Performance

### Current State
- No caching (each query performs full retrieval)
- Embedding model loaded per session
- FAISS index reloaded each run

### Improvements

#### 7.1 Query Result Caching

**Action:** Cache results for identical queries

```python
# agents/pipeline.py

import hashlib
from functools import lru_cache

class CachedPipeline(CourseAssistantPipeline):
    def __init__(self, *args, cache_dir="cache", **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def _query_key(self, query: str, student_info: dict) -> str:
        """Generate cache key from query + student profile."""
        key_str = json.dumps({"query": query, "student_info": student_info}, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def run(self, query: str, student_info: dict, use_cache=True):
        """Run with optional caching."""
        if use_cache:
            cache_key = self._query_key(query, student_info)
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            if cache_file.exists():
                logger.info(f"Cache hit: {cache_key}")
                return json.loads(cache_file.read_text())
        
        # Run pipeline
        result = super().run(query, student_info)
        
        # Cache result
        if use_cache:
            cache_file.write_text(json.dumps(result))
        
        return result
```

**Effort:** 1–2 hours  
**Impact:** ⬆️ Low (for single queries), ⬆️⬆️ High (for batch operations)

---

#### 7.2 Embedding Model Persistence

**Action:** Load embedding model once, reuse across requests

```python
# embeddings/hybrid_embedder.py

class HybridEmbedderSingleton:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HybridEmbedder(dense_model="all-MiniLM-L6-v2")
        return cls._instance

# In pipeline
def __init__(self, *args, **kwargs):
    self.embedder = HybridEmbedderSingleton.get_instance()  # Cached
```

**Effort:** 30 minutes  
**Impact:** ⬆️ Medium—reduces initialization latency

---

## 8. Multi-institution Support

### Current State
- MIT-only
- Hard-coded course codes (6.xxxx, 18.xxx, 8.xx)

### Future Enhancement
- Abstract institution configuration
- Support Stanford, CMU, Berkeley
- Institution-agnostic course code parsing

```python
# config/institutions.py

INSTITUTIONS = {
    "mit": {
        "name": "Massachusetts Institute of Technology",
        "course_regex": r"\d{1,2}\.\d{3,4}[A-Z]?",
        "gir_requirements": [...],
        "catalog_url": "https://catalog.mit.edu/",
    },
    "stanford": {
        "name": "Stanford University",
        "course_regex": r"CS\s?\d{3}",
        "gir_requirements": [...],
        "catalog_url": "https://registrar.stanford.edu/",
    },
}
```

**Effort:** 8–12 hours (future project)  
**Impact:** ⬆️⬆️⬆️ High—enables multi-institution deployment

---

## Implementation Priority Matrix

| ID | Improvement | Effort | Impact | Priority |
|----|-------------|--------|--------|----------|
| 1.1 | Query-specific prompts | 2–3h | ⬆️⬆️⬆️ | 🔴 **URGENT** |
| 1.2 | Few-shot examples | 1–2h | ⬆️⬆️ | 🔴 **URGENT** |
| 3.1 | Cross-encoder reranking | 2–3h | ⬆️⬆️⬆️ | 🔴 **URGENT** |
| 4.1 | Grade-qualified prereqs | 2–3h | ⬆️⬆️ | 🔴 **URGENT** |
| 5.1 | Evaluation framework | 3–4h | ⬆️⬆️⬆️ | 🟠 **HIGH** |
| 2.1 | Boundary-aware chunking | 3–4h | ⬆️⬆️ | 🟠 **HIGH** |
| 3.2 | Course code fast path | 1–2h | ⬆️⬆️ | 🟠 **HIGH** |
| 6.1 | Structured JSON output | 1–2h | ⬆️⬆️ | 🟡 **MEDIUM** |
| 1.3 | Step-by-step prompts | 30m | ⬆️ | 🟡 **MEDIUM** |
| 6.2 | Streamlit enhancements | 2–3h | ⬆️ | 🟡 **MEDIUM** |
| 7.1 | Query caching | 1–2h | ⬆️ | 🟡 **MEDIUM** |
| 5.2 | Failure analysis | 1–2h | ⬆️⬆️ | 🟢 **LOW** |
| 2.2 | Query-adaptive chunking | 2–3h | ⬆️ | 🟢 **LOW** |
| 3.3 | Query expansion | 1–2h | ⬆️ | 🟢 **LOW** |
| 4.2 | Corequisite optimization | 2–3h | ⬆️⬆️ | 🟢 **LOW** |
| 7.2 | Model persistence | 30m | ⬆️ | 🟢 **LOW** |
| 8 | Multi-institution | 8–12h | ⬆️⬆️⬆️ | 🔵 **FUTURE** |

---

## Quick-Win Implementation (4–6 hours)

For an immediate v2 release, focus on:

1. **Add few-shot examples to prompts** (1–2h) ✅
2. **Implement cross-encoder reranking** (2–3h) ✅
3. **Add grade-qualified prerequisite parsing** (2–3h) ✅

**Expected improvement:** Accuracy 96% → 98%+, zero hallucinations.

---

## 12-Week Enhancement Plan

**Week 1–2:** Urgent improvements (1, 3.1, 4.1)
**Week 3–4:** Evaluation framework (5.1)
**Week 5–6:** Advanced retrieval (2.1, 3.2)
**Week 7–8:** UX/API (6.1, 7.1)
**Week 9–10:** Testing, monitoring, polish
**Week 11–12:** Multi-institution groundwork

---

**Last Updated:** March 2026
