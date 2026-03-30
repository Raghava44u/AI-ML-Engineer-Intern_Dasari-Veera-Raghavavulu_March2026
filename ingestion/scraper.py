import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cli_utils import safe_print as print

# Note: built-in print is shadowed here for cross-platform Unicode safety.

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')

# Ensure directories exist
os.makedirs(RAW_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_prerequisites_advanced(text):
    """
    Extracts prerequisites using robust regex matching.
    Supports patterns like Prereq:, Recommended:, Permission of instructor, etc.
    """
    if not text:
        return None
        
    # Priority 1: Explicit labels with colon
    # Ex: "Prereq: 6.100A", "Prerequisites: Physics I", "Recommended: 18.01"
    labels_pattern = r'(?:Prereq|Prerequisite|Prerequisites|Recommended|Coreq|Corequisite|Co-requisite):\s*(.*?)(?:\nUnits:|\nCredit cannot|\. [A-Z]|URL:|$)'
    match = re.search(labels_pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        content = match.group(1).strip()
        # Clean up trailing punctuation or newlines
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'[.;]$', '', content)
        return content

    # Priority 2: Permission/Consent phrases
    permission_patterns = [
        r"permission of (?:the )?instructor",
        r"instructor consent",
        r"department approval"
    ]
    for pattern in permission_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            # Extract the sentence or phrase
            phrase_match = re.search(r'([^.]*' + pattern + r'[^.]*)', text, re.IGNORECASE)
            if phrase_match:
                return phrase_match.group(1).strip()
            return "Permission of instructor required"

    # Priority 3: Embedded course codes (heuristic)
    # If we see course codes and "must have" or "required" or "preparation"
    if any(word in text.lower() for word in ["required", "must have", "preparation", "background"]):
        codes = re.findall(r'\b(?:[A-Z]{2,4}\d{3}|\d+\.[0-9A-Z]+)\b', text)
        if codes:
            return f"Required: {', '.join(codes)}"

    # Priority 4: Default fallback for MIT style "None" 
    if "none" in text.lower() and len(text) < 15:
        return "None"
        
    return None

def scrape_stanford_courses():
    print("Scraping Stanford CS courses...")
    courses = []
    # Scraping first page
    url = "https://explorecourses.stanford.edu/search?view=catalog&filter-coursestatus-Active=on&page=0&catalog=&q=CS"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        
        course_blocks = soup.find_all("div", class_="courseInfo")
        for block in course_blocks:
            title_el = block.find("h2")
            if not title_el:
                continue
            title_text = title_el.text.strip()
            # typically "CS 106A: Programming Methodology"
            parts = title_text.split(":", 1)
            course_id = parts[0].strip() if len(parts) > 0 else ""
            title = parts[1].strip() if len(parts) > 1 else title_text
            
            desc_el = block.find("div", class_="courseDescription")
            description = desc_el.text.strip() if desc_el else ""
            
            attrs_el = block.find("div", class_="courseAttributes")
            attrs_text = attrs_el.text if attrs_el else ""
            
            # Prereqs often in description or attributes
            prereqs = ""
            if "Prerequisite" in description:
                prer_idx = description.find("Prerequisite")
                prereqs = description[prer_idx:]
            
            # Extract units from attributes text: e.g. "Units: 3-5"
            credits = ""
            units_match = re.search(r'Units:\s*([\d\-]+)', attrs_text)
            if units_match:
                credits = units_match.group(1)
            
            grading = ""
            grading_match = re.search(r'Grading:\s*([^|]+)', attrs_text)
            if grading_match:
                grading = grading_match.group(1).strip()
            
            courses.append({
                "course_id": course_id,
                "title": title,
                "credits": credits,
                "description": description,
                "prerequisites": prereqs,
                "co_requisites": "",
                "department": "Computer Science (Stanford)",
                "grading_rules": grading,
                "source_url": url,
                "date_accessed": datetime.now().isoformat()
            })
    except Exception as e:
        print(f"Error scraping Stanford: {e}")
        
    return courses

def scrape_mit_courses():
    print("Scraping MIT Course 6 and 18 courses...")
    courses = []
    urls = [
        "http://student.mit.edu/catalog/m6a.html",
        "http://student.mit.edu/catalog/m6b.html",
        "http://student.mit.edu/catalog/m6c.html",
        "http://student.mit.edu/catalog/m18a.html",
        "http://student.mit.edu/catalog/m18b.html"
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.content, "html.parser")
            
            for h3 in soup.find_all("h3"):
                title_text = h3.text.strip()
                parts = title_text.split(" ", 1)
                if len(parts) < 2: continue
                course_id, title = parts[0].strip(), parts[1].strip()
                
                desc_texts = []
                node = h3.next_sibling
                units = ""
                while node and node.name != 'h3':
                    if node.name == 'p' or getattr(node, 'text', None):
                        text = clean_text(getattr(node, 'text', str(node)))
                        if text:
                            desc_texts.append(text)
                            if "Units:" in text or "U (" in text:
                                units = text
                    node = node.next_sibling
                
                full_text = "\n".join(desc_texts)
                prereqs = extract_prerequisites_advanced(full_text)
                
                courses.append({
                    "course_id": course_id,
                    "title": title,
                    "credits": units[:50],
                    "description": full_text[:1000],
                    "prerequisites": prereqs if prereqs else "None",
                    "co_requisites": "",
                    "department": "EECS/Math (MIT)",
                    "source_url": url,
                    "date_accessed": datetime.now().isoformat()
                })
        except Exception as e:
            print(f"Error scraping MIT {url}: {e}")
    return courses

def scrape_ucb_courses():
    print("Scraping UC Berkeley Courses...")
    courses = []
    # UC Berkeley typically requires dynamic scraping or API. Using a public endpoint or hardcoded catalog structure.
    # For now we'll just pull a couple from Berkeley engineering guide or similar text endpoint.
    # UCB Guide html:
    url = "https://guide.berkeley.edu/courses/compsci/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        
        course_blocks = soup.find_all("div", class_="courseblock")
        for block in course_blocks[:10]: # take first 10 to add to dataset
            title_el = block.find("span", class_="title")
            code_el = block.find("span", class_="code")
            hours_el = block.find("span", class_="hours")
            desc_el = block.find("div", class_="courseblockdesc")
            
            course_id = code_el.text.strip() if code_el else ""
            title = title_el.text.strip() if title_el else ""
            credits = hours_el.text.strip() if hours_el else ""
            description = desc_el.text.strip() if desc_el else ""
            
            prereqs = extract_prerequisites_advanced(description)
            
            courses.append({
                "course_id": course_id,
                "title": title,
                "credits": credits,
                "description": description,
                "prerequisites": prereqs if prereqs else "None",
                "co_requisites": "",
                "department": "Computer Science (UC Berkeley)",
                "source_url": url,
                "date_accessed": datetime.now().isoformat()
            })
    except Exception as e:
        print(f"Error scraping UCB: {e}")
        
    return courses


def scrape_programs():
    print("Scraping Programs...")
    programs = []
    
    # Stanford Program
    url1 = "https://cs.stanford.edu/academics/undergraduate"
    try:
        resp = requests.get(url1, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        text = clean_text(soup.get_text())
        programs.append({
            "program_name": "Stanford CS Undergraduate",
            "total_credits_required": "See Description",
            "core_courses": "CS 106B, CS 107, CS 109, CS 111, CS 161",
            "elective_requirements": "Track requirements apply",
            "description": text[:2000],
            "source_url": url1,
            "date_accessed": datetime.now().isoformat()
        })
    except:
        pass
        
    # MIT Program
    url2 = "http://catalog.mit.edu/degree-charts/computer-science-engineering-course-6-3/"
    try:
        resp = requests.get(url2, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        table = soup.find("table", class_="sc_courselist")
        core_courses = []
        if table:
            for row in table.find_all("tr"):
                code = row.find("td", class_="codecol")
                if code:
                    core_courses.append(code.text.strip())
        description = clean_text(soup.get_text())[:2000]
        
        programs.append({
            "program_name": "MIT Course 6-3 (Computer Science)",
            "total_credits_required": "180-192 units",
            "core_courses": ", ".join(core_courses[:10]) + ("..." if len(core_courses)>10 else ""),
            "elective_requirements": "Restricted and Unrestricted electives",
            "description": description,
            "source_url": url2,
            "date_accessed": datetime.now().isoformat()
        })
    except:
        pass

    # BITS Pilani Program
    url3 = "https://www.bits-pilani.ac.in/goa/computer-science/academics/"
    try:
        resp = requests.get(url3, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        content_text = clean_text(soup.get_text())[:2000]
        
        programs.append({
            "program_name": "BITS Pilani CS Academics",
            "total_credits_required": "Varies by degree",
            "core_courses": "Data Structures, Algorithms",
            "elective_requirements": "Humanities, Disciplinary Electives",
            "description": content_text,
            "source_url": url3,
            "date_accessed": datetime.now().isoformat()
        })
    except:
        pass
        
    return programs

def scrape_policies():
    print("Scraping Policies...")
    policies = []
    
    # MIT Policies
    url1 = "https://catalog.mit.edu/mit/procedures/academic-performance/"
    try:
        resp = requests.get(url1, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        content = soup.find("div", id="content")
        text = clean_text(content.get_text()) if content else clean_text(soup.get_text())
        
        policies.append({
            "policy_id": "MIT_Academic_Performance",
            "title": "MIT Academic Performance Policy",
            "grading_rules": "A, B, C, D, F. Plus/minus modifiers.",
            "repeat_policies": "Can repeat for grade replacements under certain rules.",
            "credit_limits": "Varies per semester, usually up to 54-60 units.",
            "description": text[:3000],
            "source_url": url1,
            "date_accessed": datetime.now().isoformat()
        })
    except:
        pass
        
    # Stanford Policies
    url2 = "https://registrar.stanford.edu/students/grades-and-grading-policies"
    try:
        resp = requests.get(url2, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        text = clean_text(soup.get_text())
        
        policies.append({
            "policy_id": "Stanford_Grading_Policies",
            "title": "Stanford Grades and Grading Policies",
            "grading_rules": "A, B, C, D, NP, CR/NC",
            "repeat_policies": "Repeated courses do not accumulate duplicate units toward graduation.",
            "exceptions": "Instructor consent required for exceptions.",
            "description": text[:3000],
            "source_url": url2,
            "date_accessed": datetime.now().isoformat()
        })
    except:
        pass
        
    return policies

def main():
    print("Starting scraping process...")
    
    courses = []
    courses.extend(scrape_stanford_courses())
    courses.extend(scrape_mit_courses())
    courses.extend(scrape_ucb_courses())
    
    programs = scrape_programs()
    policies = scrape_policies()
    
    # Save to JSON
    with open(os.path.join(RAW_DIR, 'courses.json'), 'w', encoding='utf-8') as f:
        json.dump({"courses": courses}, f, indent=4, ensure_ascii=False)
        
    # Ingest expects "program" to be a single program, or we can use "programs" if ingest.py is adapted. 
    # Actually, ingest.py expects "program" to be a dict. Let's save each program in a separate file, or adapt.
    # To be safe against ingest.py structure:
    for i, prog in enumerate(programs):
        with open(os.path.join(RAW_DIR, f'program_{i}.json'), 'w', encoding='utf-8') as f:
            json.dump({"program": prog}, f, indent=4, ensure_ascii=False)
        
    with open(os.path.join(RAW_DIR, 'policies.json'), 'w', encoding='utf-8') as f:
        json.dump({"policies": policies}, f, indent=4, ensure_ascii=False)
        
    print(f"Scraping complete!")
    print(f"Total Courses: {len(courses)}")
    print(f"Total Programs: {len(programs)}")
    print(f"Total Policies: {len(policies)}")

if __name__ == "__main__":
    main()
