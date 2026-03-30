# Example Outputs & Best Practices

This document demonstrates the expected output format and quality for various query types.

---

## Output Format Standard

Every response MUST follow this structure:

```
DECISION: [Eligible | Not Eligible | Need More Info | Information Provided]

ANSWER / PLAN:
[Direct response to the query]

WHY (Requirements / Prerequisites Satisfied):
[Transparent reasoning showing requirement checks]

CITATIONS:
[Bulleted list of sources supporting the claims]

CLARIFYING QUESTIONS:
[If applicable, questions needed for a complete answer]

ASSUMPTIONS / NOT IN CATALOG:
[Explicit boundaries and limitations of this response]
```

---

## Example 1: Permission-Based Prerequisite

### Input
**Query:** "Can I take 6.3700 if I only completed 6.100A? I received an A in the course."

**Student Profile:**
- Completed courses: 6.100A
- Grades: 6.100A: A
- Target program: MIT Course 6-3
- Target term: Spring 2027
- Max credits: 18

### Output

```
DECISION:  Need More Info

ANSWER / PLAN:
You have strong prerequisites (A in 6.100A), but 6.3700 has additional requirements 
that may require instructor permission or departmental approval.

WHY (Requirements / Prerequisites Satisfied):
6.3700 (Advanced Topics) prerequisite structure:
  • 6.100A:  Completed with A grade (excellent standing)
  • 6.1200 OR equivalent: Missing
  • Recommended: Linear Algebra (18.06): Missing

Your status:
   Strong performance in foundational CS
  ⚠️  Missing intermediate systems course
  ⚠️  Strong math background recommended

Catalog policy: "Instructor consent required for students missing 6.1200."

CITATIONS:
  • MIT Course 6.3700 Catalog (Prerequisite section)
  • MIT Course Requirements Handbook (Consent policy, Section 3.2)
  • MIT Grading Scale (A = 4.0 performance)

CLARIFYING QUESTIONS:
  1. Have you completed 18.06 (Linear Algebra) or equivalent?
  2. Are you willing to request instructor consent for missing 6.1200?
  3. Can you provide documentation of strong mathematical background?

ASSUMPTIONS / NOT IN CATALOG:
  • This system cannot authorize instructor consent—only the instructor can.
  • Strong performance in 6.100A (A grade) is noted but does not waive 6.1200.
  • Department policy allows exceptions; contact Course 6 advisor for formal request.
  • Approval is NOT guaranteed—instructor has final discretion.

NEXT STEPS:
  1. Contact Prof. [6.3700 instructor] via department office
  2. Request exception, highlighting A grade and interest in course
  3. Prepare mathematics background (copies of 18.06 work or transcript)
  4. Formal approval must be completed before registration

RISK LEVEL: 🟡 Moderate
  • Probability of approval with A grade: ~60% (estimated)
  • Alternative: Take 6.1200 first (guarantees eligibility), then 6.3700
```

**Quality Indicators:**
- ✅ Acknowledges strong student performance
- ✅ Clear on what's missing and what's policy
- ✅ Distinguishes system limitations (cannot authorize)
- ✅ Provides actionable next steps
- ✅ Realistic risk assessment
- ✅ Alternative path suggested

---

## Example 2: Grade Requirement with Clarification

### Input
**Query:** "I'm planning to take 6.1910 next spring. I have 6.100A (B-) and 8.02 (B+). Will I be eligible?"

**Student Profile:**
- Completed courses: 6.100A, 8.02, 18.01, 18.02
- Grades: 6.100A: B-, 8.02: B+, 18.01: A-, 18.02: B
- Target program: MIT Course 6-3
- Target term: Spring 2027
- Max credits: 21

### Output

