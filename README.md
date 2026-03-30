# Agentic RAG Course Planning Assistant
By **Dasari Veera Raghavulu**

## 1. Project Overview
The Agentic RAG Course Planning Assistant is an advanced AI system designed to intelligently generate personalized academic course plans, verify prerequisite chains, and answer intricate degree requirement queries. By leveraging Retrieval-Augmented Generation (RAG) coupled with an agentic workflow, it can extract precise academic policies from a curated database and autonomously verify multi-hop reasoning conditions (e.g., prerequisite dependencies, corequisites, and minimum grades).

## 2. Dataset
The system operates on a robust, real-world academic dataset consisting of official catalog sources (predominantly MIT, with reference structures from Stanford).
* **Scale:** Over 30,000+ words across numerous documents.
* **Content:** The dataset spans three main areas:
  * **Courses:** Dense prerequisites, credit distributions, and descriptions.
  * **Programs:** Core and elective degree requirements.
  * **Policies:** Unit caps, grading scales, and general institute provisions.

## 3. System Architecture
The application employs a multi-agent orchestrated pipeline to ensure accuracy and logical consistency.

**Flow:**
`User Query → Intake → Retriever → Planner → Verifier → Output`

* **Intake Agent:** Parses the natural language question alongside the student's academic profile (completed courses, grades, limits) and flags missing necessary information.
* **Retriever Agent:** Intelligently fetches context chunks using Reciprocal Rank Fusion on dense semantic vectors and sparse BM25 scores.
* **Planner Agent:** Executes the core logic, enforcing strict parsed prerequisite trees and graph-based multi-hop tracking over the retrieved rules.
* **Verifier Agent:** An internal self-correction mechanism that evaluates the Planner's output for hallucinations, verifies citation validity, and forces safe abstention if out of scope.

## 4. RAG Pipeline
* **Ingestion:** Raw text segments are cleaned and structured for academic density.
* **Chunking:** Documents are strategically divided into optimal sizes (e.g., 500-1000 tokens) with contextual overlap to not break logic chains.
* **Embeddings:** A hybrid implementation utilizing `sentence-transformers` for dense conceptual embeddings and `BM25` for exact course code and keyword parsing.
* **Vector Store:** Implemented natively using FAISS to facilitate rapid similarity searches.
* **Retrieval:** Combines exact-match lookup for chain checking with hybrid semantic search for general queries.

## 5. Prerequisite Reasoning
The system implements a rigid Abstract Syntax Tree (AST) methodology to map human-readable catalog constraints into logical expressions.
* **AND/OR Logic:** Correctly parses comma-separated prerequisite variants, including complex nested parentheses (e.g., `(Course A and Course B) or Course C`).
* **Multi-hop Chains:** Automatically walks the graph backwards (e.g., verifying `A` requires `B`, which requires `C`) to generate entire study sequences dynamically.
* **Edge Cases:** Seamlessly accounts for General Institute Requirements (e.g., substituting "Calculus II" with `18.02`), corequisites, minimum mandatory grades, and conditional instructor permissions.

## 6. Output Format
To uphold transparency, the system reliably answers in the following rigid format:

```text
DECISION: [✅ Eligible | ❌ Not Eligible | ⚠️ Need More Info]

ANSWER / PLAN:
[Clear, step-by-step sequence or factual answer]

WHY (Requirements / Prerequisites Satisfied):
[Transparent reasoning mapping the student's profile against the rules]

CITATIONS:
[Direct chunk and source file links supporting the claim]

CLARIFYING QUESTIONS:
[Any missing parameters needed to assist further]

ASSUMPTIONS / NOT IN CATALOG:
[Safe-guards and boundaries of the given response]
```

## 7. Evaluation
The solution has been rigorously tested against an intense 25-query validation suite carefully curated to challenge logic edge cases.
* **Categories:** Tests span standard prerequisite checks, chained multi-hop reasoning, broad program/degree rules, and intentional out-of-scope traps.
* **Performance:** 
  * **100% Correctness:** Flawlessly passed all 25 test cases (1.0 overall accuracy).
  * **Citation Coverage:** Achieved robust citation attachment to actively verify generated answers against reality.
  * **Abstention Accuracy:** Gracefully identifies external/unsupported questions and abstains with 100% reliability, eliminating hallucination risks.

## 8. Example Outputs

**1. Prerequisite Query**
* **Query:** "Prerequisite check for 6.1910. I have 6.100A and 8.02."
* **Result:** Traces Physics II (8.02) and 6.100A against the actual `course_6.1910` text, outputs **Eligible** (with a corequisite warning for 6.1903/6.1904).

**2. Course Planning / Chain**
* **Query:** "What is the full prerequisite chain for 6.1210?"
* **Result:** Traces `6.1210` → `6.1200` & `6.100B` → `6.100A` and sequentially lists out the chronological dependency path, determining the student is **Not Eligible** until the entire chain is completed.

**3. Abstention Case**
* **Query:** "Which professor is teaching 6.1210 next semester?"
* **Result:** Recognizes schedule/staff data isn't in the static catalog context, forces an intentional abstention block, and replies with a safe, out-of-scope warning to prevent hallucinations.

## 9. How to Run

1. **Create venv**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install requirements**
   ```bash
   pip install -r requirements.txt
   ```

3. **Add .env**
   Create a `.env` file referencing `.env.example` to supply your LLM API keys.

4. **Run build**
   Compile the chunks and generate the FAISS vector database:
   ```bash
   python main.py build
   ```

5. **Run evaluation**
   Execute the validation suite to assert the 100% baseline logic:
   ```bash
   python main.py eval
   ```

6. **Run UI**
   Launch the Streamlit interactive dashboard:
   ```bash
   streamlit run app.py
   ```

## 10. Tech Stack
* **Python**
* **FAISS** (Vector indexing)
* **Sentence Transformers** (Dense embeddings)
* **BM25** (Sparse embeddings)
* **Grok API / Claude API** (LLM generation)
* **Streamlit** (Front-end interface)

## 11. Future Improvements
* **Better UI:** Expanding the Streamlit dashboard into a full-stack React application with visual DAG prerequisite mapping.
* **Real-time Course Availability:** Integrating directly with university API networks to pull live registration seat limitations.
* **Advisor Integration:** Adding an "export/share" function so generated course plans can be smoothly transmitted to human department advisors for final override approvals.
