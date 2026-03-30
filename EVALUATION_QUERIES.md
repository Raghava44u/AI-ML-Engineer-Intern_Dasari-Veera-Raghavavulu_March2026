# Agentic RAG Course Planner — 25 Evaluation Queries

**Purpose:** Comprehensive test suite covering prerequisite verification, multi-hop reasoning, program rules, and safe abstention.

**Total Queries:** 25  
**Categories:**
- **PR (Prerequisite Checks):** 10 queries
- **CH (Multi-hop Chains):** 5 queries
- **PG (Program Rules):** 5 queries
- **OOS (Out-of-Scope):** 5 queries

---

## Category A: Prerequisite Checks (10)

These test the system's ability to verify single-course eligibility given a student profile.

### PR-01: Single Course, Missing Prerequisite

**Query:** "Can I take 6.1210 if I completed 6.100A?"

**Student Profile:**
- Completed courses: 6.100A
- Target program: MIT Course 6-3 (EECS)
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ❌ **Not Eligible**

**Why:** 6.1210 requires 6.1200 and 6.100A. While 6.100A is satisfied, 6.1200 is missing.

**Expected Citations:**
- MIT Course 6.1210 Catalog (Prerequisite section)
- MIT Course 6.1200 Catalog

**Key Behaviors to Test:**
- Identifies all prerequisites, not just one
- Distinguishes between satisfied and missing requirements
- Provides clear missing reasons

---

### PR-02: Simple Multi-prerequisite (Eligible)

**Query:** "Am I eligible for 6.1020 if I've completed 6.1010?"

**Student Profile:**
- Completed courses: 6.1010, 6.1210, 6.1200, 6.100A
- Grades: 6.1010: B
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 6.1020 requires 6.1010 (completed with B grade). No minimum grade restriction stated.

**Expected Citations:**
- MIT Course 6.1020 Catalog (Prerequisite section)

**Key Behaviors to Test:**
- Recognizes sufficient prerequisites
- Handles grade requirements (if any)
- Confirms eligibility clearly

---

### PR-03: AND/OR Logic (Elective with Options)

**Query:** "Can I enroll in 6.1220[J] if I have 6.1210 and 6.1200?"

**Student Profile:**
- Completed courses: 6.1210, 6.1200, 18.01
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 6.1220[J] (advanced variant) requires 6.1210 OR 6.1200. Both are completed, so eligibility clear.

**Expected Citations:**
- MIT Course 6.1220[J] Catalog

**Key Behaviors to Test:**
- Handles multi-option prerequisites (comma-or logic)
- Doesn't over-require (both not needed if only one requested)
- Clearly states which options were satisfied

---

### PR-04: Math Prerequisite (GIR Mapping)

**Query:** "Check eligibility for 6.1200[J]. I have 18.01."

**Student Profile:**
- Completed courses: 18.01
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 6.1200[J] requires calculus foundation. 18.01 (Calculus I, GIR mapping) satisfies this.

**Expected Citations:**
- MIT Course 6.1200[J] Catalog
- MIT GIR Requirements (Calculus mapping)

**Key Behaviors to Test:**
- Maps GIR course names to course codes
- Recognizes cross-program course requirements
- Handles math prerequisites

---

### PR-05: Sequential Math Requirement

**Query:** "Can I take 18.02 after finishing 18.01?"

**Student Profile:**
- Completed courses: 18.01
- Target program: MIT Course 18 (Math)
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 18.02 (Multivariable Calculus) standard prerequisite is 18.01 (Single-variable Calculus).

**Expected Citations:**
- MIT Course 18.02 Catalog (Prerequisite section)

**Key Behaviors to Test:**
- Standard prerequisite chains (common knowledge)
- Clear progression reasoning
- Cross-major course prerequisites

---

### PR-06: No Prerequisites Met (Blank Slate)

**Query:** "Am I ready for 6.1010 with no CS classes completed yet?"

**Student Profile:**
- Completed courses: [] (empty)
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ❌ **Not Eligible**

