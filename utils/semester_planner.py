import os
import sys
import json
import re
from typing import List, Dict, Any, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.prereq_parser import PrereqParser
from utils.cli_utils import safe_print as print

# Note: built-in print is shadowed here for cross-platform Unicode safety.

class SemesterPlanner:
    def __init__(self, courses_data: List[Dict[str, Any]]):
        self.courses = courses_data
        self.parser = PrereqParser()
        
        # Pre-parse abstract syntax trees for performance
        self.course_asts = {}
        for course in self.courses:
            cid = course.get("course_id")
            prereq_str = course.get("prerequisites", "")
            self.course_asts[cid] = self.parser.parse_ast(prereq_str)

    def extract_credits(self, credit_str: str) -> int:
        """
        Extract numerical credits from string (e.g. 'Units: 3-0-9' -> 12, or '4' -> 4)
        """
        if not credit_str:
            return 3 # Default assumption if missing
            
        # MIT style: "Units: 3-0-9" (sum of components = 12)
        match = re.search(r'Units:\s*([\d]+)-([\d]+)-([\d]+)', credit_str)
        if match:
            return int(match.group(1)) + int(match.group(2)) + int(match.group(3))
            
        # Berkeley/Stanford style: "Units: 3" or flat digits
        nums = re.findall(r'\d+', credit_str)
        if nums:
            # Avoid picking up weird strings, grab the first digit if it matches typical credit sizes
            return int(nums[0])
            
        return 3

    def generate_plan(self, 
                      completed_courses: Set[str], 
                      core_requirements: Set[str], 
                      max_credits: int) -> Dict[str, Any]:
        """
        Generates a structured semester plan based on eligibility, prioritization, and constraints.
        """
        eligible_courses = []
        
        # 1. Filter eligible courses
        for course in self.courses:
            cid = course.get("course_id")
            if not cid or cid in completed_courses:
                continue # Skip invalid or already completed courses
                
            ast = self.course_asts.get(cid)
            eval_res = self.parser.evaluate(ast, completed_courses)
            
            # Strict eligibility (ignoring Need More Info/Permission cases for automated planning)
            if eval_res["status"] == "Eligible":
                eligible_courses.append(course)

        # 2. Score and prioritize courses
        # Priority logic: Core courses first, then higher credit courses
        def score_course(c):
            cid = c.get("course_id")
            is_core = cid in core_requirements
            c_credits = self.extract_credits(c.get("credits", ""))
            return (1 if is_core else 0, c_credits)

        eligible_courses.sort(key=score_course, reverse=True)

        # 3. Generate Semester Plan
        plan = []
        current_credits = 0
        
        for course in eligible_courses:
            c_credits = self.extract_credits(course.get("credits", ""))
            
            # Check if adding this course exceeds credit limits
            if current_credits + c_credits <= max_credits:
                cid = course.get("course_id")
                is_core = cid in core_requirements
                
                # 4. Add justification
                if is_core:
                    justification = f"Mandatory Core Requirement. All prerequisites met."
                else:
                    justification = f"Fulfills elective requirements. Prerequisites are met and fits schedule."
                    
                plan.append({
                    "course_id": cid,
                    "title": course.get("title", "").replace("\n", " ").strip(),
                    "credits": c_credits,
                    "justification": justification
                })
                current_credits += c_credits

            # Stop attempting to fill if we are at or near max capacity (e.g. 1-2 credits away)
            # Assuming smallest course is 1 credit.
            if current_credits == max_credits:
                break
                
        return {
            "completed_courses_analyzed": list(completed_courses),
            "semester_plan": plan,
            "total_credits": current_credits,
            "max_credits_allowed": max_credits
        }

if __name__ == "__main__":
    # Test script against the data/raw/courses.json we scraped earlier
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'raw')
    courses_file = os.path.join(data_dir, 'courses.json')
    
    if os.path.exists(courses_file):
        with open(courses_file, 'r', encoding='utf-8') as f:
            course_catalog = json.load(f)
            
        planner = SemesterPlanner(course_catalog)
        
        # Scenario: Student has completed 6.100A and 6.1200
        completed = {"6.100A", "6.1200"}
        
        # Target path: Needs 6.1210 and 6.1020 as core
        cores = {"6.1210", "6.1020", "6.1800"}
        
        try:
            # MIT max units is usually ~48-54
            plan_output = planner.generate_plan(
                completed_courses=completed,
                core_requirements=cores,
                max_credits=48 
            )
            
            with open('output_plan.json', 'w') as outf:
                json.dump(plan_output, outf, indent=2)
            print("Successfully wrote plan to output_plan.json")
        except Exception as e:
            with open('error.log', 'w') as f:
                import traceback
                f.write(traceback.format_exc())
    else:
        print(f"Could not find {courses_file}")