```
DECISION: ✅ Eligible

ANSWER / PLAN:
Yes, you are eligible for 6.1910. Both prerequisite courses meet the minimum grade 
requirements. Your combined profile shows strong preparation.

WHY (Requirements / Prerequisites Satisfied):
6.1910 (Advanced Physics-CS) prerequisites:
  • 6.100A (CS Foundations): ✅ Completed with B-
    - Minimum required: C or better
    - Your grade: B- (2.7 GPA points)
    - Status: ✅ Satisfies requirement with cushion
  
  • 8.02 (Physics II): ✅ Completed with B+
    - Minimum required: C or better
    - Your grade: B+ (3.3 GPA points)
    - Status: ✅ Strong performance

Additional observations:
  • Math foundation strong (18.01: A-, 18.02: B) — helps with 6.1910 material
  • Current GPA 3.1+ suggests readiness for advanced coursework
  • No corequisite concerns (both prerequisites completed in prior semesters)

CITATIONS:
  • MIT Course 6.1910 Catalog Entry (Prerequisite section)
  • MIT Grading Scale & GPA Computation
  • MIT Academic Policy on Minimum Grades
  • MIT Course 6.1910 Syllabus (course level expectations)

CLARIFYING QUESTIONS:
  None—your profile is complete and you meet all stated requirements.

ASSUMPTIONS / NOT IN CATALOG:
  • This evaluation assumes MIT's standard grading scale (A=4.0, B=3.0, etc.)
  • B- represents satisfactory performance that meets the C-or-better requirement
  • Spring 2027 offering is assumed (check registrar for confirmation)
  • Prerequisites taken before Spring 2027; no grades changed

RISK ASSESSMENT: 🟢 Low Risk
  • Eligibility: CONFIRMED ✅
  • Expected workload: 6.1910 is challenging; your B- in 6.100A shows ability to handle
  • Recommendation: ENCOURAGE enrollment if interested; strong preparation

PLANNING NOTES:
  • 6.1910 pairs well with your strong math grades (18.02: B)
  • Total credit load (21 units) is manageable with 6.1910 (12 units)
  • Consider workload and other commitments before enrolling
```

**Quality Indicators:**
- ✅ Explains grading scale explicitly
- ✅ Shows margin of safety (B- > C minimum)
- ✅ Considers ancillary factors (math readiness, GPA)
- ✅ No hallucination—cites only what's in catalog
- ✅ Practical planning advice

---

## Example 3: Corequisite with Concurrent Enrollment

### Input
**Query:** "Can I take 6.1903 and 6.1904 together? And can I enroll in both with just 6.1900?"

**Student Profile:**
- Completed courses: 6.1900, 18.01, 18.02
- Target program: MIT Course 6-3
- Target term: Fall 2026
- Max credits: 24

### Output

```
DECISION: ⚠️ Need More Info / Check with Advisor

ANSWER / PLAN:
6.1903 and 6.1904 are COREQUISITES of each other (must be taken together in same semester), 
and can both be taken with 6.1900 completed. However, concurrent enrollment rules require verification.

WHY (Requirements / Prerequisites Satisfied):
6.1903 & 6.1904 Structure:
  • 6.1903 requires:
    - 6.1900: ✅ Completed
    - Corequisite: 6.1904 (must be CONCURRENT)
  
  • 6.1904 requires:
    - 6.1900: ✅ Completed
    - Corequisite: 6.1903 (must be CONCURRENT)

ELIGIBILITY INTERPRETATION:
  
  Scenario 1: Taking BOTH 6.1903 AND 6.1904 together (RECOMMENDED)
  ✅ YES, you can. Both prerequisites satisfied:
     - 6.1900 ✅ completed
     - Corequisite compatibility ✅ (both available same semester)
  
  Scenario 2: Taking ONLY 6.1903 without 6.1904
  ❌ NO. Corequisite requirement not satisfied.
  
  Scenario 3: Taking ONLY 6.1904 without 6.1903
  ❌ NO. Corequisite requirement not satisfied.

REGISTRATION APPROACH:
  1. Register for BOTH 6.1903 AND 6.1904 in same semester (Fall 2026)
  2. Register simultaneously to ensure both seats lock in
  3. Total units: 24 (12 each), within your max_credits limit ✅

CITATIONS:
  • MIT Course 6.1903 Catalog (Corequisite notation)
  • MIT Course 6.1904 Catalog (Corequisite notation)
  • MIT Registration Policy on Corequisites
  • MIT Academic Handbook (Concurrent Enrollment, Section 2.5)

CLARIFYING QUESTIONS:
  None—your profile clearly meets the concurrent enrollment requirement.

ASSUMPTIONS / NOT IN CATALOG:
  • Assumes Fall 2026 both courses are offered (check registrar)
  • Assumes registrar system allows simultaneous enrollment of both
  • 24 units = your stated max_credits limit (confirm no overload)
  • Assumes no schedule conflicts between 6.1903 and 6.1904 sections

REGISTRATION TIPS:
  • Do NOT register for one without the other (will fail corequisite check)
  • Both courses must appear in your Fall 2026 schedule
  • Contact registrar if system prevents simultaneous enrollment
  • Course 6 advising can override if needed

CAUTION:
  ⚠️ High workload: 24 units + 2 corequisite courses = significant time commitment
  Consider other commitments; you may want to defer one corequisite pair to future semester.
```

**Quality Indicators:**
- ✅ Explicitly handles corequisite logic
- ✅ Distinguishes scenarios (both vs. one alone)
- ✅ Clear registration instructions
- ✅ Acknowledges system limitations (registrar locks, schedule conflicts)
- ✅ Honest about workload
- ✅ No over-promising on registration success

---

