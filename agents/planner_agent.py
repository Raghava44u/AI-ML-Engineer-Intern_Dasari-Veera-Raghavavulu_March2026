"""
agents/planner_agent.py
------------------------
Planner Agent: Prerequisite decisions, course plans, and multi-hop chain reasoning.
Upgraded: structured prerequisite parsing, AND/OR logic, grade handling, chain reasoning.
FIXED: GIR mapping, corequisite handling, MIT comma-or lists, program-req queries.
"""

import os, re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from loguru import logger
from agents.intake_agent import StudentProfile
from agents.retriever_agent import RetrievalContext
from utils.course_utils import (
    extract_course_codes, get_course_code_help_message, COURSE_REGEX,
    normalize_course_id, course_ids_match, gir_satisfied, GIR_MAP
)
from utils.prereq_parser import PrereqParser


@dataclass
class PlannerOutput:
    answer_or_plan: str
    why: str
    citations: List[str]
    clarifying_questions: List[str]
    assumptions: List[str]
    eligibility_decision: Optional[str] = None
    recommended_courses: Optional[List[Dict]] = None
    risks: Optional[List[str]] = None

    def format_output(self) -> str:
        lines = ["=" * 70, "📋 COURSE PLANNING ASSISTANT RESPONSE", "=" * 70, ""]
        if self.eligibility_decision:
            emoji = {"Eligible": "✅", "Not Eligible": "❌", "Need More Info": "⚠️"}.get(
                self.eligibility_decision, "ℹ️")
            lines.append(f"DECISION: {emoji} {self.eligibility_decision}")
            lines.append("")
        lines.append("ANSWER / PLAN:")
        lines.append(self.answer_or_plan)
        lines.append("")
        lines.append("WHY (Requirements / Prerequisites Satisfied):")
        lines.append(self.why)
        lines.append("")
        lines.append("CITATIONS:")
        if self.citations:
            for cite in self.citations:
                lines.append(f"  • {cite}")
        else:
            lines.append("  ⚠️  No citations — claims not verified from catalog.")
        lines.append("")
        if self.clarifying_questions:
            lines.append("CLARIFYING QUESTIONS:")
            for i, q in enumerate(self.clarifying_questions, 1):
                lines.append(f"  {i}. {q}")
            lines.append("")
        if self.assumptions:
            lines.append("ASSUMPTIONS / NOT IN CATALOG:")
            for a in self.assumptions:
                lines.append(f"  ⚠️  {a}")
            lines.append("")
        if self.risks:
            lines.append("RISKS:")
            for r in self.risks:
                lines.append(f"  ⚠️  {r}")
            lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)


# Grade comparison utilities
GRADE_SCALE = {
    "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7, "D+": 1.3, "D": 1.0, "D-": 0.7, "F": 0.0
}

def grade_meets_minimum(student_grade: str, min_grade: str) -> bool:
    """Check if student's grade meets or exceeds the minimum required grade."""
    student_pts = GRADE_SCALE.get(student_grade, 0.0)
    min_pts = GRADE_SCALE.get(min_grade, 0.0)
    return student_pts >= min_pts


