"""
agents/intake_agent.py
-----------------------
Intake Agent: Collects and normalizes student information before planning.

RESPONSIBILITIES:
  1. Parse student-provided information from free-text or structured input
  2. Identify what's missing (major, completed courses, grades, credit limit, term)
  3. Generate 1-5 clarifying questions for missing fields
  4. Normalize the student profile for downstream agents

This agent runs FIRST in the pipeline. If info is incomplete, it stops
and returns clarifying questions before any retrieval or planning occurs.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from loguru import logger
from utils.course_utils import extract_course_codes


@dataclass
class StudentProfile:
    """
    Normalized student profile for course planning.
    None = not provided (will trigger clarifying questions).
    """
    completed_courses: Optional[List[str]] = None    # e.g., ["CS101", "CS102", "MATH101"]
    grades: Optional[Dict[str, str]] = None          # e.g., {"CS101": "A", "MATH101": "B+"}
    target_program: Optional[str] = None             # e.g., "BS Computer Science"
    target_term: Optional[str] = None                # e.g., "Fall 2025"
    max_credits: Optional[int] = None                # e.g., 15
    catalog_year: Optional[str] = None               # e.g., "2024-2025"
    transfer_credits: Optional[List[str]] = None     # e.g., ["MATH101 (transfer)"]
    current_credits_earned: Optional[int] = None     # Total earned credits so far
    gpa: Optional[float] = None                      # Cumulative GPA

    def is_complete_for_planning(self) -> bool:
        """Returns True only if all required fields for planning are present."""
        return (
            self.completed_courses is not None
            and self.target_program is not None
            and self.target_term is not None
            and self.max_credits is not None
        )

    def summary(self) -> str:
        """Human-readable profile summary."""
        lines = ["=== Student Profile ==="]
        lines.append(f"Target Program: {self.target_program or 'NOT PROVIDED'}")
        lines.append(f"Target Term: {self.target_term or 'NOT PROVIDED'}")
        lines.append(f"Max Credits: {self.max_credits or 'NOT PROVIDED'}")
        lines.append(f"Catalog Year: {self.catalog_year or '2024-2025 (assumed)'}")
        if self.completed_courses:
            lines.append(f"Completed Courses ({len(self.completed_courses)}): {', '.join(self.completed_courses)}")
        else:
            lines.append("Completed Courses: NOT PROVIDED")
        if self.grades:
            grade_str = ", ".join(f"{k}:{v}" for k, v in self.grades.items())
            lines.append(f"Grades: {grade_str}")
        if self.gpa:
            lines.append(f"Cumulative GPA: {self.gpa}")
        if self.current_credits_earned:
            lines.append(f"Credits Earned: {self.current_credits_earned}")
        return "\n".join(lines)


class IntakeAgent:
    """
    Intake Agent: validates and completes student profile before planning.

    If profile is incomplete → returns clarifying questions (list of strings).
    If profile is complete → returns validated StudentProfile.
    """

    REQUIRED_FIELDS = ["completed_courses", "target_program", "target_term", "max_credits"]
    CLARIFYING_QUESTIONS = {
        "completed_courses": (
            "Which courses have you already completed? "
            "Please list course codes (e.g., CS101, MATH101, CS102)."
        ),
        "target_program": (
            "What is your target degree program? "
            "(e.g., BS Computer Science, MS Computer Science, Data Science Minor)"
        ),
        "target_term": (
            "Which term are you planning for? "
            "(e.g., Fall 2025, Spring 2026)"
        ),
        "max_credits": (
            "What is the maximum number of credits you want to take next semester? "
            "(Standard full-time is 12-18 credits; default is 15 if not specified)"
        ),
        "catalog_year": (
            "Which catalog year are you following? "
            "(e.g., 2024-2025 — this affects which requirements apply to you)"
        ),
        "grades": (
            "Do you have grades for your completed courses? "
            "Some courses require minimum grades (e.g., C or better) for their prerequisites. "
            "If you know them, please share. If not, we'll note this assumption."
        ),
        "gpa": (
            "What is your current cumulative GPA? "
            "This affects eligibility for overload registration and tracks your academic standing."
        ),
        "current_credits_earned": (
            "How many total credits have you earned so far? "
            "This determines your class standing (junior/senior) and capstone eligibility."
        )
    }

    def __init__(self, require_grades: bool = False, require_catalog_year: bool = False):
        self.require_grades = require_grades
        self.require_catalog_year = require_catalog_year

    def process(self, raw_input: Dict) -> Dict:
        """
        Main entry point. Accepts a dict of student info.

        Returns:
          {
            "status": "complete" | "needs_clarification",
            "profile": StudentProfile,
            "clarifying_questions": [...],
            "warnings": [...]
          }
        """
        profile = self._parse_input(raw_input)
        questions = self._identify_missing(profile)
        warnings = self._validate_profile(profile)

        if questions:
            return {
                "status": "needs_clarification",
                "profile": profile,
                "clarifying_questions": questions,
                "warnings": warnings
            }
        else:
            return {
                "status": "complete",
                "profile": profile,
                "clarifying_questions": [],
                "warnings": warnings
            }

    def _parse_input(self, raw: Dict) -> StudentProfile:
        """Parse raw input dict into StudentProfile."""
        # Normalize course list — explicit None check to preserve empty lists
        completed = raw.get("completed_courses")
        if completed is None:
            completed = raw.get("courses_completed")
        if isinstance(completed, str):
            completed = extract_course_codes(completed)
        elif isinstance(completed, list):
            if len(completed) > 0:
                completed = [c.strip().upper() for c in completed]
                # Further normalize list items just in case
                completed = extract_course_codes(" ".join(completed))
            # else: completed stays as [] (valid: student has no courses)

        # Normalize grades
        grades = raw.get("grades") or {}
        if isinstance(grades, str):
            # Try to parse "CS101:A, MATH101:B+" format
            grades_dict = {}
            for part in grades.split(","):
                part = part.strip()
                if ":" in part:
                    k, v = part.split(":", 1)
                    grades_dict[k.strip().upper()] = v.strip()
            grades = grades_dict

        # Normalize max_credits
        max_credits = raw.get("max_credits") or raw.get("credit_limit")
        if isinstance(max_credits, str):
            try:
                max_credits = int(max_credits)
            except ValueError:
                max_credits = None

        # Normalize GPA
        gpa = raw.get("gpa")
        if isinstance(gpa, str):
            try:
                gpa = float(gpa)
            except ValueError:
                gpa = None

        credits_earned = raw.get("current_credits_earned") or raw.get("credits_earned")
        if isinstance(credits_earned, str):
            try:
                credits_earned = int(credits_earned)
            except ValueError:
                credits_earned = None

        return StudentProfile(
            completed_courses=completed if completed is not None else None,
            grades=grades if grades else None,
            target_program=raw.get("target_program") or raw.get("program") or raw.get("major"),
            target_term=raw.get("target_term") or raw.get("term"),
            max_credits=max_credits,
            catalog_year=raw.get("catalog_year", "2024-2025"),
            transfer_credits=raw.get("transfer_credits"),
            current_credits_earned=credits_earned,
            gpa=gpa
        )

    def _identify_missing(self, profile: StudentProfile) -> List[str]:
        """Return list of clarifying questions for missing required fields."""
        questions = []
        if profile.completed_courses is None:
            questions.append(self.CLARIFYING_QUESTIONS["completed_courses"])
        if profile.target_program is None:
            questions.append(self.CLARIFYING_QUESTIONS["target_program"])
        if profile.target_term is None:
            questions.append(self.CLARIFYING_QUESTIONS["target_term"])
        if profile.max_credits is None:
            questions.append(self.CLARIFYING_QUESTIONS["max_credits"])

        # Optional but recommended
        if self.require_grades and profile.grades is None:
            questions.append(self.CLARIFYING_QUESTIONS["grades"])

        # Cap at 5 questions per assessment requirement
        return questions[:5]

    def _validate_profile(self, profile: StudentProfile) -> List[str]:
        """Return warnings about potentially problematic profile data."""
        warnings = []

        if profile.max_credits and profile.max_credits > 18:
            warnings.append(
                f"Credit load of {profile.max_credits} exceeds normal maximum (18). "
                "Overload requires cumulative GPA ≥ 3.0 and advisor approval "
                "(Source: Academic Policies, Credit Load Limits)."
            )

        if profile.gpa and profile.gpa < 2.0:
            warnings.append(
                f"GPA of {profile.gpa} is below the minimum 2.0 required to remain in good standing. "
                "Student may be on academic probation "
                "(Source: Academic Policies, Academic Probation)."
            )

        if profile.completed_courses and profile.grades:
            for course, grade in profile.grades.items():
                if grade in ["D", "D-", "D+", "F"] and course in profile.completed_courses:
                    warnings.append(
                        f"Grade of {grade} in {course} is below the C minimum required "
                        "for most CS prerequisites. This course may need to be repeated "
                        "(Source: CS Program Requirements, Core Requirements)."
                    )

        return warnings

    def apply_defaults(self, profile: StudentProfile) -> StudentProfile:
        """Apply safe defaults for optional missing fields."""
        if profile.max_credits is None:
            profile.max_credits = 15
        if profile.catalog_year is None:
            profile.catalog_year = "2024-2025"
        if profile.grades is None:
            profile.grades = {}
        return profile
