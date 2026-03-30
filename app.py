import streamlit as st
import pandas as pd
import subprocess
import sys
import os

# Important: ensure project root is reachable for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.pipeline import CourseAssistantPipeline

# Page Configuration
st.set_page_config(page_title="RAG Course Planner", page_icon="🎓", layout="wide")

# Initialize Pipeline State
@st.cache_resource
def get_pipeline():
    # Call existing pipeline (same logic as main.py interactive)
    pipeline = CourseAssistantPipeline(data_dir="data", vectorstore_dir="vectorstore", top_k=5)
    pipeline.load_index()
    return pipeline

pipeline = get_pipeline()

# 1. INPUT SECTION (Sidebar)
with st.sidebar:
    st.header("📋 Student Profile")
    target_program = st.text_input("Target program", value="Computer Science (Course 6)")
    target_term = st.text_input("Target term", value="Fall 2026")
    completed_courses_str = st.text_area("Completed courses (comma-separated)", value="6.100A, 18.01")
    max_credits = st.number_input("Max credits", min_value=1, max_value=60, value=48)
    
    st.markdown("---")
    st.header(" System Admin")
    # EXTRA (BONUS): Analyze Dataset button
    if st.button("Dataset Information"):
        with st.spinner("Running analyze_data.py..."):
            try:
                res = subprocess.run([sys.executable, "analyze_data.py"], capture_output=True, text=True)
                st.session_state["analysis_output"] = res.stdout
            except Exception as e:
                st.session_state["analysis_output"] = f"Error: {e}"

# 2. MAIN QUERY SECTION
st.title("🎓 Agentic RAG Course Planning Assistant")

if "analysis_output" in st.session_state:
    with st.expander("Dataset Analysis Results", expanded=True):
        st.code(st.session_state["analysis_output"])

st.markdown("### Ask your question")
query = st.text_area("Enter your question:", placeholder="e.g. Can I take 6.1210 if I completed 6.100A?")

st.markdown("**Example queries:**")
colA, colB, colC = st.columns(3)
with colA:
    if st.button("Can I take 6.1210 if I completed 6.100A?"):
        query = "Can I take 6.1210 if I completed 6.100A?"
with colB:
    if st.button("Plan my next semester"):
        query = "Plan my next semester"
with colC:
    if st.button("What is the prerequisite chain for 6.1020?"):
        query = "What is the prerequisite chain for 6.1020?"

# 3. BUTTON
if st.button(" Run Query", type="primary") or query:
    if not query:
        st.warning("Please enter a question or click an example.")
    else:
        with st.spinner("Orchestrating AI Agents (Retriever, Planner, Verifier)..."):
            # Construct dictionary to pass to pipeline verbatim
            completed_courses = [c.strip() for c in completed_courses_str.split(",") if c.strip()]
            student_info = {
                "target_program": target_program,
                "target_term": target_term,
                "completed_courses": completed_courses,
                "max_credits": max_credits
            }
            
            # Execute original pipeline identically to main.py
            result = pipeline.run(query=query, student_info=student_info, verbose=False)
            
            st.markdown("---")
            
            # 7. DESIGN: Highlight decision
            decision = result.get("eligibility_decision")
            if decision == "Eligible":
                st.success(f"### Status:  {decision}")
            elif decision == "Not Eligible":
                st.error(f"### Status:  {decision}")
            elif decision == "Need More Info":
                st.warning(f"### Status:  {decision}")
            else:
                st.info("### Status:  Information Provided")
            
            # Parse `formatted_output` to cleanly separate UI components exactly as requested
            raw_text = result.get("formatted_output", "")
            
            parts = {}
            current_header = None
            current_content = []
            
            for line in raw_text.split("\n"):
                if line.startswith("ANSWER / PLAN:"):
                    if current_header: parts[current_header] = "\n".join(current_content).strip()
                    current_header = "Answer / Plan"
                    current_content = []
                elif line.startswith("WHY"):
                    if current_header: parts[current_header] = "\n".join(current_content).strip()
                    current_header = "Why"
                    current_content = []
                elif line.startswith("CITATIONS:"):
                    if current_header: parts[current_header] = "\n".join(current_content).strip()
                    current_header = "Citations"
                    current_content = []
                elif line.startswith("CLARIFYING QUESTIONS:"):
                    if current_header: parts[current_header] = "\n".join(current_content).strip()
                    current_header = "Clarifying Questions"
                    current_content = []
                elif line.startswith("ASSUMPTIONS"):
                    if current_header: parts[current_header] = "\n".join(current_content).strip()
                    current_header = "Assumptions"
                    current_content = []
                elif not line.startswith("=====") and not line.startswith("📋") and not line.startswith("DECISION:"):
                    current_content.append(line)
            
            if current_header:
                parts[current_header] = "\n".join(current_content).strip()

            # 4. OUTPUT DISPLAY
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("Answer / Plan")
                # Fallback to general output if parsing fails to catch the header
                st.info(parts.get("Answer / Plan", result.get("formatted_output")))
                
                st.subheader("Why")
                st.markdown(parts.get("Why", "N/A"))
            
            with col2:
                st.subheader("Citations")
                citations_text = parts.get("Citations")
                if citations_text:
                    st.markdown(citations_text)
                else:
                    st.markdown("\n".join([f"- {c}" for c in result.get("citations", [])]))
                
                cq_text = parts.get("Clarifying Questions")
                system_cq = result.get("clarifying_questions", [])
                if cq_text or system_cq:
                    st.subheader("Clarifying Questions")
                    st.warning(cq_text if cq_text else "\n".join([f"- {c}" for c in system_cq]))
                
                if parts.get("Assumptions"):
                    st.subheader("Assumptions")
                    st.markdown(parts.get("Assumptions"))
            
            # 5. COURSE PLAN VIEW (SPECIAL)
            recs = result.get("recommended_courses")
            if recs:
                st.markdown("---")
                st.markdown("###  Proposed Semester Course Plan")
                # Convert list of dicts to dataframe
                df = pd.DataFrame(recs)
                # Ensure mapping of exact columns requested by user
                cols_to_show = {}
                if "course_id" in df.columns: cols_to_show["course_id"] = "Course ID"
                if "title" in df.columns: cols_to_show["title"] = "Title"
                if "credits" in df.columns: cols_to_show["credits"] = "Credits"
                if "justification" in df.columns: cols_to_show["justification"] = "Justification"
                
                # Render using Streamlit's rich table
                if cols_to_show:
                    display_df = df[list(cols_to_show.keys())].rename(columns=cols_to_show)
                    st.table(display_df)
                else:
                    st.table(df)
