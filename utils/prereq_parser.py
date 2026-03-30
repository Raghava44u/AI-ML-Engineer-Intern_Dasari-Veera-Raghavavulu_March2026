import re
import json
from typing import Dict, Any, List

class PrereqParser:
    """
    Parses and evaluates complex course prerequisite strings into an AST,
    and determines enrollment eligibility.
    
    FIXED: MIT comma-OR lists (e.g., "6.3700, 6.3800, 18.05, or 18.600" = ANY of these)
    """
    
    def __init__(self):
        pass

    def _tokenize(self, text: str) -> List[str]:
        # Basic cleanup
        text = text.replace('Prereq:', '').strip()
        
        # Handle MIT-style comma-separated OR lists
        # Pattern: "A , B , C , or D" means ANY of A/B/C/D
        # Pattern: "A , B , and C" means ALL of A/B/C
        
        def _expand_comma_or(m):
            """Given a comma-separated list ending in 'or', convert all commas to 'or'."""
            full = m.group(0)
            parts = re.split(r'\s*,\s*', full)
            clean_parts = []
            for p in parts:
                p = p.strip()
                if p.lower().startswith('or '):
                    p = p[3:].strip()
                clean_parts.append(p)
            return ' or '.join(clean_parts)
        
        # Match "A , B , ... , or Z" patterns (with course-code-like tokens)
        text = re.sub(
            r'(?:[\w.\[\]]+\s*,\s*)+or\s+[\w.\[\]]+',
            _expand_comma_or,
            text,
            flags=re.IGNORECASE
        )
        
        # Handle ", and " explicitly
        text = re.sub(r',\s*and\s+', ' and ', text, flags=re.IGNORECASE)
        
        # Remaining commas are AND by default (e.g., "6.1020, 6.1210, and 6.1910")
        text = text.replace(',', ' and ')
        
        # Pad parentheses for easy splitting
        text = text.replace('(', ' ( ').replace(')', ' ) ')
        
        raw_tokens = text.split()
        
        tokens = []
        current_course = []
        
        for word in raw_tokens:
            w_lower = word.lower()
            if w_lower in ('and', 'or', '(', ')'):
                if current_course:
                    tokens.append(' '.join(current_course))
                    current_course = []
                tokens.append(w_lower.upper() if w_lower in ('and', 'or') else word)
            else:
                current_course.append(word)
                
        if current_course:
            tokens.append(' '.join(current_course))
            
        return tokens

    def parse_ast(self, prereq_str: str) -> Dict[str, Any]:
        """
        Parses a prerequisite string into a JSON / Dictionary AST.
        """
        if not prereq_str or prereq_str.strip().lower() in ['none', '']:
            return {}

        tokens = self._tokenize(prereq_str)
        pos = [0] # Use list to pass by reference in nested functions

        def peek():
            if pos[0] < len(tokens):
                return tokens[pos[0]]
            return None

        def consume():
            t = peek()
            pos[0] += 1
            return t

        def parse_primary():
            t = peek()
            if t == '(':
                consume()
                node = parse_or()
                if peek() == ')':
                    consume()
                return node
            elif t is not None:
                consume()
                return {'type': 'COURSE', 'name': t}
            return None

        def parse_and():
            node = parse_primary()
            while peek() == 'AND':
                consume()
                right = parse_primary()
                if node and right:
                    node = {'type': 'AND', 'left': node, 'right': right}
            return node

        def parse_or():
            node = parse_and()
            while peek() == 'OR':
                consume()
                right = parse_and()
                if node and right:
                    node = {'type': 'OR', 'left': node, 'right': right}
            return node

        ast = parse_or()
        return ast if ast else {}

    def evaluate(self, ast: Dict[str, Any], completed_courses: set) -> Dict[str, Any]:
        """
        Evaluates the AST against a set of completed courses.
        Returns the overall status and structured missing requirements.
        """
        if not ast:
            return {"status": "Eligible", "missing": []}
            
        def eval_node(node) -> Dict[str, Any]:
            if node['type'] == 'COURSE':
                cname = node['name']
                cname_lower = cname.lower()
                
                # Check for Edge Cases requiring manual review (consent, instructor permission, etc.)
                if any(x in cname_lower for x in ["permission", "consent", "approval"]):
                    return {"met": False, "needs_info": True, "missing": [cname]}
                    
                # Direct check: does the student have this course?
                clean_cname = re.sub(r'\s*\(.*?\)', '', cname).strip()
                is_met = clean_cname in completed_courses
                
                # Also check without bracket suffix (e.g., 6.1220[J] match 6.1220)
                if not is_met:
                    stripped = re.sub(r'\[.*?\]$', '', clean_cname)
                    is_met = stripped in completed_courses
                    # Also check the reverse: student has "6.1220[J]" but we're looking for "6.1220"
                    if not is_met:
                        for comp in completed_courses:
                            if re.sub(r'\[.*?\]$', '', comp) == stripped:
                                is_met = True
                                break
                
                # Grade check logic (bonus extraction):
                grade_req = None
                grade_match = re.search(r'\((.*? or better)\)', cname, re.IGNORECASE)
                if grade_match:
                    grade_req = grade_match.group(1)
                
                missing_entry = cname
                if not is_met and grade_req:
                    missing_entry = f"{clean_cname} with {grade_req}"
                    
                return {"met": is_met, "needs_info": False, "missing": [] if is_met else [missing_entry]}
                
            elif node['type'] == 'AND':
                l_res = eval_node(node['left'])
                r_res = eval_node(node['right'])
                
                met = l_res['met'] and r_res['met']
                needs_info = l_res['needs_info'] or r_res['needs_info']
                missing = l_res['missing'] + r_res['missing']
                
                return {"met": met, "needs_info": needs_info, "missing": missing}
                
            elif node['type'] == 'OR':
                l_res = eval_node(node['left'])
                r_res = eval_node(node['right'])
                
                met = l_res['met'] or r_res['met']
                # If neither is met, we might need info if either side needs info
                needs_info = (not met) and (l_res['needs_info'] or r_res['needs_info'])
                
                if met:
                    return {"met": True, "needs_info": False, "missing": []}
                else:
                    return {"met": False, "needs_info": needs_info, "missing": [{"OR": [l_res['missing'], r_res['missing']]}]}
                    
            return {"met": False, "needs_info": False, "missing": []}

        result = eval_node(ast)
        
        status = "Not Eligible"
        if result['met']:
            status = "Eligible"
        elif result['needs_info']:
            status = "Need More Info"
            
        return {
            "status": status,
            "missing": result['missing']
        }

    def format_missing(self, missing_list: List[Any], indent=0) -> str:
        """
        Helper method to print the structured missing requirements in human-readable text.
        """
        lines = []
        spaces = "  " * indent
        for item in missing_list:
            if isinstance(item, str):
                lines.append(f"{spaces}- {item}")
            elif isinstance(item, dict) and 'OR' in item:
                lines.append(f"{spaces}- One of the following tracks:")
                for or_option in item['OR']:
                    if isinstance(or_option, list) and len(or_option) > 0:
                        lines.append(self.format_missing(or_option, indent + 1))
        return "\n".join(lines)


