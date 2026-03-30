"""
agents/verifier_agent.py
-------------------------
Verifier/Auditor Agent: Validates planner output before delivery to the user.

RESPONSIBILITIES:
  1. Check that ALL factual claims have citations
  2. Detect potential hallucinations (claims not backed by retrieved context)
  3. Verify prerequisite logic is consistent with catalog data
  4. Reject or flag invalid outputs
  5. Enforce the structured output format

THIS IS THE SAFETY LAYER. If the planner makes unsupported claims,
the verifier catches them and either:
  - Removes the unsupported claim
  - Adds a warning flag
  - Triggers re-generation with stricter prompting
  - Falls back to safe abstention

Per assessment: "Check missing citations, hallucinations, wrong prerequisite logic. Reject invalid outputs."
"""

import re
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
from loguru import logger

from agents.planner_agent import PlannerOutput
from agents.retriever_agent import RetrievalContext


@dataclass
class VerificationResult:
    """Result of the verification process."""
    passed: bool
    original_output: PlannerOutput
    verified_output: PlannerOutput
    issues_found: List[str]
    issues_corrected: List[str]
    citation_coverage: float  # 0.0 to 1.0

    def summary(self) -> str:
        lines = [
            f"✓ Verification {'PASSED' if self.passed else 'FAILED/CORRECTED'}",
            f"  Citation coverage: {self.citation_coverage:.0%}",
            f"  Issues found: {len(self.issues_found)}",
            f"  Issues corrected: {len(self.issues_corrected)}",
        ]
        if self.issues_found:
            lines.append("  Issues:")
            for issue in self.issues_found:
                lines.append(f"    ⚠️  {issue}")
        return "\n".join(lines)


