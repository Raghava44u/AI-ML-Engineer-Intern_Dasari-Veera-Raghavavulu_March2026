import os
import json
import time
from typing import List, Dict, Any
from loguru import logger

# 25 TEST QUERIES (Normalized for MIT Catalog with complete student profiles)
TEST_QUERIES = [
    # ── 1. Prerequisite Checks (10) ──
    {
        "id": "PR-01",
        "category": "prereq_check",
        "query": "Can I take 6.1210 if I completed 6.100A?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Not Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-02",
        "category": "prereq_check",
        "query": "Am I eligible for 6.1020? I've finished 6.1010.",
        "student_info": {"completed_courses": ["6.1010", "6.1210", "6.1200", "6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-03",
        "category": "prereq_check",
        "query": "Can I enroll in 6.1220[J] if I took 6.1210 and 6.1200?",
        "student_info": {"completed_courses": ["6.1210", "6.1200", "18.01"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-04",
        "category": "prereq_check",
        "query": "Check eligibility for 6.1200[J]. I have 18.01.",
        "student_info": {"completed_courses": ["18.01"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-05",
        "category": "prereq_check",
        "query": "Can I take 18.02 after finishing 18.01?",
        "student_info": {"completed_courses": ["18.01"], "target_program": "MIT Course 18", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-06",
        "category": "prereq_check",
        "query": "Am I ready for 6.1010? I haven't taken any CS classes yet.",
        "student_info": {"completed_courses": [], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Not Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-07",
        "category": "prereq_check",
        "query": "Can I take 6.1800? I have 6.1910, 6.1210 and 6.1020.",
        "student_info": {"completed_courses": ["6.1910", "6.1210", "6.1020", "6.100A", "6.1200"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-08",
        "category": "prereq_check",
        "query": "Is 18.06 accessible if I have 18.02?",
        "student_info": {"completed_courses": ["18.02"], "target_program": "MIT Course 18", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-09",
        "category": "prereq_check",
        "query": "Can I take 6.3900 if I have 6.100A, 6.1210 and 18.06?",
        "student_info": {"completed_courses": ["6.100A", "6.1210", "18.06", "18.02"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "PR-10",
        "category": "prereq_check",
        "query": "Prerequisite check for 6.1910. I have 6.100A and 8.02.",
        "student_info": {"completed_courses": ["6.100A", "8.02"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Eligible",
        "is_out_of_scope": False
    },

    # ── 2. Multi-step Prerequisite Chains (5) ──
    {
        "id": "CH-01",
        "category": "prereq_chain",
        "query": "What is the full prerequisite chain for 6.1210?",
        "student_info": {"completed_courses": [], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Not Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "CH-02",
        "category": "prereq_chain",
        "query": "In what order should I take courses to reach 6.1800?",
        "student_info": {"completed_courses": [], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Not Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "CH-03",
        "category": "prereq_chain",
        "query": "Show me the path to 6.1020 starting from 6.100A.",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Not Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "CH-04",
        "category": "prereq_chain",
        "query": "What do I need to complete before I can take 6.4310?",
        "student_info": {"completed_courses": [], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Not Eligible",
        "is_out_of_scope": False
    },
    {
        "id": "CH-05",
        "category": "prereq_chain",
        "query": "Give me the sequence of courses to reach 6.046 for the Algorithms track.",
        "student_info": {"completed_courses": [], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "Not Eligible",
        "is_out_of_scope": False
    },

    # ── 3. Program Requirements (5) ──
    {
        "id": "PG-01",
        "category": "program_req",
        "query": "What are the core requirements for the MIT Course 6-3 major?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "N/A",
        "is_out_of_scope": False
    },
    {
        "id": "PG-02",
        "category": "program_req",
        "query": "How many units are required to graduate with a 6-3 degree?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "N/A",
        "is_out_of_scope": False
    },
    {
        "id": "PG-03",
        "category": "program_req",
        "query": "Does 6.1200 count towards the Math requirement for CS?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "N/A",
        "is_out_of_scope": False
    },
    {
        "id": "PG-04",
        "category": "program_req",
        "query": "What core courses are required for Course 18 (Mathematics)?",
        "student_info": {"completed_courses": ["18.01"], "target_program": "MIT Course 18", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "N/A",
        "is_out_of_scope": False
    },
    {
        "id": "PG-05",
        "category": "program_req",
        "query": "Is there a senior capstone requirement for degree?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": "N/A",
        "is_out_of_scope": False
    },

    # ── 4. Tricky / Out of Scope (5) ──
    {
        "id": "TS-01",
        "category": "tricky",
        "query": "Which professor is teaching 6.1210 next semester?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": None,
        "is_out_of_scope": True
    },
    {
        "id": "TS-02",
        "category": "tricky",
        "query": "What is the room number for the 18.01 lecture?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": None,
        "is_out_of_scope": True
    },
    {
        "id": "TS-03",
        "category": "tricky",
        "query": "How much does it cost to audit a course at MIT?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": None,
        "is_out_of_scope": True
    },
    {
        "id": "TS-04",
        "category": "tricky",
        "query": "Is there a waitlist for 6.1020 right now?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": None,
        "is_out_of_scope": True
    },
    {
        "id": "TS-05",
        "category": "tricky",
        "query": "What is the deadline for financial aid applications?",
        "student_info": {"completed_courses": ["6.100A"], "target_program": "MIT Course 6-3", "target_term": "Fall 2026", "max_credits": 48},
        "expected_decision": None,
        "is_out_of_scope": True
    }
]

class Evaluator:
    def __init__(self, pipeline, output_dir="evaluation/results"):
        self.pipeline = pipeline
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def run_evaluation(self, queries: List[Dict[str, Any]]):
        logger.info(f"STARTING EVALUATION: {len(queries)} cases")
        full_results = []
        
        # Separate counters for proper denominator calculation
        prereq_total = 0
        prereq_correct = 0
        abstention_total = 0
        abstention_correct = 0
        program_total = 0
        program_answered = 0  # Did we give a real answer (not "couldn't find course code")?
        total_coverage = 0.0
        
        category_stats = {}

        for q in queries:
            try:
                start_time = time.time()
                result = self.pipeline.run(q["query"], q["student_info"], verbose=False)
                latency = time.time() - start_time

                # Initialize category stats
                cat = q["category"]
                if cat not in category_stats:
                    category_stats[cat] = {"total": 0, "correct": 0, "coverage": 0.0}
                category_stats[cat]["total"] += 1

                # Metrics calculation based on category
                passed = False
                abstention_hit = False
                
                if q["is_out_of_scope"]:
                    # Out-of-scope query: check for proper abstention
                    abstention_total += 1
                    refusal_keywords = [
                        "don't have that information", 
                        "not in the provided catalog",
                        "out of scope",
                        "not contained in the curated",
                        "not available in the catalog"
                    ]
                    output_lower = result["formatted_output"].lower()
                    if any(kw in output_lower for kw in refusal_keywords):
                        abstention_hit = True
                        abstention_correct += 1
                        passed = True
                    
                elif q["expected_decision"] == "N/A":
                    # Program requirement: check we gave a substantive answer
                    program_total += 1
                    output = result["formatted_output"]
                    # Fail if we just said "couldn't identify a course code"
                    if "couldn't identify a course code" not in output.lower():
                        program_answered += 1
                        passed = True
                    
                else:
                    # Prerequisite check or chain: check decision
                    prereq_total += 1
                    actual = result.get("eligibility_decision")
                    if str(actual) == str(q["expected_decision"]):
                        prereq_correct += 1
                        passed = True

                if passed:
                    category_stats[cat]["correct"] += 1

                coverage = result.get("citation_coverage", 0.0)
                total_coverage += coverage
                category_stats[cat]["coverage"] += coverage

                full_results.append({
                    "case": q,
                    "actual_decision": result.get("eligibility_decision"),
                    "passed": passed,
                    "abstention_hit": abstention_hit,
                    "coverage": coverage,
                    "latency": latency,
                    "formatted_output": result["formatted_output"]
                })
                
                # Log individual result
                status = "✅ PASS" if passed else "❌ FAIL"
                logger.info(f"  {q['id']} [{cat}] {status} | decision={result.get('eligibility_decision')} expected={q['expected_decision']}")
                
            except Exception as e:
                logger.error(f"EVAL FAILURE on {q['id']}: {e}")
                import traceback
                traceback.print_exc()

        # Summary calculations
        total_correct = prereq_correct + abstention_correct + program_answered
        total_queries = len(queries)
        
        summary = {
            "total_queries": total_queries,
            "total_correct": total_correct,
            "overall_accuracy": total_correct / total_queries if total_queries > 0 else 0,
            "prereq_accuracy": prereq_correct / prereq_total if prereq_total > 0 else 0,
            "prereq_correct": prereq_correct,
            "prereq_total": prereq_total,
            "abstention_accuracy": abstention_correct / abstention_total if abstention_total > 0 else 0,
            "abstention_correct": abstention_correct,
            "abstention_total": abstention_total,
            "program_accuracy": program_answered / program_total if program_total > 0 else 0,
            "program_answered": program_answered,
            "program_total": program_total,
            "citation_coverage_avg": total_coverage / total_queries if total_queries > 0 else 0,
            "category_breakdown": {}
        }
        
        for cat, stats in category_stats.items():
            summary["category_breakdown"][cat] = {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
                "avg_coverage": stats["coverage"] / stats["total"] if stats["total"] > 0 else 0
            }

        # Save files
        with open(os.path.join(self.output_dir, "full_results.json"), "w", encoding="utf-8") as f:
            json.dump(full_results, f, indent=2, ensure_ascii=False)
        with open(os.path.join(self.output_dir, "evaluation_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info(f"EVALUATION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Overall Accuracy:     {summary['overall_accuracy']:.1%} ({total_correct}/{total_queries})")
        logger.info(f"Prereq Accuracy:      {summary['prereq_accuracy']:.1%} ({prereq_correct}/{prereq_total})")
        logger.info(f"Abstention Accuracy:  {summary['abstention_accuracy']:.1%} ({abstention_correct}/{abstention_total})")
        logger.info(f"Program Accuracy:     {summary['program_accuracy']:.1%} ({program_answered}/{program_total})")
        logger.info(f"Citation Coverage:    {summary['citation_coverage_avg']:.1%}")
        logger.info(f"{'='*60}")

        return summary