# Example usage demonstration
if __name__ == "__main__":
    parser = PrereqParser()
    
    # 1. MIT comma-or test
    expr = "6.100A and ( 6.1200 or ( 6.120A and ( 6.3700 , 6.3800 , 18.05 , or 18.600 )))"
    ast = parser.parse_ast(expr)
    print("----- AST -----")
    print(json.dumps(ast, indent=2))
    
    # Test with student who has 6.100A and 6.1200
    completed = {"6.100A", "6.1200"}
    eval_result = parser.evaluate(ast, completed)
    print(f"\nStatus with {{6.100A, 6.1200}}: {eval_result['status']}")
    assert eval_result['status'] == 'Eligible', f"Expected Eligible, got {eval_result['status']}"
    print("✓ PASSED")
    
    # Test with student who has only 6.100A
    completed2 = {"6.100A"}
    eval_result2 = parser.evaluate(ast, completed2)
    print(f"\nStatus with {{6.100A}}: {eval_result2['status']}")
    assert eval_result2['status'] == 'Not Eligible', f"Expected Not Eligible, got {eval_result2['status']}"
    print("✓ PASSED")
    
    # Test: "( 6.1010 or 6.1210 ) and ( 18.03 , 18.06 , 18.700 , or 18.C06 )"
    expr2 = "( 6.1010 or 6.1210 ) and ( 18.03 , 18.06 , 18.700 , or 18.C06 )"
    ast2 = parser.parse_ast(expr2)
    completed3 = {"6.100A", "18.06"}  # Has 18.06 (satisfies OR) but no 6.1010/6.1210
    eval_result3 = parser.evaluate(ast2, completed3)
    print(f"\nStatus with {{6.100A, 18.06}} for '{expr2}': {eval_result3['status']}")
    assert eval_result3['status'] == 'Not Eligible', f"Expected Not Eligible, got {eval_result3['status']}"
    print("✓ PASSED (missing 6.1010/6.1210)")
    
    # Now add 6.100A + 18.06 + no programming → still not eligible
    completed4 = {"6.100A", "18.06"}
    eval4 = parser.evaluate(ast2, completed4)
    print(f"\nStatus: {eval4['status']} — Missing: {parser.format_missing(eval4['missing'])}")
