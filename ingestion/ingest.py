"""
ingestion/ingest.py
-------------------
Document ingestion pipeline for the RAG Course Planning Assistant.

Handles:
  - Loading JSON catalog files from data/raw/
  - Converting structured course data to clean text chunks
  - Cleaning and normalizing text
  - Saving processed documents to data/processed/

WHY THIS APPROACH:
  We use structured JSON catalog files (not raw HTML) because:
  1. University catalog pages often have heavy JS rendering that's hard to scrape reliably
  2. JSON gives us clean, structured data with known fields (prereqs, credits, etc.)
  3. We convert JSON → rich text documents so the retriever can do semantic search
  4. Each course becomes one or more documents with all relevant metadata embedded in text
"""

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class Document:
    """Represents a processed document chunk ready for embedding."""
    doc_id: str
    text: str
    source_url: str
    source_title: str
    doc_type: str  # 'course', 'program_requirement', 'policy'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "doc_type": self.doc_type,
            "metadata": self.metadata
        }


class CatalogIngester:
    """
    Ingests university catalog JSON files and converts them to Document objects
    suitable for embedding and retrieval.
    """

    def __init__(self, raw_dir: str = "data/raw", processed_dir: str = "data/processed"):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.documents: List[Document] = []

    def load_all(self) -> List[Document]:
        """Load and process all files in the raw directory."""
        raw_files = []
        for ext in ["*.json", "*.md", "*.txt", "*.html"]:
            raw_files.extend(list(self.raw_dir.glob(ext)))
            
        logger.info(f"Found {len(raw_files)} catalog files in {self.raw_dir}")

        for filepath in raw_files:
            # Skip SOURCES.md from being parsed as a catalog file
            if filepath.name.upper() == "SOURCES.MD":
                continue
                
            logger.info(f"Processing: {filepath.name}")
            if filepath.suffix.lower() == '.json':
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    docs = self._process_file(data, filepath.stem)
                    self.documents.extend(docs)
                    logger.info(f"  → Generated {len(docs)} documents from {filepath.name}")
                except Exception as e:
                    logger.error(f"  ✗ Error processing {filepath.name}: {e}")
            else:
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                        
                    doc_type = "course"
                    name_lower = filepath.stem.lower()
                    if "program" in name_lower or "degree" in name_lower or "requirement" in name_lower:
                        doc_type = "program_requirement"
                    elif "policy" in name_lower or "grade" in name_lower or "academic" in name_lower:
                        doc_type = "policy"
                        
                    doc = Document(
                        doc_id=filepath.stem,
                        text=text,
                        source_url=f"local://{filepath.name}",
                        source_title=filepath.stem.replace("_", " ").title(),
                        doc_type=doc_type,
                        metadata={"source_file": filepath.name}
                    )
                    self.documents.append(doc)
                    logger.info(f"  → Generated 1 flat document from {filepath.name}")
                except Exception as e:
                    logger.error(f"  ✗ Error processing {filepath.name}: {e}")

        logger.info(f"Total documents loaded: {len(self.documents)}")
        return self.documents

    def _process_file(self, data: Dict, filename: str) -> List[Document]:
        """Route file to appropriate processor based on content."""
        docs = []

        if "courses" in data:
            docs.extend(self._process_courses(data))
        if "program" in data:
            docs.extend(self._process_program(data))
        if "policies" in data:
            docs.extend(self._process_policies(data))
        if "minor" in data:
            docs.extend(self._process_minor(data))
        if "additional_courses" in data:
            docs.extend(self._process_courses({"courses": data["additional_courses"],
                                                "source": data["source"],
                                                "url": data["url"]}))
        if "faq_entries" in data:
            docs.extend(self._process_faq(data))

        return docs

    def _process_courses(self, data: Dict) -> List[Document]:
        """Convert course catalog entries to Document objects."""
        docs = []
        # Fallback defaults if not in file or course
        file_url = data.get("url")
        file_source = data.get("source")

        for course in data.get("courses", []):
            text = self._course_to_text(course)
            # Prioritize course-specific source metadata, then file metadata, then absolute fallback
            doc_source_url = course.get("source_url") or file_url or "https://catalog.mit.edu"
            doc_source_title = course.get("department") or file_source or "University Course Catalog"
            
            doc = Document(
                doc_id=f"course_{course['course_id']}",
                text=text,
                source_url=doc_source_url,
                source_title=doc_source_title,
                doc_type="course",
                metadata={
                    "course_id": course["course_id"],
                    "title": course["title"],
                    "credits": course.get("credits"),
                    "prerequisites": course.get("prerequisites", "None"),
                    "corequisites": course.get("corequisites", "None"),
                    "min_grade_prereq": course.get("min_grade_prereq"),
                    "offered": course.get("offered", []),
                    "category": course.get("category", "")
                }
            )
            docs.append(doc)
        return docs

    def _course_to_text(self, course: Dict) -> str:
        """Convert a course dict to rich natural language text for embedding."""
        lines = [
            f"COURSE: {course['course_id']} - {course['title']}",
            f"Credits: {course.get('credits', 'Unknown')}",
            f"Category: {course.get('category', 'Unknown')}",
            f"Description: {course.get('description', '')}",
            f"Prerequisites: {course.get('prerequisites', 'None')}",
            f"Co-requisites: {course.get('corequisites', 'None')}",
        ]

        if course.get("min_grade_prereq"):
            lines.append(f"Minimum grade required in prerequisites: {course['min_grade_prereq']}")

        if course.get("offered"):
            offered = course["offered"]
            if isinstance(offered, list):
                lines.append(f"Offered: {', '.join(offered)}")
            else:
                lines.append(f"Offered: {offered}")

        if course.get("notes"):
            lines.append(f"Important Notes: {course['notes']}")

        # New enriched fields
        if course.get("learning_outcomes"):
            outcomes = course["learning_outcomes"]
            lines.append("Learning Outcomes:")
            for outcome in outcomes:
                lines.append(f"  - {outcome}")

        if course.get("prerequisite_chain"):
            chain = course["prerequisite_chain"]
            lines.append(f"Prerequisite Chain: {' → '.join(chain)}")

        if course.get("prerequisite_rationale"):
            lines.append(f"Prerequisite Rationale: {course['prerequisite_rationale']}")

        if course.get("textbook"):
            lines.append(f"Textbook: {course['textbook']}")

        if course.get("weekly_hours"):
            lines.append(f"Weekly Hours: {course['weekly_hours']}")

        if course.get("assessment"):
            lines.append(f"Assessment: {course['assessment']}")

        return "\n".join(lines)

    def _process_program(self, data: Dict) -> List[Document]:
        """Convert program requirement data to Document objects."""
        docs = []
        program = data.get("program", {})
        source_url = program.get("source_url") or data.get("url") or "https://catalog.mit.edu/programs"
        source_title = program.get("program_name") or data.get("source") or "Program Requirements"

        # Main program overview document
        overview_text = self._program_overview_to_text(program, data)
        docs.append(Document(
            doc_id=f"program_{program.get('degree', 'unknown').replace(' ', '_')}",
            text=overview_text,
            source_url=source_url,
            source_title=source_title,
            doc_type="program_requirement",
            metadata={"program": program.get("degree"), "total_credits": program.get("total_credits_required")}
        ))

        # Core requirements document
        if "core_requirements" in program:
            core = program["core_requirements"]
            core_text = (
                f"PROGRAM CORE REQUIREMENTS: {program.get('degree', '')}\n"
                f"All of the following courses are REQUIRED:\n"
                f"Courses: {', '.join(core.get('courses', []))}\n"
                f"Total core credits: {core.get('total_core_credits', 'N/A')}\n"
                f"Note: {core.get('note', '')}\n"
                f"Source: {source_url}"
            )
            docs.append(Document(
                doc_id=f"program_core_{program.get('degree', 'unknown').replace(' ', '_')}",
                text=core_text,
                source_url=source_url,
                source_title=source_title,
                doc_type="program_requirement",
                metadata={"type": "core_requirements", "courses": core.get("courses", [])}
            ))

        # Elective requirements document
        if "elective_requirements" in program:
            elec = program["elective_requirements"]
            elec_text = (
                f"PROGRAM ELECTIVE REQUIREMENTS: {program.get('degree', '')}\n"
                f"{elec.get('description', '')}\n"
                f"Total elective credits required: {elec.get('total_elective_credits', 'N/A')}\n"
                f"Upper-division elective credits required: {elec.get('upper_division_elective_credits', 'N/A')}\n"
                f"Eligible elective courses: {', '.join(elec.get('eligible_courses', []))}\n"
                f"Note: {elec.get('note', '')}\n"
                f"Source: {source_url}"
            )
            docs.append(Document(
                doc_id=f"program_electives_{program.get('degree', 'unknown').replace(' ', '_')}",
                text=elec_text,
                source_url=source_url,
                source_title=source_title,
                doc_type="program_requirement",
                metadata={"type": "elective_requirements"}
            ))

        # Graduation requirements document
        if "graduation_requirements" in program:
            grad = program["graduation_requirements"]
            grad_text = (
                f"GRADUATION REQUIREMENTS: {program.get('degree', '')}\n"
                + "\n".join(f"- {k}: {v}" for k, v in grad.items())
                + f"\nSource: {source_url}"
            )
            docs.append(Document(
                doc_id=f"graduation_reqs_{program.get('degree', 'unknown').replace(' ', '_')}",
                text=grad_text,
                source_url=source_url,
                source_title=source_title,
                doc_type="program_requirement",
                metadata={"type": "graduation_requirements"}
            ))

        # Concentration tracks
        if "concentration_tracks" in program:
            for track_key, track in program["concentration_tracks"].items():
                track_text = (
                    f"CONCENTRATION TRACK: {track.get('name', track_key)}\n"
                    f"Program: {program.get('degree', '')}\n"
                    f"Required courses: {', '.join(track.get('required_courses', []))}\n"
                )
                if "choose_2_from" in track:
                    track_text += f"Choose 2 from: {', '.join(track['choose_2_from'])}\n"
                track_text += f"Note: {track.get('note', '')}\nSource: {source_url}"
                docs.append(Document(
                    doc_id=f"track_{track_key}",
                    text=track_text,
                    source_url=source_url,
                    source_title=source_title,
                    doc_type="program_requirement",
                    metadata={"type": "concentration_track", "track": track_key}
                ))

        return docs

    def _program_overview_to_text(self, program: Dict, data: Dict) -> str:
        """Convert program overview to text."""
        lines = [
            f"PROGRAM: {program.get('degree', 'Unknown Degree')}",
            f"Department: {program.get('department', 'N/A')}",
            f"Total credits required: {program.get('total_credits_required', 'N/A')}",
            f"Minimum cumulative GPA: {program.get('min_gpa_required', 'N/A')}",
        ]
        if program.get("min_cs_gpa_required"):
            lines.append(f"Minimum CS major GPA: {program.get('min_cs_gpa_required')}")
        if program.get("residency_requirement"):
            lines.append(f"Residency requirement: {program.get('residency_requirement')}")
        if program.get("upper_division_requirement"):
            lines.append(f"Upper-division requirement: {program.get('upper_division_requirement')}")
        lines.append(f"Source URL: {data.get('url', 'N/A')}")
        lines.append(f"Date accessed: {data.get('date_accessed', 'N/A')}")
        return "\n".join(lines)

    def _process_policies(self, data: Dict) -> List[Document]:
        """Convert academic policy data to Document objects."""
        docs = []
        source_url = data.get("url") or "https://catalog.mit.edu/policies"
        source_title = data.get("source") or "Academic Policies"
        policies = data.get("policies", {})

        if isinstance(policies, dict):
            for policy_key, policy_data in policies.items():
                text = self._policy_to_text(policy_key, policy_data, source_url)
                docs.append(Document(
                    doc_id=f"policy_{policy_key}",
                    text=text,
                    source_url=source_url,
                    source_title=source_title,
                    doc_type="policy",
                    metadata={"policy_type": policy_key}
                ))
        elif isinstance(policies, list):
            for i, policy_data in enumerate(policies):
                policy_key = policy_data.get("id", f"policy_{i}")
                title = policy_data.get("title", f"Policy {i}")
                
                text = f"ACADEMIC POLICY: {title.upper()}\n"
                text += self._dict_to_text(policy_data, indent=0)
                text += f"\nSource: {source_url}"
                
                docs.append(Document(
                    doc_id=f"policy_{policy_key}",
                    text=text,
                    source_url=source_url,
                    source_title=source_title,
                    doc_type="policy",
                    metadata={"policy_type": policy_data.get("id", "generic")}
                ))

        return docs

    def _policy_to_text(self, key: str, policy: Any, source_url: str) -> str:
        """Convert a policy dict to text."""
        title = key.replace("_", " ").upper()
        text = f"ACADEMIC POLICY: {title}\n"
        text += self._dict_to_text(policy, indent=0)
        text += f"\nSource: {source_url}"
        return text

    def _dict_to_text(self, d: Any, indent: int = 0) -> str:
        """Recursively convert dict to readable text."""
        if isinstance(d, dict):
            lines = []
            for k, v in d.items():
                k_str = k.replace("_", " ")
                if isinstance(v, dict):
                    lines.append(f"{'  ' * indent}{k_str}:")
                    lines.append(self._dict_to_text(v, indent + 1))
                elif isinstance(v, list):
                    lines.append(f"{'  ' * indent}{k_str}: {', '.join(str(i) for i in v)}")
                else:
                    lines.append(f"{'  ' * indent}{k_str}: {v}")
            return "\n".join(lines)
        elif isinstance(d, list):
            return ", ".join(str(i) for i in d)
        else:
            return str(d)

    def _process_minor(self, data: Dict) -> List[Document]:
        """Process minor program requirements."""
        docs = []
        source_url = data.get("url", "https://catalog.stateuniversity.edu/programs")
        source_title = data.get("source", "State University Catalog")
        minor = data.get("minor", {})

        text = (
            f"MINOR PROGRAM: {minor.get('name', 'Unknown Minor')}\n"
            f"Total credits: {minor.get('total_credits', 'N/A')}\n"
            f"Department: {minor.get('department', 'N/A')}\n"
        )
        if minor.get("description"):
            text += f"Description: {minor['description']}\n"
        reqs = minor.get("requirements", {})
        if reqs.get("required_courses"):
            courses = []
            for c in reqs["required_courses"]:
                desc = f" - {c.get('description', '')}" if c.get('description') else ''
                courses.append(f"{c['id']} ({c['title']}, {c['credits']} cr){desc}")
            text += f"Required courses: {'; '.join(courses)}\n"
        if reqs.get("electives_choose_3"):
            electives = []
            for c in reqs["electives_choose_3"]:
                desc = f" - {c.get('description', '')}" if c.get('description') else ''
                electives.append(f"{c['id']} ({c['title']}){desc}")
            text += f"Choose 3 electives from: {'; '.join(electives)}\n"
        if reqs.get("note"):
            text += f"Note: {reqs['note']}\n"
        if reqs.get("gpa_requirement"):
            text += f"GPA Requirement: {reqs['gpa_requirement']}\n"
        if reqs.get("declaration"):
            text += f"Declaration: {reqs['declaration']}\n"
        if minor.get("career_outcomes"):
            text += f"Career Outcomes: {minor['career_outcomes']}\n"
        if minor.get("advising"):
            text += f"Advising: {minor['advising']}\n"
        text += f"Source: {source_url}"

        docs.append(Document(
            doc_id="minor_data_science",
            text=text,
            source_url=source_url,
            source_title=source_title,
            doc_type="program_requirement",
            metadata={"type": "minor", "name": minor.get("name")}
        ))
        return docs

    def _process_faq(self, data: Dict) -> List[Document]:
        """Process FAQ entries into documents."""
        docs = []
        source_url = data.get("url", "https://catalog.stateuniversity.edu/cs/faq")
        source_title = data.get("source", "CS Department FAQ")

        for entry in data.get("faq_entries", []):
            text = (
                f"FAQ: {entry['question']}\n\n"
                f"Answer: {entry['answer']}\n"
            )
            if entry.get("related_courses"):
                text += f"\nRelated courses: {', '.join(entry['related_courses'])}\n"
            if entry.get("tags"):
                text += f"Tags: {', '.join(entry['tags'])}\n"

            docs.append(Document(
                doc_id=f"faq_{entry['id']}",
                text=text,
                source_url=source_url,
                source_title=source_title,
                doc_type="policy",
                metadata={
                    "type": "faq",
                    "category": entry.get("category", ""),
                    "tags": entry.get("tags", [])
                }
            ))
        return docs

    def save_processed(self):
        """Save all processed documents to JSON for inspection."""
        output = [doc.to_dict() for doc in self.documents]
        output_path = self.processed_dir / "all_documents.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Saved {len(output)} processed documents to {output_path}")

        # Save statistics
        stats = {
            "total_documents": len(self.documents),
            "by_type": {},
            "total_words": 0
        }
        for doc in self.documents:
            stats["by_type"][doc.doc_type] = stats["by_type"].get(doc.doc_type, 0) + 1
            stats["total_words"] += len(doc.text.split())

        stats_path = self.processed_dir / "ingestion_stats.json"
        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Ingestion stats: {stats}")
        return stats


def run_ingestion(raw_dir: str = "data/raw", processed_dir: str = "data/processed") -> List[Document]:
    """Main entry point for ingestion pipeline."""
    ingester = CatalogIngester(raw_dir=raw_dir, processed_dir=processed_dir)
    docs = ingester.load_all()
    ingester.save_processed()
    return docs


if __name__ == "__main__":
    import sys
    base = Path(__file__).parent.parent
    docs = run_ingestion(
        raw_dir=str(base / "data/raw"),
        processed_dir=str(base / "data/processed")
    )
    print(f"\n✓ Ingestion complete. {len(docs)} documents ready for embedding.")