**Why:** 6.1010 (Intro to CS) requires 6.100A. Student has no prerequisites.

**Expected Citations:**
- MIT Course 6.1010 Catalog

**Key Behaviors to Test:**
- Handles empty completed_courses list
- Doesn't make assumptions about "should be eligible"
- Clear explanation of what's needed

---

### PR-07: Complex Multi-course Prerequisite (Eligible)

**Query:** "Can I take 6.1800 with 6.1910, 6.1210, and 6.1020?"

**Student Profile:**
- Completed courses: 6.1910, 6.1210, 6.1020, 6.100A, 6.1200
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 6.1800 (Advanced Systems) requires: 6.1910, 6.1210, 6.1020. All completed.

**Expected Citations:**
- MIT Course 6.1800 Catalog

**Key Behaviors to Test:**
- Handles multiple required prerequisites
- Explicitly lists all requirements met
- No false positives

---

### PR-08: Linear Algebra Requirement

**Query:** "Is 18.06 accessible if I have 18.02?"

**Student Profile:**
- Completed courses: 18.02
- Target program: MIT Course 18
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 18.06 (Linear Algebra) prerequisite: 18.02 or 18.01A. 18.02 satisfies.

**Expected Citations:**
- MIT Course 18.06 Catalog

**Key Behaviors to Test:**
- Recognizes alternative prerequisites
- Math course sequencing
- Clear explanation of alternatives

---

### PR-09: Cross-Department Requirements (Physics + CS)

**Query:** "Can I take 6.3900 if I have 6.100A, 6.1210, and 18.06?"

**Student Profile:**
- Completed courses: 6.100A, 6.1210, 18.06, 18.02, 8.02
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 6.3900 (AI course) requires 6.100A, 6.1210, linear algebra (18.06). All satisfied.

**Expected Citations:**
- MIT Course 6.3900 Catalog
- MIT Course 6.1210, 18.06 Catalogs

**Key Behaviors to Test:**
- Multi-department prerequisites (CS + Math)
- Handles cross-program requirements
- Explicit checklist format

---

### PR-10: Physics + CS Prerequisite (Corequisite Note)

**Query:** "Prerequisite check for 6.1910. I have 6.100A and 8.02."

**Student Profile:**
- Completed courses: 6.100A, 8.02
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ✅ **Eligible**

**Why:** 6.1910 (Advanced Physics-CS) requires 6.100A and 8.02 (Physics II). Both completed. Note: 6.1903/6.1904 are corequisites (can be concurrent).

**Expected Citations:**
- MIT Course 6.1910 Catalog

**Key Behaviors to Test:**
- Identifies corequisites separately from prerequisites
- Flags concurrent needs
- Clear notifications about course variants

---

## Category B: Multi-hop Prerequisite Chains (5)

These test the system's ability to trace transitive prerequisites (A requires B, B requires C, C requires ...).

### CH-01: Simple Two-level Chain

**Query:** "What is the full prerequisite chain for 6.1210?"

**Student Profile:**
- Completed courses: [] (empty—testing from scratch)
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ❌ **Not Eligible** (from current state)

**Why:**
- 6.1210 requires: 6.1200 + 6.100A + 18.01
- 6.1200 requires: 18.01
- 6.100A requires: none (foundational)
- 18.01 requires: none (GIR)

**Expected Output:**
```
Chain: 6.1210
├── 6.1200 *
│   └── 18.01 (fulfilled by GIR)
├── 6.100A (no further prerequisites)
└── 18.01 (fulfilled by GIR)

Recommendation:
1. Complete 18.01 (Calculus I) — 12 units, GIR
2. Complete 6.100A (Intro CS) — 12 units
3. Complete 6.1200 (depends on 18.01) — 12 units
4. Then eligible for 6.1210 — 12 units

Estimated timeline: 4 semesters minimum
```

**Expected Citations:**
- MIT Course 6.1210 Catalog
- MIT Course 6.1200 Catalog
- MIT Course 6.100A Catalog
- MIT GIR Requirements