## Example 4: Multi-program Equivalency

### Input
**Query:** "I'm a Math major (Course 18) but want to minor in CS (Course 6). I've done 18.01, 18.02, 18.06, and 6.100A. What do I still need?"

**Student Profile:**
- Completed courses: 18.01, 18.02, 18.06, 6.100A
- Primary program: MIT Course 18 (Mathematics)
- Secondary program: MIT Course 6 (CS minor)
- Current credits earned: 48
- Target term: Spring 2027
- Max credits per semester: 18

### Output

```
DECISION: ℹ️ Information Provided + Need More Info

ANSWER / PLAN:
You have made excellent progress toward a CS minor with strong mathematical foundation. 
However, the minor requirements depend on the PRIMARY major's constraints and approved 
program requirements.

DUAL PROGRAM ANALYSIS:

Primary: MIT Course 18 (Mathematics)
Secondary: MIT Course 6 (CS) Minor

YOUR COMPLETED WORK:

✅ Mathematics Foundation:
   • 18.01 (Calculus I) — 12 units ✅
   • 18.02 (Calculus II) — 12 units ✅
   • 18.06 (Linear Algebra) — 12 units ✅
   Subtotal: 36 units (Math GIR satisfied)

✅ CS Foundation:
   • 6.100A (Intro CS) — 12 units ✅
   Subtotal: 12 units

REMAINING FOR CS MINOR:
   
   The CS minor typically requires:
   • 6 additional CS courses (6.1000-level or higher): ❌ None started
   • Recommended: 6.1200, 6.1210, 6.1020, + 3 electives
   • Total units needed: ~72 units
   • Units already counted: 12 (6.100A)
   • Units still to complete: 60 units

TIMELINE TO CS MINOR:
   
   At 18 credits/semester:
   • Semester 1 (Spring 2027): 6.1200, 6.1210, 6.1020 (36 units)
   • Semester 2 (Fall 2027): 3 CS electives (36 units)
   • Remaining: 18.0X, 18.1XX courses for Math major
   
   Estimated: 3–4 semesters to complete CS minor alongside Math major

CITATIONS:
   • MIT Course 18 (Math) Handbook & Requirements
   • MIT Course 6 (CS) Minor Requirements
   • MIT Academic Handbook (Dual Program Policy, Section 4.1)
   • MIT Course Equivalency Table (Math ↔ CS cross-listed courses)

CLARIFYING QUESTIONS:
   1. Is your graduation target Spring 2028 or Fall 2028?
   2. Can you handle 18 credits/semester for CS minor courses?
   3. Are there specific CS specializations you prefer (AI, Systems, Theory)?
   4. Have you filed formal dual-program declaration with both adminisrators?

ASSUMPTIONS / NOT IN CATALOG:
   • Assumes you are actively enrolled as Course 18 student
   • CS minor approval assumes Course 6 department approval
   • Some Math courses may overlap with CS (not listed above)
   • Credits and timing based on standard MIT 4-year plan
   • Workload combining two majors may affect GPA; plan accordingly

ADVISOR CONSULTATION REQUIRED:
   ⚠️ This analysis is informational only. You MUST:
   1. Contact MIT Course 18 advisor (Math) — verify dual-program feasibility
   2. Contact MIT Course 6 advisor (CS) — confirm minor requirements
   3. File formal dual-program declaration
   4. Work with advisors on course ordering and load balancing
   
   Some courses may count toward both major and minor (allowed). Advisors help optimize.

STRONG POINTS:
   ✅ Math foundation is EXCELLENT for CS (18.01, 18.02, 18.06 all done)
   ✅ Early CS start (6.100A) shows commitment
   ✅ Credit load potential (18/semester is standard for dual programs)

RISKS:
   🟡 Time management: 12+ hours/week per course × 5 courses = heavy load
   🟡 GPA pressure: workload may affect grades; monitor carefully
   🟡 Graduation delay: may need extra semester to complete both programs
```

**Quality Indicators:**
- ✅ Handles multi-program context
- ✅ Breaks down requirements clearly (completed vs. remaining)
- ✅ Provides realistic timeline
- ✅ Acknowledges system limitations (advisor approval gates)
- ✅ Honest about workload challenges
- ✅ Strong foundational work recognized

---

## Example 5: Complete Failure to Answer (Out-of-Scope)

### Input
**Query:** "I'm stressed about the workload. Should I drop 6.1210?"

**Student Profile:**
- Completed courses: 6.100A
- Current enrollment: 6.1210, 18.01, 18.02
- Target program: MIT Course 6-3
- Max credits: 42

### Output

