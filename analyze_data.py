import json
import os
import re
from urllib.parse import urlparse

def analyze():
    # Resolve the data path relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "data", "raw", "courses.json")
    
    if not os.path.exists(data_path):
        print(f"Error: Dataset not found at {data_path}")
        return

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    courses = data.get("courses", [])
    num_courses = len(courses)
    
    if num_courses == 0:
        print("Dataset is empty.")
        return

    # Analyze Sources
    sources = set()
    departments = set()
    urls = set()
    for c in courses:
        if "source_url" in c:
            url = c["source_url"]
            urls.add(url)
            domain = urlparse(url).netloc
            if domain:
                sources.add(domain)
        if "department" in c:
            departments.add(c["department"])

    # Analyze Words
    total_words = 0
    desc_words = []
    for c in courses:
        # Combine title and description for word count roughly
        text = c.get("title", "") + " " + c.get("description", "")
        # Simple word count using regex
        w_count = len(re.findall(r'\b\w+\b', text))
        total_words += w_count
        desc_words.append(w_count)

    avg_words = total_words // num_courses
    max_words = max(desc_words) if desc_words else 0

    # Analyze Prerequisites
    has_prereq = 0
    no_prereq = 0
    for c in courses:
        p = c.get("prerequisites", "None").strip()
        if p.lower() in ["none", "", "()"]:
            no_prereq += 1
        else:
            has_prereq += 1

    # Output formatted statistics
    print("=========================================")
    print("         DATASET INFORMATION             ")
    print("=========================================\n")
    
    print(f"Total Courses: {num_courses}\n")
    
    print("--- 🌍 Data Collection Sources ---")
    print(f"Domains: {', '.join(sources) if sources else 'N/A'}")
    print(f"Unique URLs crawled: {len(urls)}")
    print(f"Departments covered: {', '.join(departments) if departments else 'N/A'}\n")
    
    print("--- 📝 Word & Text Statistics ---")
    print(f"Total Words (Title + Desc): {total_words:,}")
    print(f"Average Words per Course  : {avg_words}")
    print(f"Longest Course Description: {max_words} words\n")
    
    print("--- 🎓 Prerequisites ---")
    print(f"Courses WITH prerequisites   : {has_prereq}")
    print(f"Courses WITHOUT prerequisites: {no_prereq}\n")
    
    print("--- 📊 General Schema / All Info ---")
    print("Available metadata fields per course record:")
    sample = courses[0] if num_courses > 0 else {}
    for k in sample.keys():
        print(f"  - {k}")

if __name__ == "__main__":
    analyze()
