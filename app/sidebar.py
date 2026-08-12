import streamlit as st
from ingestion import build_document_from_upload
from chunking import chunk_documents
from embedding import add_document_to_project
from logger import get_logger

logger = get_logger(__name__)

def reset_audit_state():
    st.session_state.retrieved_evidence = []
    st.session_state.audit_result = None

def render_sidebar():
    st.sidebar.header("1. Audit Configuration")
    
    project_choice = st.sidebar.selectbox(
        "Select Project Scope", 
        options=["atlas", "nova"], 
        index=0,
        on_change=reset_audit_state
    )

    if "upload_status" not in st.session_state:
        st.session_state.upload_status = None

    with st.sidebar.expander(f"Upload a document into '{project_choice}'", expanded=False):
        uploaded_file = st.file_uploader(
            "Add a new sprint report, ticket export, or transcript",
            type=["md", "txt", "csv"],
            key=f"uploader_{project_choice}",
        )
        add_doc_clicked = st.button("Add to Knowledge Base", disabled=uploaded_file is None)

        if add_doc_clicked and uploaded_file is not None:
            with st.spinner(f"Embedding '{uploaded_file.name}'..."):
                try:
                    raw_text = uploaded_file.getvalue().decode("utf-8")
                    doc = build_document_from_upload(uploaded_file.name, raw_text, project_choice)
                    add_document_to_project(chunk_documents([doc]), project_choice)
                    logger.info("Uploaded document '%s' added to project '%s'.", uploaded_file.name, project_choice)
                    
                    st.session_state.upload_status = {"ok": True, "message": f"Added '{uploaded_file.name}'."}
                    # Clear previous audit runs on new upload 
                    st.session_state.retrieved_evidence = []
                    st.session_state.audit_result = None
                except Exception as e:
                    logger.exception("Upload failed for project '%s' and file '%s': %s", project_choice, getattr(uploaded_file, "name", "unknown"), e)
                    st.session_state.upload_status = {"ok": False, "message": f"Failed: {e}"}

        if st.session_state.upload_status:
            if st.session_state.upload_status["ok"]:
                st.success(st.session_state.upload_status["message"])
            else:
                st.error(st.session_state.upload_status["message"])

    user_question = st.sidebar.text_input(
        "Audit Query", 
        value="What are this week's top delivery risks and blockers?",
        on_change=reset_audit_state
    )

    st.sidebar.markdown("---")
    st.sidebar.header("2. Execution Workflow")
    run_inspection = st.sidebar.button("Step A: Inspect Retrieved Evidence")
    run_audit = st.sidebar.button("Step B: Run Full Risk Audit", type="primary")

    return project_choice, user_question, run_inspection, run_audit