**Key Behaviors to Test:**
- Recursive prerequisite lookup
- Identifies independent paths (parallel enrollment)
- Suggests realistic ordering
- Handles GIR mappings at leaf level

---

### CH-02: Complex Four-level Chain

**Query:** "Trace complete path to 6.1800 from scratch."

**Student Profile:**
- Completed courses: [] (empty)
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ❌ **Not Eligible** (from current state)

**Why:**
- 6.1800 requires: 6.1910 + 6.1210 + 6.1020
- 6.1910 requires: 6.100A + 8.02
- 6.1210 requires: 6.1200 + 6.100A + 18.01
- 6.1020 requires: 6.1010
- 6.1010 requires: 6.100A + 18.01
- ... (continues recursively)

**Expected Output:** Detailed dependency DAG with minimum course count ~12–15 courses over 6–8 semesters.

**Key Behaviors to Test:**
- Handles deeply nested chains
- Identifies critical path (longest prerequisite chain)
- Suggests parallelization opportunities
- Realistic semester planning

---

### CH-03: Parallel Paths (Concurrent Enrollment Possible)

**Query:** "Can I complete enough prerequisites for 6.1020 by Fall if I start now?"

**Student Profile:**
- Completed courses: 6.100A, 18.01
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48
- Current term: Spring 2026

**Expected Decision:** ✅ **Need More Info** (or Yes, with planning)

**Why:**
- 6.1020 requires: 6.1010
- 6.1010 requires: 6.100A (completed) + 18.01 (completed)
- Can take 6.1010 next semester → eligible for 6.1020 by Fall

**Expected Output:**
```
Timeline:
- Spring 2026: Take 6.1010 (prerequisites satisfied)
- Fall 2026: Eligible for 6.1020

Feasibility: ✅ YES, achievable by target term
```

**Key Behaviors to Test:**
- Temporal reasoning (current term + future semesters)
- Parallel course possibility
- Realistic scheduling advice

---

### CH-04: Branching Prerequisites (Multiple Paths)

**Query:** "What are ALL prerequisites for 6.3900 (transitive closure)?"

**Student Profile:**
- Completed courses: [] (empty)
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ❌ **Not Eligible**

**Why:** 6.3900 has multi-branch prerequisites requiring 10+ foundational courses across CS, Math, Physics.

**Expected Output:** Full DAG with all nodes and edges, identifying:
- Longest critical path
- Total minimum courses required
- Parallelizable sections
- Estimated timeline

**Key Behaviors to Test:**
- Complex DAG handling
- Transitive closure (all dependencies, not just immediate)
- Visual/structural representation
- Critical path identification

---

### CH-05: Circular Dependency Detection (Edge Case)

**Query:** "Are there any circular prerequisites in the course catalog?"

**Student Profile:**
- Completed courses: [] (empty)
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 48

**Expected Decision:** ⚠️ **Out-of-Scope** or ℹ️ **Information**

**Why:** This queries system integrity, not student eligibility. Should abstain or provide info.

**Expected Output:**
```
I cannot verify system-wide catalog integrity from individual queries.
However, no circular dependencies were found in the data processed for this system.

Recommendation: Contact Registrar for official verification.
```

**Key Behaviors to Test:**
- Recognizes meta-questions (about system, not about student)
- Safe abstention on out-of-scope
- Honest boundary acknowledgment

---

## Category C: Program Rules & Degree Requirements (5)

These test the system's ability to handle degree requirements, program-level rules, and policies.

### PG-01: Program Requirement Satisfaction

**Query:** "Do I meet Course 6-3 (EECS) degree requirements with the following courses: 6.100A, 6.1200, 6.1210, 6.1020, 6.1800, 18.01, 18.02, 18.06?"

**Student Profile:**
- Completed courses: 6.100A, 6.1200, 6.1210, 6.1020, 6.1800, 18.01, 18.02, 18.06
- Target program: MIT Course 6-3 (EECS)
- Cumulative GPA: 3.5
- Credits earned: 96