def smart_prereq_check(prereq_text: str, completed: set, grades: dict = None, 
                         min_grade: str = None, credits_earned: int = 0) -> Dict[str, Any]:
    """
    Smart prerequisite check that handles:
    - MIT comma-or lists: "6.3700 , 6.3800 , 18.05 , or 18.600" = ANY of these
    - AND conditions
    - Nested parentheses: "6.100A and ( 6.1200 or ( 6.120A and ... ))"
    - GIR requirements: "Calculus I (GIR)" maps to 18.01
    - Corequisites: "Coreq: 6.1903 or 6.1904" = can be taken concurrently
    - Permission of instructor = Need More Info
    
    Returns: {decision, missing, grade_issues, needs_consent, coreqs_needed}
    """
    result = {
        'decision': 'Eligible',
        'missing': [],
        'grade_issues': [],
        'needs_consent': False,
        'coreqs_needed': [],
        'raw': prereq_text,
    }
    
    if not prereq_text or prereq_text.lower().strip() in ("none", "", "n/a"):
        return result
    
    text = prereq_text.strip()
    text_lower = text.lower()
    
    # Check for "permission of instructor" — this is always satisfiable separately
    if 'permission of instructor' in text_lower:
        result['needs_consent'] = True
        # If entire prereq is "permission of instructor" alone, it's eligible
        # Otherwise, parse the rest
        # Remove " or permission of instructor" and "; or permission of instructor"
        text = re.sub(r'[;,]?\s*or\s+permission\s+of\s+instructor', '', text, flags=re.IGNORECASE)
        text = re.sub(r'permission\s+of\s+instructor\s*[;,]?\s*', '', text, flags=re.IGNORECASE)
        text = text.strip().rstrip(';').rstrip(',').strip()
        if not text or text.lower() in ("none", "", "n/a"):
            return result
    
    # Extract corequisites — they can be taken concurrently, not hard prereqs
    coreq_match = re.search(r'Coreq:\s*(.+?)(?:\)|;|$)', text, re.IGNORECASE)
    coreqs = []
    if coreq_match:
        coreq_text = coreq_match.group(1).strip()
        coreqs = extract_course_codes(coreq_text)
        result['coreqs_needed'] = [c for c in coreqs if c not in completed]
        # Remove corequisite text from main prerequisite parsing
        text = text[:coreq_match.start()] + text[coreq_match.end():]
        text = re.sub(r'\(\s*\)', '', text)
        text = re.sub(r',\s*and\s*$', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'and\s*$', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',\s*$', '', text).strip()
        text = text.rstrip(';').rstrip(',').strip()
    
    # Check GIR requirements by length descending to prevent 'physics i' matching within 'physics ii'
    for gir_key, gir_courses in sorted(GIR_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        gir_full_pattern = re.compile(re.escape(gir_key), re.IGNORECASE)
        if gir_full_pattern.search(text_lower):
            # Check if student has any equivalent
            gir_met = any(c in completed for c in gir_courses)
            if not gir_met:
                result['missing'].append(f"{gir_key.title()} ({' or '.join(gir_courses)})")
            # Remove GIR text from further parsing to avoid confusion
            text = gir_full_pattern.sub('', text)
            # Recompute text_lower after substitution to prevent cascading matching issues
            text_lower = text.lower()
            text = re.sub(r'^\s*,\s*', '', text)
            text = re.sub(r'\s*,\s*$', '', text)
            text = re.sub(r'\s*,\s*and\s+', ' and ', text, flags=re.IGNORECASE)
            text = text.strip()

    # Now parse the remaining text using the AST parser for complex expressions
    if text and text.lower() not in ("none", "", "n/a", "and", ","):
        parser = PrereqParser()
        try:
            ast = parser.parse_ast(text)
            if ast:
                eval_result = parser.evaluate(ast, completed)
                if eval_result['status'] != 'Eligible':
                    # Extract flat missing list
                    flat_missing = _flatten_missing(eval_result['missing'])
                    result['missing'].extend(flat_missing)
        except Exception as e:
            logger.warning(f"AST parse failed for '{text}': {e}")
            # Fallback: simple course code check
            codes = extract_course_codes(text)
            for code in codes:
                if code not in completed:
                    result['missing'].append(code)
    
    # Grade check
    if min_grade and min_grade in GRADE_SCALE and grades:
        all_prereq_codes = extract_course_codes(prereq_text)
        for code in all_prereq_codes:
            if code in grades and code in completed:
                if not grade_meets_minimum(grades[code], min_grade):
                    result['grade_issues'].append(
                        f"{code}: earned {grades[code]} but need {min_grade} or better"
                    )
    
    # Determine final decision
    if result['grade_issues']:
        result['decision'] = 'Not Eligible'
    elif result['missing']:
        if result['needs_consent']:
             result['decision'] = 'Need More Info'
        else:
             result['decision'] = 'Not Eligible'
    
    return result


def _flatten_missing(missing_list: list) -> List[str]:
    """Flatten nested missing requirements into human-readable strings."""
    result = []
    for item in missing_list:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and 'OR' in item:
            or_options = item['OR']
            flat_options = []
            for opt in or_options:
                if isinstance(opt, list):
                    flat_options.extend(opt)
                elif isinstance(opt, str):
                    flat_options.append(opt)
            result.append(" OR ".join(str(o) for o in flat_options))
        elif isinstance(item, list):
            result.extend(_flatten_missing(item))
    return result


class PlannerAgent:
    def __init__(self, llm_client=None, use_rule_based_fallback=True):
        self.llm_client = llm_client
        self.use_rule_based = True
        self._try_init_llm()

    def _try_init_llm(self):
        """Try Grok, Anthropic then OpenAI; fall back to rule-based if neither available."""
        key = os.getenv("GROK_API_KEY")
        if key:
            try:
                import openai
                self.llm_client = openai.OpenAI(api_key=key, base_url="https://api.x.ai/v1")
                self.llm_type = "grok"
                self.use_rule_based = False
                logger.info("✓ Using Grok for planning")
                return
            except Exception:
                pass
                
        key = os.getenv("ANTHROPIC_API_KEY")
        if key:
            try:
                import anthropic
                self.llm_client = anthropic.Anthropic(api_key=key)
                self.llm_type = "anthropic"
                self.use_rule_based = False
                logger.info("✓ Using Anthropic Claude for planning")
                return
            except Exception:
                pass
        key = os.getenv("OPENAI_API_KEY")
        if key:
            try:
                import openai
                self.llm_client = openai.OpenAI(api_key=key)
                self.llm_type = "openai"
                self.use_rule_based = False
                logger.info("✓ Using OpenAI for planning")
                return
            except Exception:
                pass
        logger.info("No LLM API key — using rule-based prerequisite logic")
        self.llm_type = "rule_based"

    def check_prerequisites(self, query, profile, ctx) -> PlannerOutput:
        if self.use_rule_based:
            return self._rule_based_prereq_check(query, profile, ctx)
        return self._llm_prereq_check(query, profile, ctx)

    def generate_course_plan(self, profile, ctx) -> PlannerOutput:
        if self.use_rule_based:
            return self._rule_based_course_plan(profile, ctx)
        return self._llm_course_plan(profile, ctx)

    def check_prerequisite_chain(self, query, profile, ctx) -> PlannerOutput:
        """Multi-hop prerequisite chain reasoning."""
        return self._rule_based_chain_check(query, profile, ctx)

    def handle_out_of_scope(self, query) -> PlannerOutput:
        return PlannerOutput(
            answer_or_plan=(
                "I don't have that information in the provided catalog/policies.\n\n"
                "This question may be about:\n"
                "• Course availability in a specific semester (not in static catalog)\n"
                "• Instructor-specific assignments (contact department office)\n"
                "• Real-time enrollment/waitlist data (check student portal)\n"
                "• Financial aid or tuition (contact Bursar/Financial Aid Office)"
            ),
            why="The requested information is not contained in the curated catalog documents.",
            citations=[],
            clarifying_questions=[],
            assumptions=[],
            risks=["Verify all details with official university sources before acting."]
        )

    def handle_program_query(self, query, profile, ctx) -> PlannerOutput:
        """Handle program requirement queries (no specific course code needed)."""
        # Gather all relevant program/policy context
        context_lines = []
        relevant_citations = []
        for result in ctx.results:
            if result.doc_type in ("program_requirement", "policy"):
                context_lines.append(result.text)
                relevant_citations.append(result.citation())
            elif "requirement" in result.text.lower() or "program" in result.text.lower():
                context_lines.append(result.text)
                relevant_citations.append(result.citation())
        
        if not context_lines:
            # Include all retrieved context as fallback
            for result in ctx.results:
                context_lines.append(result.text[:500])
                relevant_citations.append(result.citation())
        
        combined_context = "\n\n---\n\n".join(context_lines)
        
        # Construct a helpful answer from the context
        answer_lines = [f"Based on the catalog context for {profile.target_program or 'your program'}:\n"]
        answer_lines.append(combined_context[:2000])  # Cap at reasonable length
        
        return PlannerOutput(
            answer_or_plan="\n".join(answer_lines),
            why=f"Retrieved {len(context_lines)} relevant catalog sections for this query.",
            citations=relevant_citations or [r.citation() for r in ctx.results],
            clarifying_questions=[],
            assumptions=[
                "Program requirement information from catalog year 2024-2025.",
                "Verify current requirements with academic advisor."
            ]
        )

    # ── Rule-based prerequisite check ────────────────────────────────────────

    def _rule_based_prereq_check(self, query, profile, ctx) -> PlannerOutput:
        course_codes = extract_course_codes(query)
        if not course_codes:
            return PlannerOutput(
                answer_or_plan="Couldn't identify a course code. Please specify e.g. CS301 or 6.1210.",
                why="No course code found in query.",
                citations=[],
                clarifying_questions=[f"Which course are you asking about? {get_course_code_help_message()}"],
                assumptions=[]
            )

        # Heuristic: If multiple codes, the target is likely the one mentioned after certain keywords
        target_course = course_codes[0]
        if len(course_codes) > 1:
            q_low = query.lower()
            for code in course_codes:
                pattern = rf"(?:before|for|enrolling? in|take|regarding?|about)\s+{re.escape(code)}"
                if re.search(pattern, q_low, re.IGNORECASE):
                    target_course = code
                    break
            else:
                target_course = course_codes[-1]

        # ── Find the chunk that IS the target course ──
        course_info = self._find_course_chunk(target_course, ctx)

        if course_info is None:
            return PlannerOutput(
                answer_or_plan=(
                    f"I don't have sufficient information about {target_course} "
                    "in the provided catalog. It may not be in the curated course set."
                ),
                why="Course not found in retrieved catalog context.",
                citations=[r.citation() for r in ctx.results],
                clarifying_questions=[],
                assumptions=[f"{target_course} may not be in the curated catalog subset."]
            )

        # ── Extract prerequisites from the correct chunk ──
        prereq_match = re.search(
            r'(?:Prereq(?:uisite)?s?):\s*(.+?)(?:\n\s*Units:|\n\s*Credit cannot|\n\s*URL:|\n\s*Lecture:|\n\s*Co-requisite|\n\s*Min|\n\s*Offered|\n\s*Category|\n\s*Learning|$)',
            course_info.text, re.IGNORECASE | re.DOTALL
        )
        prereqs_raw = prereq_match.group(1).strip() if prereq_match else "None"
        prereqs_raw = prereqs_raw.replace('\n', ' ').strip()
        # Clean up extra whitespace
        prereqs_raw = re.sub(r'\s+', ' ', prereqs_raw)

        # Extract min grade from dedicated field
        min_grade_match = re.search(
            r'Minimum grade required in prerequisites:\s*([A-F][+-]?)',
            course_info.text, re.IGNORECASE
        )
        min_grade = min_grade_match.group(1) if min_grade_match else None

        # Extract offered semesters
        offered_match = re.search(r'Offered:\s*(.+?)(?:\n|$)', course_info.text, re.IGNORECASE)
        offered = offered_match.group(1).strip() if offered_match else "Not specified"

        completed = set(profile.completed_courses or [])
        grades = profile.grades or {}
        credits_earned = profile.current_credits_earned or 0

        # ── Smart prerequisite check ──
        check = smart_prereq_check(
            prereqs_raw, completed, grades, min_grade, credits_earned
        )

        decision = check['decision']
        missing = check['missing']
        grade_issues = check['grade_issues']
        needs_consent = check['needs_consent']
        coreqs_needed = check['coreqs_needed']

        if decision == 'Eligible':
            prereq_codes = extract_course_codes(prereqs_raw)
            completed_prereqs = [c for c in prereq_codes if c in completed]
            reason_lines = [
                f"All prerequisites satisfied: {', '.join(completed_prereqs) if completed_prereqs else 'None required'}.",
            ]
            if min_grade and not grade_issues:
                reason_lines.append(f"Minimum grade requirement ({min_grade}) met for all prerequisites.")
            if needs_consent:
                # We mention that permission is an option/note, but we do NOT override Eligible to Need More Info
                # because if they satisfied the course prerequisites, they don't strictly *need* permission.
                reason_lines.append(
                    "Note: Course also mentions permission of instructor as an option/requirement."
                )
            if coreqs_needed:
                reason_lines.append(f"Corequisite(s) can be taken concurrently: {', '.join(coreqs_needed)}.")
            reason_lines.append(f"Offered: {offered}.")
            reason_lines.append(f"(Source: {course_info.source_title}, chunk: {course_info.chunk_id})")
            reason = "\n".join(reason_lines)
            next_step = f"You are eligible to enroll in {target_course}. Register during your enrollment window."
        elif grade_issues:
            reason = (
                f"Prerequisites completed but minimum grade requirement not met.\n"
                f"Grade issues: {'; '.join(grade_issues)}.\n"
                f"Minimum required: {min_grade}.\n"
                f"(Source: {course_info.source_title}, chunk: {course_info.chunk_id})"
            )
            next_step = "Retake the failing prerequisite or seek instructor override."
        else:
            reason_lines = [
                f"Missing prerequisites: {', '.join(missing)}.",
                f"Full prerequisite requirement: '{prereqs_raw}'",
                f"(Source: {course_info.source_title}, chunk: {course_info.chunk_id})"
            ]
            if needs_consent:
                reason_lines.append("Also requires instructor consent — contact department.")
            if coreqs_needed:
                reason_lines.append(f"Also need corequisite(s): {', '.join(coreqs_needed)} (can be taken concurrently).")
            reason = "\n".join(reason_lines)
            next_step = f"Complete missing prerequisites before enrolling: {', '.join(missing)}"

        return PlannerOutput(
            answer_or_plan=(
                f"Prerequisite check for {target_course}: {decision}.\n\n"
                f"{next_step}\n\n"
                f"Full prerequisite requirement: '{prereqs_raw}'"
            ),
            why=reason,
            citations=[r.citation() for r in ctx.results],
            clarifying_questions=(
                [] if profile.grades
                else ["Do you have grades for your completed courses? Some courses require minimum grades (e.g., C or better)."]
            ),
            assumptions=[
                "Course availability by term not verified — check current course schedule.",
                f"Prerequisite information from catalog year 2024-2025 (chunk: {course_info.chunk_id if course_info else 'N/A'})."
            ],
            eligibility_decision=decision
        )

    # ── Multi-hop prerequisite chain reasoning ─────────────────────────────

    def _rule_based_chain_check(self, query, profile, ctx) -> PlannerOutput:
        """Build and present the full prerequisite chain for a target course."""
        course_codes = extract_course_codes(query)
        target_course = course_codes[0] if course_codes else None

        if not target_course:
            return PlannerOutput(
                answer_or_plan="Couldn't identify a target course for chain analysis.",
                why="No course code found in query.",
                citations=[],
                clarifying_questions=["Which course do you want the prerequisite chain for?"],
                assumptions=[]
            )

        completed = set(profile.completed_courses or [])
        grades = profile.grades or {}

        # Build the full prerequisite graph from retrieved context
        prereq_graph: Dict[str, Dict] = {}
        for result in ctx.results:
            course_match = re.search(f'COURSE: ({COURSE_REGEX})', result.text)
            if not course_match:
                continue
            cid = course_match.group(1)
            prereq_match = re.search(
                r'(?:Prereq(?:uisite)?s?):\s*(.+?)(?:\n\s*Units:|\n\s*Credit cannot|\n\s*URL:|\n\s*Lecture:|\n\s*Co-requisite|\n\s*Min|\n\s*Offered|\n\s*Category|\n\s*Learning|$)',
                result.text, re.IGNORECASE | re.DOTALL
            )
            prereqs_raw = prereq_match.group(1).strip().replace('\n', ' ') if prereq_match else "None"
            prereqs_raw = re.sub(r'\s+', ' ', prereqs_raw)
            
            min_grade_match = re.search(r'Minimum grade.*?:\s*([A-F][+-]?)', result.text, re.IGNORECASE)
            min_grade = min_grade_match.group(1) if min_grade_match else None
            
            prereq_graph[cid] = {
                'prereqs_raw': prereqs_raw,
                'min_grade': min_grade,
                'citation': result.citation()
            }

        # Walk the chain backward from target
        chain = self._build_chain(target_course, prereq_graph, completed)

        # Determine eligibility for target
        if target_course in prereq_graph:
            info = prereq_graph[target_course]
            check = smart_prereq_check(info['prereqs_raw'], completed)
            all_prereqs_met = check['decision'] == 'Eligible'
            missing_for_target = check['missing']
        else:
            all_prereqs_met = False
            missing_for_target = [f"No data for {target_course}"]

        # Format the chain output
        chain_lines = [f"Prerequisite Chain Analysis for {target_course}:", ""]
        
        if chain:
            chain_lines.append("STEP-BY-STEP PREREQUISITE CHAIN:")
            for i, step in enumerate(chain, 1):
                status = "✅ COMPLETED" if step['course'] in completed else "❌ NOT COMPLETED"
                grade_info = ""
                if step['course'] in grades:
                    grade_info = f" (grade: {grades[step['course']]})"
                chain_lines.append(
                    f"  Step {i}: {step['course']}{grade_info} — {status}"
                )
                if step.get('prereqs'):
                    chain_lines.append(f"    Prerequisites: {step['prereqs']}")
                if step.get('min_grade'):
                    chain_lines.append(f"    Minimum grade required: {step['min_grade']}")
        
        chain_lines.append("")
        
        # Remaining courses needed
        remaining = [s['course'] for s in chain if s['course'] not in completed and s['course'] != target_course]
        if remaining:
            chain_lines.append(f"COURSES STILL NEEDED BEFORE {target_course}:")
            for c in remaining:
                chain_lines.append(f"  → {c}")
            chain_lines.append(f"\nYou need to complete {len(remaining)} more course(s) before taking {target_course}.")
        elif all_prereqs_met:
            chain_lines.append(f"✅ All prerequisites for {target_course} are satisfied!")
        else:
            chain_lines.append(f"Missing for {target_course}: {', '.join(missing_for_target)}")

        decision = "Eligible" if all_prereqs_met else "Not Eligible"

        return PlannerOutput(
            answer_or_plan="\n".join(chain_lines),
            why=(
                f"Chain analysis traced all prerequisite dependencies for {target_course}. "
                f"Completed courses: {', '.join(sorted(completed)) if completed else 'None'}. "
                f"Remaining prerequisites: {', '.join(remaining) if remaining else 'None'}."
            ),
            citations=[r.citation() for r in ctx.results],
            clarifying_questions=[],
            assumptions=[
                "Chain analysis uses prerequisite data from the current catalog year.",
                "Some prerequisites may have OR alternatives not fully explored.",
            ],
            eligibility_decision=decision
        )

    def _build_chain(self, target: str, graph: Dict, completed: Set[str]) -> List[Dict]:
        """
        Build ordered prerequisite chain via BFS backward from target.
        Returns list of {course, prereqs, min_grade} in order (earliest first).
        """
        visited = set()
        queue = [target]
        chain = []

        while queue:
            course = queue.pop(0)
            if course in visited:
                continue
            visited.add(course)

            info = graph.get(course, {})
            prereqs_raw = info.get('prereqs_raw', 'Unknown')
            min_grade = info.get('min_grade')
            
            # Extract course codes from prereqs
            prereq_codes = extract_course_codes(prereqs_raw) if prereqs_raw not in ('Unknown', 'None', '') else []

            chain.append({
                'course': course,
                'prereqs': prereqs_raw,
                'min_grade': min_grade,
            })

            # Add prerequisites to queue
            for code in prereq_codes:
                if code not in visited:
                    queue.append(code)

        # Reverse to get earliest-first order
        chain.reverse()
        return chain

    # ── Rule-based course plan ────────────────────────────────────────────────

    def _rule_based_course_plan(self, profile, ctx) -> PlannerOutput:
        completed = set(profile.completed_courses or [])
        grades = profile.grades or {}
        max_credits = profile.max_credits or 15

        available = []
        for result in ctx.results:
            course_match = re.search(f'COURSE: ({COURSE_REGEX}) - (.+)', result.text)
            if not course_match:
                continue
            course_id = course_match.group(1)
            course_title = course_match.group(2).strip()
            if course_id in completed:
                continue

            prereq_match = re.search(
                r'(?:Prereq(?:uisite)?s?):\s*(.+?)(?:\n\s*Units:|\n\s*Credit cannot|\n\s*URL:|\n\s*Lecture:|\n\s*Co-requisite|\n\s*Min|\n\s*Offered|\n\s*Category|\n\s*Learning|$)',
                result.text, re.IGNORECASE | re.DOTALL
            )
            prereqs_raw = prereq_match.group(1).strip().replace('\n', ' ') if prereq_match else "None"
            prereqs_raw = re.sub(r'\s+', ' ', prereqs_raw)

            credits_match = re.search(r'Credits?: ([\d-]+)', result.text)
            credits = 3  # default
            if credits_match:
                cred_text = credits_match.group(1)
                # MIT format: "3-0-9" means 3+0+9=12 units
                parts = cred_text.split('-')
                try:
                    credits = sum(int(p) for p in parts)
                except ValueError:
                    credits = 3

            min_grade_match = re.search(r'Minimum grade.*?:\s*([A-F][+-]?)', result.text, re.IGNORECASE)
            min_grade = min_grade_match.group(1) if min_grade_match else None

            # Category for prioritization
            category_match = re.search(r'Category:\s*(.+?)(?:\n|$)', result.text, re.IGNORECASE)
            category = category_match.group(1).strip() if category_match else ""

            check = smart_prereq_check(prereqs_raw, completed, grades, min_grade,
                                        profile.current_credits_earned or 0)
            eligible = check['decision'] == 'Eligible'

            # Priority score for ordering
            priority = 0
            if "Core Required" in category or "Capstone" in category:
                priority = 3
            elif "Elective" in category:
                priority = 1
            else:
                priority = 2

            available.append({
                "course_id": course_id,
                "title": course_title,
                "credits": credits,
                "eligible": eligible,
                "missing": check['missing'],
                "prereqs_raw": prereqs_raw,
                "citation": result.citation(),
                "category": category,
                "priority": priority,
                "justification": self._generate_justification(course_id, course_title, category, prereqs_raw, completed)
            })

        eligible_courses = sorted(
            [c for c in available if c["eligible"]],
            key=lambda x: x["priority"],
            reverse=True
        )

        if not eligible_courses:
            return PlannerOutput(
                answer_or_plan=(
                    "Based on the retrieved catalog context, no eligible courses were identified for your profile. "
                    "This may be because all eligible courses are already completed, or the catalog subset "
                    "doesn't cover your current level. Please consult your academic advisor."
                ),
                why="No eligible courses found in retrieved chunks.",
                citations=[r.citation() for r in ctx.results],
                clarifying_questions=["Which specific areas/tracks are you interested in?"],
                assumptions=["Only courses in the retrieved catalog subset were considered."]
            )

        plan, total = [], 0
        for course in eligible_courses:
            if total + course["credits"] <= max_credits:
                plan.append(course)
                total += course["credits"]
            if total >= max_credits:
                break

        plan_lines = [
            f"Proposed Course Plan for {profile.target_term} (Max {max_credits} credits)",
            f"Total planned credits: {total}",
            ""
        ]
        for i, c in enumerate(plan, 1):
            plan_lines.append(
                f"{i}. {c['course_id']} — {c['title']} ({c['credits']} cr)\n"
                f"   Category: {c['category']}\n"
                f"   Prerequisites: {c['prereqs_raw']}\n"
                f"   Status: All prerequisites satisfied ✓\n"
                f"   Justification: {c['justification']}\n"
                f"   Source: {c['citation']}"
            )

        # Show near-eligible courses
        near_eligible = [c for c in available if not c["eligible"] and len(c["missing"]) == 1]
        if near_eligible:
            plan_lines.append("\nCourses requiring 1 more prerequisite (for next planning):")
            for c in near_eligible[:5]:
                plan_lines.append(f"  - {c['course_id']} ({c['title']}): needs {c['missing'][0]}")

        return PlannerOutput(
            answer_or_plan="\n".join(plan_lines),
            why=(
                f"Selected courses where all prerequisites are satisfied based on "
                f"completed courses: {', '.join(sorted(completed))}.\n"
                f"Credit limit: {max_credits} credits. Total planned: {total} credits.\n"
                f"Courses are prioritized: core required > math required > electives."
            ),
            citations=[c["citation"] for c in plan],
            clarifying_questions=[],
            assumptions=[
                "Course offering by term (Fall/Spring/Summer) not verified — check current schedule.",
                "Program requirement fit not fully verified without complete program document context.",
            ],
            recommended_courses=plan,
            risks=[
                "Some courses offered only in Fall OR Spring — verify availability for your target term.",
                "Course capacity limits unknown — register early during your enrollment window.",
                "Transfer credit equivalencies not verified by this system.",
            ]
        )

    def _generate_justification(self, course_id, title, category, prereqs, completed):
        """Generate a brief justification for why a course is recommended."""
        justifications = []
        if "Core Required" in category:
            justifications.append(f"{course_id} is a core requirement for the CS major")
        elif "Capstone" in category:
            justifications.append(f"{course_id} is required for graduation (capstone)")
        elif "Math Core" in category:
            justifications.append(f"{course_id} fulfills a math requirement for the CS major")
        else:
            justifications.append(f"{course_id} is an eligible elective")
        
        if prereqs.lower() == "none":
            justifications.append("no prerequisites needed")
        else:
            justifications.append("all prerequisites have been completed")
        
        return "; ".join(justifications) + "."

    def _find_course_chunk(self, target_course, ctx):
        """Find the chunk that IS the target course, with fuzzy bracket matching."""
        target_norm = normalize_course_id(target_course)
        
        # Exact match first
        for result in ctx.results:
            header = f"COURSE: {target_course}"
            if result.text.startswith(header) or f"\n{header}" in result.text:
                return result
        
        # Normalized match (strip [J] etc.)
        for result in ctx.results:
            course_match = re.search(f'COURSE: ({COURSE_REGEX})', result.text)
            if course_match:
                found_id = course_match.group(1)
                if normalize_course_id(found_id) == target_norm:
                    return result
        
        # Fallback: search all results with contains check
        for result in ctx.results:
            if f"COURSE: {target_course}" in result.text:
                return result
            # Check normalized version
            if f"COURSE: {target_norm}" in result.text:
                return result
        
        return None

    # ── LLM-based methods ─────────────────────────────────────────────────────

    SYSTEM_PROMPT = """You are a university course planning assistant. Use ONLY the provided catalog context.
RULES:
1. ALWAYS cite sources using [Source Title] URL format for every factual claim.
2. Say "I don't have that information in the provided catalog/policies." if the answer is not in context.
3. When checking prerequisites, list ALL required courses and check each one explicitly.
4. When a minimum grade is required (e.g., "C or better"), C- does NOT satisfy it.
5. For AND prerequisites, ALL courses must be completed. For OR prerequisites, only ONE is needed.
6. YOU MUST STRICTLY FORMAT YOUR OUTPUT USING THESE EXACT HEADERS:
Answer / Plan:
Why:
Citations:
Clarifying Questions:
Assumptions / Not in catalog:"""

    def _llm_prereq_check(self, query, profile, ctx) -> PlannerOutput:
        prompt = f"""Student Profile:\n{profile.summary()}\n\nCatalog Context:\n{ctx.to_context_string()}\n\nQuestion: {query}\n\nAnalyze prerequisites step by step. State: Eligible / Not Eligible / Need More Info.
Important: When a minimum grade is specified (e.g., B or better), grades below that letter (including B-) do NOT satisfy it. Check AND vs OR prerequisites carefully."""
        response = self._call_llm(prompt)
        return self._parse_llm(response, ctx.citations)

    def _llm_course_plan(self, profile, ctx) -> PlannerOutput:
        prompt = f"""Student Profile:\n{profile.summary()}\n\nCatalog Context:\n{ctx.to_context_string()}\n\nGenerate a course plan for {profile.target_term} with max {profile.max_credits} credits.
For each recommended course, provide:
1. Course ID and title
2. Why it's recommended (core requirement, track requirement, or elective)
3. Citation from catalog
4. Prerequisites status (all satisfied)"""
        response = self._call_llm(prompt)
        return self._parse_llm(response, ctx.citations)

    def _call_llm(self, prompt):
        try:
            if self.llm_type == "grok":
                r = self.llm_client.chat.completions.create(
                    model="grok-beta", max_tokens=2000, temperature=0.0,
                    messages=[{"role": "system", "content": self.SYSTEM_PROMPT},
                              {"role": "user", "content": prompt}])
                return r.choices[0].message.content
            elif self.llm_type == "anthropic":
                r = self.llm_client.messages.create(
                    model="claude-sonnet-4-20250514", max_tokens=2000, temperature=0.0,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}])
                return r.content[0].text
            elif self.llm_type == "openai":
                r = self.llm_client.chat.completions.create(
                    model="gpt-4o", max_tokens=2000, temperature=0.0,
                    messages=[{"role": "system", "content": self.SYSTEM_PROMPT},
                              {"role": "user", "content": prompt}])
                return r.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"Error: {e}"

    def _parse_llm(self, response, retrieval_citations):
        sections = {"answer": "", "why": "", "citations": [], "clarifying": [], "assumptions": []}
        current = "answer"
        for line in response.split("\n"):
            ll = line.lower().strip()
            if ll.startswith("answer") or ll.startswith("plan:"):
                current = "answer"
            elif ll.startswith("why"):
                current = "why"
            elif ll.startswith("citation"):
                current = "citations"
            elif ll.startswith("clarif"):
                current = "clarifying"
            elif ll.startswith("assumption"):
                current = "assumptions"
            else:
                if current in ("answer", "why"):
                    sections[current] += line + "\n"
                elif line.strip():
                    sections[current].append(line.strip())

        decision = None
        rl = response.lower()
        if "not eligible" in rl:
            decision = "Not Eligible"
        elif "eligible" in rl:
            decision = "Eligible"
        elif "need more info" in rl:
            decision = "Need More Info"

        return PlannerOutput(
            answer_or_plan=sections["answer"].strip() or response[:500],
            why=sections["why"].strip() or "See answer above.",
            citations=list(set(sections["citations"] + retrieval_citations)),
            clarifying_questions=sections["clarifying"],
            assumptions=sections["assumptions"],
            eligibility_decision=decision
        )