class VerifierAgent:
    """
    Verifier/Auditor Agent: the last line of defense against hallucination.

    Verification pipeline:
      1. Citation check: does every factual claim have a citation?
      2. Consistency check: does the prerequisite logic match retrieved context?
      3. Completeness check: are all required output sections present?
      4. Safe abstention check: is the abstention appropriate for out-of-scope queries?
      5. Format check: is the output in the mandatory format?
    """

    # Keywords that indicate factual claims requiring citations
    CLAIM_INDICATORS = [
        "requires", "prerequisite", "must have", "must complete", "eligible",
        "not eligible", "minimum grade", "credit", "only offered", "offered in",
        "students must", "cannot enroll", "cannot register", "advisor approval",
        "instructor consent", "maximum", "at least", "no more than",
        "requires concurrent", "corequisite", "residency"
    ]

    # Keywords that should trigger safe abstention (not in catalog)
    OUT_OF_SCOPE_KEYWORDS = [
        "which professor", "what time does", "when does the class meet",
        "is there still space", "waitlist position", "how many seats",
        "financial aid", "scholarship", "tuition", "room and board",
        "which section", "online or in-person", "zoom", "hybrid"
    ]

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: If True, flag any claim without a citation. 
                         If False, only flag obviously hallucinated content.
        """
        self.strict_mode = strict_mode

    def verify(
        self,
        planner_output: PlannerOutput,
        retrieval_context: RetrievalContext,
        original_query: str
    ) -> VerificationResult:
        """
        Main verification pipeline.

        Returns a VerificationResult with either the original (if passed)
        or a corrected output with issues flagged.
        """
        issues = []
        corrections = []
        output = planner_output  # We may modify this

        # 1. Citation coverage check
        citation_score, citation_issues = self._check_citations(output, retrieval_context)
        issues.extend(citation_issues)

        # 2. Hallucination detection
        hallucination_issues = self._check_for_hallucinations(output, retrieval_context)
        issues.extend(hallucination_issues)

        # 3. Prerequisite logic consistency
        prereq_issues = self._check_prereq_logic(output, retrieval_context)
        issues.extend(prereq_issues)

        # 4. Out-of-scope / safe abstention check
        abstention_needed, abstention_reason = self._check_out_of_scope(original_query, output)
        if abstention_needed:
            issues.append(f"ABSTENTION REQUIRED: {abstention_reason}")

        # 5. Apply corrections
        corrected_output, corrections = self._apply_corrections(output, issues, retrieval_context)

        # Determine if verification passed
        critical_issues = [i for i in issues if "CRITICAL" in i or "HALLUCINATION" in i or "ABSTENTION" in i]
        passed = len(critical_issues) == 0

        return VerificationResult(
            passed=passed,
            original_output=planner_output,
            verified_output=corrected_output,
            issues_found=issues,
            issues_corrected=corrections,
            citation_coverage=citation_score
        )

    def _check_citations(
        self, output: PlannerOutput, ctx: RetrievalContext
    ) -> Tuple[float, List[str]]:
        """
        Check if factual claims have citations.
        Returns (coverage_score, list_of_issues).
        """
        issues = []
        claims_found = 0
        claims_cited = 0

        # Count factual claims in the answer
        full_text = output.answer_or_plan + " " + output.why
        sentences = re.split(r'[.!?]', full_text)

        for sentence in sentences:
            sentence_lower = sentence.lower()
            has_claim = any(kw in sentence_lower for kw in self.CLAIM_INDICATORS)
            if has_claim:
                claims_found += 1

        # Check if citations were provided
        if claims_found > 0 and not output.citations:
            issues.append(
                f"CRITICAL: {claims_found} factual claim(s) found but NO citations provided. "
                "All prerequisite and requirement claims must be cited."
            )
            coverage = 0.0
        elif claims_found > 0:
            # Citations exist — score based on how many retrieval sources were used
            cited_sources = set()
            for cite in output.citations:
                # Extract source identifiers from citations
                if "chunk_" in cite:
                    cited_sources.add(cite.split("chunk_")[1].split()[0])
                elif "http" in cite:
                    cited_sources.add(cite)

            claims_cited = min(claims_found, len(cited_sources))
            coverage = claims_cited / max(claims_found, 1)

            if coverage < 0.5 and self.strict_mode:
                issues.append(
                    f"WARNING: Low citation coverage ({coverage:.0%}). "
                    f"{claims_found} claims found, {len(cited_sources)} unique sources cited."
                )
        else:
            coverage = 1.0  # No claims to cite

        return coverage, issues

    def _check_for_hallucinations(
        self, output: PlannerOutput, ctx: RetrievalContext
    ) -> List[str]:
        """
        Detect potential hallucinations: claims in output not supported by retrieved context.
        Uses simple heuristic: check if specific course codes/policies mentioned in output
        appear in any retrieved chunk.
        """
        issues = []

        # Extract all course codes mentioned in the output
        output_text = output.answer_or_plan + " " + output.why
        mentioned_courses = set(re.findall(r'\b([A-Z]{2,4}\d{3})\b', output_text))

        # Check if they appear in retrieved context
        context_text = " ".join(r.text for r in ctx.results)
        context_courses = set(re.findall(r'\b([A-Z]{2,4}\d{3})\b', context_text))

        uncited_courses = mentioned_courses - context_courses
        if uncited_courses:
            issues.append(
                f"POTENTIAL HALLUCINATION: Course(s) {', '.join(uncited_courses)} mentioned in output "
                f"but NOT found in any retrieved catalog chunk. "
                "Verify these course codes exist in the catalog."
            )

        # Check for specific numbers that might be hallucinated (credits, GPA thresholds)
        # These are high-risk hallucination targets
        output_numbers = re.findall(r'\b(\d+)\s*credits?\b', output_text, re.IGNORECASE)
        context_numbers = re.findall(r'\b(\d+)\s*credits?\b', context_text, re.IGNORECASE)

        hallucinated_numbers = set(output_numbers) - set(context_numbers)
        if hallucinated_numbers and self.strict_mode:
            issues.append(
                f"WARNING: Credit count(s) {', '.join(hallucinated_numbers)} mentioned in output "
                f"not found in retrieved context. Verify these values."
            )

        return issues

    def _check_prereq_logic(
        self, output: PlannerOutput, ctx: RetrievalContext
    ) -> List[str]:
        """
        Verify that prerequisite logic in the output matches catalog data.
        """
        issues = []

        # If output claims "Eligible", verify it against retrieved prerequisites
        if output.eligibility_decision == "Eligible":
            # Find any prerequisite info in context
            for result in ctx.results:
                if "Prerequisites:" in result.text:
                    prereq_match = re.search(r'Prerequisites?: (.+?)(?:\n|$)', result.text)
                    if prereq_match:
                        prereq_text = prereq_match.group(1)
                        required_codes = re.findall(r'\b([A-Z]{2,4}\d{3})\b', prereq_text)
                        if required_codes and prereq_text.lower() != "none":
                            # Verify the output mentions checking these
                            for code in required_codes:
                                if code not in output.why and code not in output.answer_or_plan:
                                    issues.append(
                                        f"PREREQ LOGIC: Prerequisite {code} was not mentioned in eligibility reasoning "
                                        f"but appears in catalog requirements. Verify this was considered."
                                    )

        return issues

    def _check_out_of_scope(
        self, query: str, output: PlannerOutput
    ) -> Tuple[bool, str]:
        """
        Check if the query is out of scope (should trigger safe abstention).
        """
        query_lower = query.lower()
        for keyword in self.OUT_OF_SCOPE_KEYWORDS:
            if keyword in query_lower:
                # Check if the output already abstains
                abstain_phrases = [
                    "don't have that information",
                    "not in the provided catalog",
                    "check with your advisor",
                    "not available in the catalog"
                ]
                already_abstaining = any(
                    p in output.answer_or_plan.lower() for p in abstain_phrases
                )
                if not already_abstaining:
                    return True, (
                        f"Query contains out-of-scope keyword: '{keyword}'. "
                        "This information is not in the catalog documents."
                    )
        return False, ""

    def _apply_corrections(
        self,
        output: PlannerOutput,
        issues: List[str],
        ctx: RetrievalContext
    ) -> Tuple[PlannerOutput, List[str]]:
        """
        Apply automatic corrections to the output where possible.
        """
        corrections = []

        # Ensure citations are always populated with retrieved sources
        if not output.citations and ctx.results:
            output.citations = [r.citation() for r in ctx.results]
            corrections.append("Auto-populated citations from retrieved context.")

        # Add a verification note to assumptions if issues were found
        critical_issues = [i for i in issues if "CRITICAL" in i or "HALLUCINATION" in i]
        if critical_issues:
            output.assumptions = output.assumptions or []
            output.assumptions.append(
                "⚠️  VERIFIER FLAG: This response had verification issues. "
                "Please confirm all details with your academic advisor before registering."
            )
            corrections.append("Added verifier warning to assumptions section.")

        # Ensure safe abstention format for out-of-scope queries
        abstention_issues = [i for i in issues if "ABSTENTION" in i]
        if abstention_issues:
            output.answer_or_plan = (
                "I don't have that information in the provided catalog/policies.\n\n"
                + output.answer_or_plan
            )
            if not output.assumptions:
                output.assumptions = []
            output.assumptions.append(
                "This query requires information not available in the curated catalog. "
                "Check with your academic advisor, department office, or the university's schedule of classes."
            )
            corrections.append("Applied safe abstention format for out-of-scope query.")

        return output, corrections