**Expected Decision:** ⚠️ **Need More Info**

**Why:** Partial program evaluation. Need to know:
- Humanities electives (3 courses)
- Lab requirement fulfillment
- Thesis/capstone status
- Total unit count distribution

**Expected Output:**
```
Degree Requirements Check for MIT Course 6-3:

Core Requirements:
✅ Introductory CS (6.100A) - satisfied
✅ Circuits (6.1200) - satisfied
✅ Digital Systems (6.1210) - satisfied
✅ Data Structures (6.1020) - satisfied
✅ Advanced Systems (6.1800) - satisfied

Math Requirements:
✅ Calculus I (18.01) - satisfied
✅ Calculus II (18.02) - satisfied
✅ Linear Algebra (18.06) - satisfied

Outstanding:
❌ 3 Humanities/Social Science electives
❌ Lab requirement designation
❌ Thesis (if double-degree)

GPA: 3.5 (exceeds minimum 2.0) ✅

Recommendation: Complete humanities requirements + designate lab before graduation.
```

**Expected Citations:**
- MIT Course 6-3 Degree Requirements
- MIT Liberal Arts Requirement
- MIT Lab Requirement Policy

**Key Behaviors to Test:**
- Handles degree-level queries
- Distinguishes core vs. elective requirements
- Identifies missing components
- Transparent checklist format

---

### PG-02: Minimum GPA for Major Admission

**Query:** "What is the minimum GPA required to declare MIT Course 6-3?"

**Student Profile:**
- Completed courses: 6.100A, 6.1200
- Current GPA: 2.8
- Target program: MIT Course 6-3

**Expected Decision:** ℹ️ **Information Provided**

**Why:** This is a policy lookup, not a prerequisite check.

**Expected Output:**
```
MIT Course 6-3 (EECS) Major Declaration Requirements:

Minimum GPA: 2.0 (cumulative)
Your GPA: 2.8 ✅ EXCEEDS minimum

Required completed courses before declaration:
- 6.100A (intro CS) - satisfied ✅
- At least one 6.1000-level course - satisfied ✅

Status: ELIGIBLE to declare MIT Course 6-3

Next steps:
1. Contact Course 6 advisor
2. Submit declaration form
3. Register for next semester courses
```

**Expected Citations:**
- MIT Course 6 Major Requirements
- MIT Academic Policy Handbook

**Key Behaviors to Test:**
- Policy lookup (not prerequisite logic)
- Student profile interpretation
- Clear actionable next steps

---

### PG-03: Course Substitution Policy

**Query:** "Can I substitute 6.1210 with 6.1220 to satisfy degree requirements?"

**Student Profile:**
- Completed courses: 6.1220 (not 6.1210)
- Target program: MIT Course 6-3
- Target term: Fall 2026

**Expected Decision:** ⚠️ **Need More Info**

**Why:** Substitution requires advisor approval. Catalog may state policy, but individual exceptions need human review.

**Expected Output:**
```
Substitution Query: 6.1210 → 6.1220

Catalog Policy:
Course 6-3 requires 6.1210 (Digital Systems) as a CORE requirement.
Course 6.1220 (Advanced DS) is an ELECTIVE variant with higher prerequisites.

Substitution Possibility:
✓ 6.1220 is more advanced than 6.1210
⚠️ Substitution policy: ADVISOR APPROVAL REQUIRED

Next Steps:
1. Contact MIT Course 6 Advisor
2. Present rationale (e.g., taking advanced variant early)
3. Advisor may approve with conditions

This system cannot approve substitutions. Human review required.
```

**Expected Citations:**
- MIT Course 6 Major Requirements
- MIT Academic Substitution Policy

**Key Behaviors to Test:**
- Recognizes policy limits
- Acknowledges human approval gates
- Safe abstention on advisor-only decisions

---

### PG-04: General Institute Requirements (GIR) Fulfillment

**Query:** "What are the MIT General Institute Requirements (GIR)? How many courses are required?"

