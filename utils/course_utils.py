import re
from typing import List

# Updated for MIT style: 6.1210, 6.1210[J], 6.100A, 18.01, CS106B
COURSE_REGEX = r'(?:[A-Z]{1,5}\d+[A-Z]*|\d+\.[A-Z0-9]+(?:\[[A-Z]\])?)'
# Use more flexible boundary that allows brackets
COURSE_BOUNDED_REGEX = COURSE_REGEX

# Map GIR (General Institute Requirements) to actual MIT course numbers
GIR_MAP = {
    "calculus i (gir)": ["18.01", "18.01A"],
    "calculus i": ["18.01", "18.01A"],
    "calculus ii (gir)": ["18.02", "18.02A"],
    "calculus ii": ["18.02", "18.02A"],
    "physics i (gir)": ["8.01", "8.011", "8.012"],
    "physics i": ["8.01", "8.011", "8.012"],
    "physics ii (gir)": ["8.02", "8.021", "8.022"],
    "physics ii": ["8.02", "8.021", "8.022"],
    "biology (gir)": ["7.012", "7.013", "7.014", "7.015", "7.016"],
    "chemistry (gir)": ["5.111", "5.112", "3.091"],
}


def extract_course_codes(query: str) -> List[str]:
    """
    Robustly extracts course codes from a string (query or catalog text).
    
    Supports:
    - Alpha-Numeric: CS301, MATH201, CS106B
    - MIT Style: 6.1210, 18.01, 6.100A, 6.006, 6.046
    - MIT Style with brackets: 6.1220[J], 6.1200[J]
    
    Normalization: 
    - Forced to UPPERCASE
    - Unique-fied
    """
    if not query:
        return []

    findings = re.findall(COURSE_BOUNDED_REGEX, query.upper())
    
    # Return unique, sorted list
    return sorted(list(set(findings)))


def normalize_course_id(course_id: str) -> str:
    """Normalize a course ID by stripping bracket suffixes for matching.
    E.g., '6.1220[J]' -> '6.1220'
    """
    return re.sub(r'\[[A-Z]\]$', '', course_id.strip())


def course_ids_match(id1: str, id2: str) -> bool:
    """Check if two course IDs refer to the same course (ignoring [J] suffixes)."""
    return normalize_course_id(id1) == normalize_course_id(id2)


def gir_satisfied(gir_text: str, completed_courses: set) -> bool:
    """Check if a GIR requirement is satisfied by any completed course."""
    gir_lower = gir_text.lower().strip()
    for gir_key, course_list in GIR_MAP.items():
        if gir_key in gir_lower:
            return any(c in completed_courses for c in course_list)
    return False


def get_course_code_help_message() -> str:
    """Helper for guiding user when no course is found."""
    return "Please include a valid course code such as 'CS301' or '6.1210' in your query."
