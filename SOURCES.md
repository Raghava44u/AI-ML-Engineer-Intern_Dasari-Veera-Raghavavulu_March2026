# Dataset Sources

This repository operates on real, scraped academic catalog data sourced from prominent universities (primarily MIT) to ensure the RAG Course Planner interacts with structurally accurate, rigorously defined rules, and edge dependencies.

## Primary Sources
- **Massachusetts Institute of Technology (MIT)**
  - Course Catalog (Subjects, Prerequisites, and Corequisites)
  - Degree Programs and Requirements (e.g., Course 6-3 Computer Science and Engineering)
  - General Institute Requirements (GIR)

- **Stanford University** (Reference Structures)
  - Undergraduate Bulletins and policy requirements

## Characteristics
- **Volume:** Over 30,000+ words of raw academic content processed into vectorized chunks.
- **Documents:** Includes courses, programs, and policies formatted precisely for dense RAG mapping:
  - `course_{id}.txt`
  - `policies.txt`
  - `programs.txt`