**Student Profile:**
- Completed courses: 18.01, 8.02, 5.111
- Target program: MIT Course 6-3
- Target term: Fall 2026

**Expected Decision:** ℹ️ **Information Provided**

**Why:** This is a policy/requirement lookup.

**Expected Output:**
```
MIT General Institute Requirements (GIR):

SCIENCE:
- Physics (8.01 or 8.02): ✅ 8.02 completed
- Physics II (8.02): ✅ completed
- Chemistry (5.111): ✅ completed
- Biology (7.015 or 7.016): ❌ NOT taken

MATHEMATICS:
- Calculus I (18.01): ✅ completed
- Calculus II (18.02) OR Discrete Math (6.042): ❌ NOT taken

HUMANITIES & SOCIAL SCIENCES:
- 3 courses from approved electives: ❌ NOT completed

YOUR GIR STATUS:
Completed: 3/9 core requirements
Outstanding: 6 more courses

Timeline to complete GIR: 2–3 semesters
```

**Expected Citations:**
- MIT GIR Requirements (official)
- Course equivalency table

**Key Behaviors to Test:**
- Handles system-wide policies (not major-specific)
- Tracks student progress toward requirements
- Clear mapping of completed to outstanding

---

### PG-05: Elective Count & Credit Requirements

**Query:** "How many electives must I take for MIT Course 6? What's the total unit requirement?"

**Student Profile:**
- Completed courses: 6.100A, 6.1200, 6.1210, 6.1020, 18.01, 18.02
- Credits earned so far: 72
- Target program: MIT Course 6-3

**Expected Decision:** ℹ️ **Information Provided**

**Why:** This is a degree requirement lookup.

**Expected Output:**
```
MIT Course 6-3 (EECS) Degree Requirements:

CORE COURSES (Required):
- Intro to CS (6.100A) — 12 units ✅
- Circuits (6.1200) — 12 units ✅
- Digital Systems (6.1210) — 12 units ✅
- Data Structures (6.1020) — 12 units ✅
- Advanced Systems (6.1800) — 12 units ❌

Core Subtotal: 48 units (4 of 5 completed)

ELECTIVES (Choose 3+ from list):
- Minimum: 3 electives = 36 units
- You have: 0 electives ❌

OTHER REQUIREMENTS:
- GIR completion: 36 units
- Humanities: 12 units

TOTAL DEGREE REQUIREMENT: 180 units
Your progress: 72/180 (40%)

Remaining needed: 108 units over ~3 semesters
```

**Expected Citations:**
- MIT Course 6-3 Handbook (official)

**Key Behaviors to Test:**
- Arithmetic on credit totals
- Degree planning math
- Clear unit breakdown

---

## Category D: Out-of-Scope Detection (5)

These test the system's ability to gracefully refuse queries outside the catalog's scope (staff, schedules, financial info, real-time data).

### OOS-01: Staff & Instructor Assignment

**Query:** "Who is teaching 6.1210 this semester? What are their office hours?"

**Student Profile:**
- Completed courses: 6.100A, 6.1200, 18.01
- Target program: MIT Course 6-3
- Target term: Fall 2026

**Expected Decision:** ⚠️ **Out-of-Scope / Not in Catalog**

**Expected Output:**
```
DECISION: ⚠️ Cannot Answer

ANSWER:
I cannot provide instructor information. This data is not in the course catalog.

WHY:
The course catalog contains:
✓ Course descriptions and prerequisites
✓ Credit values
✓ General policies

The course catalog does NOT contain:
✗ Instructor assignments (change semester-to-semester)
✗ Office hours (managed by department)
✗ Teaching format (in-person vs. online)

CITATIONS:
None—this query is out-of-scope.

NEXT STEPS:
For instructor & schedule info, visit:
  1. MIT Registrar (https://registrar.mit.edu)
  2. Course 6 Department Office
  3. Course website on Canvas/Stellar

ASSUMPTIONS:
This system operates on static catalog data only. For real-time scheduling and staffing, 
consult the registrar portal.
```

