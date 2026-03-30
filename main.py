#!/usr/bin/env python3
"""
main.py
--------
Main entry point for the RAG Course Planning Assistant.

Usage:
    python main.py build         # Build the FAISS index from catalog data
    python main.py demo          # Run sample queries
    python main.py eval          # Run evaluation suite (25 queries)
    python main.py interactive   # Interactive chat mode
    python main.py all           # Build + demo + eval
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from agents.pipeline import CourseAssistantPipeline
from utils.cli_utils import safe_print as print

# Note: built-in print is shadowed here for cross-platform Unicode safety.


def build(pipeline: CourseAssistantPipeline):
    """Build the FAISS index."""
    print("\n🔨 BUILDING INDEX...")
    stats = pipeline.build_index()
    print(f"\n✓ Index built successfully!")
    print(f"  Vectors:    {stats.get('total_vectors', 'N/A')}")
    print(f"  Dimension:  {stats.get('dimension', 'N/A')}")
    print(f"  By type:    {stats.get('chunks_by_type', {})}")
    return stats


def demo(pipeline: CourseAssistantPipeline):
    """Run sample demo queries."""
    print("\n🎯 RUNNING DEMO QUERIES...\n")

    demo_cases = [
        {
            "title": "DEMO 1: Prerequisite Check — ELIGIBLE",
            "query": "Can I take CS301 if I've completed CS201 and MATH201 (both with B grades)?",
            "student_info": {
                "completed_courses": ["CS101", "CS102", "MATH101", "MATH102", "MATH201", "CS201", "CS210"],
                "grades": {"CS201": "B", "MATH201": "B", "CS102": "B+"},
                "target_program": "BS Computer Science",
                "target_term": "Fall 2025",
                "max_credits": 15,
                "current_credits_earned": 60
            }
        },
        {
            "title": "DEMO 2: Prerequisite Check — NOT ELIGIBLE",
            "query": "Can I take CS360 (Machine Learning)? I have CS350 with a C grade and MATH210.",
            "student_info": {
                "completed_courses": ["CS101", "CS102", "CS201", "CS220", "CS350", "MATH210"],
                "grades": {"CS350": "C", "MATH210": "B+"},
                "target_program": "BS Computer Science",
                "target_term": "Spring 2026",
                "max_credits": 15
            }
        },
        {
            "title": "DEMO 3: Course Planning",
            "query": "Help me plan my schedule for Fall 2025. I've finished the first two years of CS.",
            "student_info": {
                "completed_courses": [
                    "CS101", "CS102", "CS201", "CS210", "CS220",
                    "MATH101", "MATH102", "MATH201", "MATH210",
                    "ENG101", "ENG102"
                ],
                "grades": {"CS201": "A-", "CS210": "B", "CS220": "B+"},
                "target_program": "BS Computer Science",
                "target_term": "Fall 2025",
                "max_credits": 15,
                "current_credits_earned": 70
            }
        },
        {
            "title": "DEMO 4: Safe Abstention (Out of Scope)",
            "query": "Which professor teaches CS301 this semester and what time does the class meet?",
            "student_info": {
                "completed_courses": ["CS101", "CS102", "CS201", "MATH201"],
                "target_program": "BS Computer Science",
                "target_term": "Fall 2025",
                "max_credits": 15
            }
        },
        {
            "title": "DEMO 5: Clarifying Questions (Incomplete Profile)",
            "query": "What courses should I take next semester?",
            "student_info": {
                # Missing: completed_courses, target_program
                "target_term": "Fall 2025",
                "max_credits": 15
            }
        }
    ]

    for case in demo_cases:
        print(f"\n{'#' * 70}")
        print(f"  {case['title']}")
        print('#' * 70)
        print(f"  Query: {case['query']}")
        print('#' * 70)

        result = pipeline.run(
            query=case["query"],
            student_info=case["student_info"],
            verbose=True
        )
        print(result["formatted_output"])
        print(f"\n  [Verification: {'✓ PASSED' if result.get('verification_passed') else '⚠ FLAGGED'}]")
        print(f"  [Citations: {len(result.get('citations', []))} sources]")
        print(f"  [Citation Coverage: {result.get('citation_coverage', 0):.0%}]")


def run_eval(pipeline: CourseAssistantPipeline):
    """Run the full 25-query evaluation suite."""
    print("\n📊 RUNNING EVALUATION SUITE (25 queries)...")
    from evaluation.evaluator import Evaluator, TEST_QUERIES
    evaluator = Evaluator(pipeline, output_dir="evaluation/results")
    report = evaluator.run_evaluation(TEST_QUERIES)

    print("\n✓ Evaluation complete. Results saved to evaluation/results/")
    print("  Files: evaluation_summary.json, full_results.json, example_transcripts.json")
    return report


def interactive(pipeline: CourseAssistantPipeline):
    """Interactive chat mode."""
    print("\n💬 INTERACTIVE MODE")
    print("Type 'quit' to exit. Type 'reset' to start a new session.\n")

    student_info = {}

    # Collect basic student info
    print("Let's set up your student profile first.")
    print("(Press Enter to skip optional fields)\n")

    program = input("Target program (e.g., BS Computer Science): ").strip()
    if program:
        student_info["target_program"] = program

    term = input("Target term (e.g., Fall 2025): ").strip()
    if term:
        student_info["target_term"] = term

    courses = input("Completed courses (comma-separated, e.g., CS101,CS102): ").strip()
    if courses:
        student_info["completed_courses"] = [c.strip() for c in courses.split(",")]

    max_cr = input("Max credits per semester (default: 15): ").strip()
    student_info["max_credits"] = int(max_cr) if max_cr.isdigit() else 15

    print(f"\n✓ Profile set up. Ask me anything about courses and prerequisites!\n")

    while True:
        query = input("\n> Your question: ").strip()
        if query.lower() == "quit":
            print("Goodbye!")
            break
        if query.lower() == "reset":
            print("Session reset. Restart for new profile.")
            break
        if not query:
            continue

        result = pipeline.run(query, student_info, verbose=False)
        print(result["formatted_output"])


def main():
    # Detect mode from command line args
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"

    print("=" * 70)
    print("🎓 RAG COURSE PLANNING ASSISTANT")
    print("   Agentic RAG | FAISS | sentence-transformers")
    print("=" * 70)

    # Initialize pipeline
    pipeline = CourseAssistantPipeline(
        data_dir="data",
        vectorstore_dir="vectorstore",
        top_k=5
    )

    # Try to load existing index, build if not found
    index_exists = os.path.exists("vectorstore/index.faiss")

    if mode == "build" or not index_exists:
        build(pipeline)
    else:
        print("\n✓ Loading existing index from disk...")
        pipeline.load_index()

    # Run the requested mode
    if mode == "demo" or mode == "all":
        demo(pipeline)

    if mode == "eval" or mode == "all":
        run_eval(pipeline)

    if mode == "interactive":
        interactive(pipeline)

    if mode not in ("build", "demo", "eval", "interactive", "all"):
        print(f"\nUnknown mode: '{mode}'")
        print("Usage: python main.py [build|demo|eval|interactive|all]")


if __name__ == "__main__":
    main()