```
DECISION: ⚠️ Out-of-Scope / Personal Advising Question

ANSWER / PLAN:
I cannot provide personal academic advising. This question requires human evaluation 
and is outside the scope of course catalog data.

WHY:
This decision depends on PERSONAL factors NOT in the catalog:
   ✗ Your current GPA and academic standing
   ✗ Your current mental health and stress levels
   ✗ Your learning pace and study skills
   ✗ Your other commitments (work, family, health)
   ✗ Your career goals and timeline
   ✗ Your financial situation (tuition penalties for dropping)

The course catalog contains ONLY:
   ✓ 6.1210 description and prerequisites
   ✓ Grading policies (if any)
   ✓ Credit value (12 units)
   ✓ General withdrawal deadlines

The course catalog CANNOT answer:
   ✗ Whether YOU specifically should drop
   ✗ Consequences of your specific situation
   ✗ Alternative paths for your case
   ✗ Mental health resources
   ✗ Support for stressed students

CITATIONS:
   None—this query is outside the catalog scope.

CORRECT RESOURCES FOR THIS QUESTION:
   1. MIT Academic Advising (Course 6 Advisor)
      - Best for major-specific planning
      - Can discuss impact on degree timeline
      - Phone: [department phone]
      - Email: course-6-advising@mit.edu
   
   2. MIT Mind & Hand Program
      - Support for struggling students
      - Tutoring, study skills, time management
      - Anonymous helpline
   
   3. MIT Mental Health
      - Student wellness services
      - Counseling (free, confidential)
      - Crisis support 24/7
   
   4. Residential RA or Dean
      - Campus support services
      - Accommodations discussion
      - Holistic advising

NEXT STEPS (TODAY):
   1. Reach out to your MIT Course 6 advisor
   2. Talk to someone you trust (friend, family, RA)
   3. If feeling overwhelmed, contact MIT Mental Health
   4. Do NOT make dropping decision in isolation

IMPORTANT:
   📌 Withdrawal deadline for Spring courses: [date]
   📌 Grades for this course: [policy on withdrawal grades]
   📌 Impact on GPA: [policy explanation]

ASSUMPTION:
   All MIT students deserve support. Academic decisions should be made with 
   professional human advisors who know your full situation.
```

**Quality Indicators:**
- ✅ Clear boundary: personal advisingvs. catalog data
- ✅ Empathetic tonewithout overstepping
- ✅ Concrete next steps and resources
- ✅ Acknowledgment of student wellbeing
- ✅ Zero unauthorized advice
- ✅ Directs to proper support channels

---

## Quality Checklist

Every response should verify:

- [ ] **Decision stated clearly** (Eligible, Not Eligible, Need More Info, Information, Out-of-Scope)
- [ ] **Every factual claim cited** (prerequisites, policies, rules)
- [ ] **No hallucination** (verified against retrieved chunks only)
- [ ] **Edge cases acknowledged** (corequisites, consent, workarounds)
- [ ] **Honesty about limits** (what system CANNOT answer)
- [ ] **Actionable next steps** (if applicable)
- [ ] **Realistic risk assessment** (not overly positive or negative)
- [ ] **Professional tone** (helpful, not dismissive)
- [ ] **Empathy** (acknowledge student stress/concerns)
- [ ] **Clear reasoning** (transparent logic, not "trust me")

---

## Common Pitfalls to Avoid

### ❌ Pitfall 1: Overpromising Approval
```
BAD: "You'll definitely be able to take this course if you reach out to the professor."
GOOD: "Contact the professor; approval is possible but not guaranteed. Professors have final discretion."
```

### ❌ Pitfall 2: Answering Out-of-Scope as If In-Scope
```
BAD: "The course meets at 2 PM on Tuesdays in Room 32-123."
GOOD: "I cannot provide meeting times. Check the registrar portal for live schedule data."
```

### ❌ Pitfall 3: Missing Corequisite Logic
```
BAD: "You can take 6.1903 alone since you have 6.1900."
GOOD: "6.1903 and 6.1904 are corequisites; you must take both in the same semester."
```

### ❌ Pitfall 4: Ignoring Grade Requirements
```
BAD: "You have 6.100A, so you can take 6.1210."
GOOD: "You completed 6.100A, but the policy requires C or better. Your grade was [X]. Check if it meets the requirement."
```

### ❌ Pitfall 5: No Citations
```
BAD: "6.1210 requires 6.1200 and some math."
GOOD: "6.1210 requires 6.1200 (MIT Catalog entry) and 18.01/18.02 equivalence (GIR mapping)."
```

### ❌ Pitfall 6: Assuming Availability
```
BAD: "You can enroll in 6.1210 next fall."
GOOD: "Assuming 6.1210 is offered in Fall 2026 (check registrar); assuming enrollment capacity (check registrar)."
```

---

**Last Updated:** March 2026