**Key Behaviors to Test:**
- Recognizes real-time data (staff, schedules) outside scope
- Provides helpful redirection
- Explicit boundary statement
- Zero hallucination on unknown data

---

### OOS-02: Class Schedule & Meeting Times

**Query:** "What time does 6.1210 meet on Tuesdays? Is it online or in-person?"

**Student Profile:**
- Completed courses: 6.100A, 6.1200, 18.01

**Expected Decision:** ⚠️ **Out-of-Scope**

**Expected Output:**
```
DECISION: ⚠️ Information Not in Catalog

ANSWER:
I cannot determine class schedules or meeting times. This information is managed 
by the MIT Registrar, not the static course catalog.

WHY:
Scheduling is semester-specific and managed dynamically:
✗ Meeting times change each semester
✗ Instructors and room assignments vary
✗ Format (in-person/hybrid/online) decided each year
✗ Conflicts and overlaps managed in real-time

The course catalog contains ONLY:
✓ Course descriptions
✓ Prerequisites and credits
✓ General policies (NOT schedules)

CITATIONS:
None—out-of-scope query.

HOW TO FIND SCHEDULES:
1. MIT Registrar (https://registrar.mit.edu/schedule)
2. Login to student portal
3. Search by course code: 6.1210
4. View available sections and times

ASSUMPTIONS:
This system cannot answer real-time queries. Schedule must come from official registrar.
```

**Key Behaviors to Test:**
- Recognizes schedule queries as out-of-scope
- Distinguishes "course" from "section" (one course, many sections)
- Helps student find correct resource
- Avoids guessing/hallucinating times

---

### OOS-03: Financial Information (Tuition, Aid, Cost)

**Query:** "How much does MIT tuition cost? What financial aid is available for MIT Course 6 students?"

**Student Profile:**
- Completed courses: 6.100A
- Target program: MIT Course 6-3

**Expected Decision:** ⚠️ **Out-of-Scope**

**Expected Output:**
```
DECISION: ⚠️ Cannot Answer

ANSWER:
Financial information is not in the course catalog. Contact MIT Financial Aid office.

WHY:
The course catalog covers:
✓ Academic requirements
✓ Course descriptions
✓ Degree policies

The course catalog does NOT cover:
✗ Tuition cost (administrative, not academic)
✗ Financial aid (student services, not catalog)
✗ Scholarships (admissions/finance, not catalog)
✗ Loan information (financial services, not catalog)

CITATIONS:
None—out-of-scope query.

CORRECT RESOURCES:
1. MIT Financial Aid (https://sfs.mit.edu)
2. Tuition information (https://sfs.mit.edu/tuition)
3. Scholarship office
4. Course 6 department administrator (for major-specific aid awareness)

ASSUMPTIONS:
This system handles ACADEMIC requirements only. Financial topics require contacting 
Student Financial Services.
```

**Key Behaviors to Test:**
- Refuses financial queries
- Recognizes non-academic scope
- Professional redirection to correct office
- No guessing on costs or aid

---

### OOS-04: Waitlist & Real-time Enrollment

**Query:** "Is there still space in 6.1210? What's my waitlist position?"

**Student Profile:**
- Completed courses: 6.100A, 6.1200, 18.01
- Current term: Spring 2026

**Expected Decision:** ⚠️ **Out-of-Scope**

**Expected Output:**
```
DECISION: ⚠️ Not in Catalog

ANSWER:
Enrollment capacity and waitlist information are managed in real-time by the registrar.
I cannot provide this information from the catalog.

WHY:
The course catalog contains STATIC information:
✓ Course descriptions
✓ Prerequisites
✓ Credit values
✓ General policies

The course catalog does NOT contain DYNAMIC information:
✗ Current enrollment count
✗ Capacity limits
✗ Waitlist positions
✗ Section availability

This data changes HOURLY during registration and requires real-time database access.

CITATIONS:
None—this query is out-of-scope.

TO CHECK ENROLLMENT STATUS:
1. Log into MIT Student Portal
2. Search for course 6.1210
3. View all sections, enrollment, limits
4. Check waitlist status if applicable

ASSUMPTIONS:
This system uses static catalog data. For live registration data, consult the 
registrar system directly during registration periods.
```

**Key Behaviors to Test:**
- Recognizes real-time enrollment data (out-of-scope)
- Clear explanation of why (static vs. dynamic)
- Correct referral to registrar system
- Zero fabrication of availability info

---

### OOS-05: Course Availability by Semester

**Query:** "Is 6.1210 offered in Spring 2026? When is the next time it's available?"

**Student Profile:**
- Completed courses: 6.100A, 6.1200, 18.01
- Current term: Spring 2026
- Target term: Planning ahead

**Expected Decision:** ⚠️ **Out-of-Scope** (Partial)

**Expected Output:**
```
DECISION: ⚠️ Partially Out-of-Scope

ANSWER:
The catalog does NOT contain semester-by-semester offering information.
However, I can provide general guidance:

WHAT I CAN SAY (from catalog):
✓ 6.1210 is a CORE requirement for MIT Course 6
✓ Core courses are typically offered MULTIPLE times per year
✓ Most core courses offered: Fall + Spring (occasionally summer)

WHAT I CANNOT SAY (requires registrar data):
✗ Is 6.1210 specifically offered Spring 2026?
✗ Which sections are open right now?
✗ When is the next offering after Spring 2026?

WHY:
- Offering schedules are determined each academic year
- Depends on enrollment, instructor availability, room conflicts
- Registrar publishes schedules semester-by-semester
- Not contained in the static course catalog

CITATIONS:
- MIT Course 6.1210 Catalog (core course status)
- MIT Registrar (for semester-specific offerings)

TO FIND CURRENT OFFERINGS:
1. MIT Registrar (https://registrar.mit.edu)
2. Search by course code: 6.1210
3. Check all sections for Spring 2026
4. Contact Course 6 department if unavailable

ASSUMPTIONS:
- Course is offered regularly (as a core, likely multiple times yearly)
- Your eligibility remains valid (prerequisites satisfied)
- For specific semester availability, consult registrar
```

**Key Behaviors to Test:**
- Distinguishes catalog info from scheduler info
- Provides what CAN be answered (general offering pattern)
- Clear boundary on semester-specific data
- Helpful partial answer when possible

---

## Evaluation Metrics

### Citation Coverage
- **Definition:** Percentage of factual claims with supporting citations
- **Target:** ≥ 95%
- **Method:** Manual review of each response, audit claims vs. citations

### Overall Accuracy
- **Definition:** Percentage of decisions matching expected answers
- **Target:** ≥ 90%
- **Method:** Blind evaluation of 25 test queries

### Abstention Accuracy
- **Definition:** Percentage of out-of-scope queries correctly identified
- **Target:** 100%
- **Method:** All 5 OOS queries return explicit "I cannot answer" responses

### Hallucination Rate
- **Definition:** Percentage of responses containing unsupported claims
- **Target:** 0%
- **Method:** Verifier agent audit

---

## Test Execution Protocol

### Setup
1. Load FAISS index (pre-built)
2. Initialize all agents (Intake, Retriever, Planner, Verifier)
3. Configure LLM (OpenAI GPT-4 recommended)

### Execution
```bash
python main.py eval
```

### Expected Output
- `evaluation/results/full_results.json` — detailed results per query
- `evaluation/results/evaluation_summary.json` — aggregate metrics
- Console output with pass/fail summary

### Success Criteria
- **All prerequisite checks (PR-01 to PR-10):** 9/10 correct (90%+)
- **All chain traces (CH-01 to CH-05):** 4/5 correct (80%+, chains are complex)
- **All program rules (PG-01 to PG-05):** 4/5 correct (80%+)
- **All out-of-scope (OOS-01 to OOS-05):** 5/5 correct (100%, safety critical)
- **Overall:** 22/25 (88%) with strong out-of-scope handling

---

**Last Updated:** March 2026
