import asyncio
import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Ensure the src directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from graph import build_graph
from retrieval import gather_evidence_async
from reporting import generate_sample_report_markdown

# Import our new UI modules
from theme import apply_custom_theme
from cards import render_executive_summary, render_risk_breakdown
from sidebar import render_sidebar

load_dotenv()

st.set_page_config(page_title="Delivery Evidence Auditor", layout="wide")
apply_custom_theme()

st.title("🛡️ Delivery Evidence Auditor")
st.markdown("Automated multi-angle evidence extraction, cost/impact estimation, citation gating, and deterministic HITL routing.")

# --- Caching Decorators for Demo Speed & Cost Saving ---

@st.cache_resource(show_spinner=False)
def get_cached_graph():
    """Caches the compiled LangGraph workflow object in memory."""
    return build_graph()

@st.cache_data(show_spinner=False)
def cached_gather_evidence(project_choice: str, user_question: str):
    """Caches retrieval and reranking results for 10 minutes."""
    return asyncio.run(gather_evidence_async(project_choice, user_question))

# ==========================================
# SIDEBAR: Configuration & Controls
# ==========================================
project_choice, user_question, run_inspection, run_audit = render_sidebar()

# Maintain session state
if "retrieved_evidence" not in st.session_state:
    st.session_state.retrieved_evidence = []
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None
# ==========================================
# STEP A: EVIDENCE INSPECTION PANEL
# ==========================================
if run_inspection or run_audit:
    with st.spinner(f"Gathering evidence for '{project_choice.upper()}'..."):
        try:
            st.session_state.retrieved_evidence = cached_gather_evidence(project_choice, user_question)
        except Exception as e:
            st.error(f"⚠️ Evidence retrieval hiccup: {e}")
            st.info("💡 Tip: Check your API keys or network connection.")
            st.session_state.retrieved_evidence = []

if st.session_state.retrieved_evidence and not run_audit:
    st.subheader(f"🔍 Evidence Inspection Panel — Project: {project_choice.upper()}")
    for idx, chunk in enumerate(st.session_state.retrieved_evidence, 1):
        with st.expander(f"Chunk {idx}: `{chunk.get('chunk_id')}` | Score: {chunk.get('rerank_score', chunk.get('score', 0)):.4f}"):
            st.info(chunk.get('text', 'No text found'))
    st.info("💡 Review evidence, then click **Step B: Run Full Risk Audit** in the sidebar.")

# ==========================================
# STEP B: FULL AUDIT & DECISION ROUTING
# ==========================================
if run_audit:
    with st.spinner(f"Executing LangGraph pipeline for '{project_choice.upper()}'..."):
        try:
            graph = get_cached_graph()
            st.session_state.audit_result = asyncio.run(graph.ainvoke({
                "project": project_choice, 
                "question": user_question
            }))
            
            # Save sample report safely
            samples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../samples"))
            os.makedirs(samples_dir, exist_ok=True)
            with open(os.path.join(samples_dir, f"{project_choice}_risk_report.md"), "w", encoding="utf-8") as f:
                f.write(generate_sample_report_markdown(project_choice, st.session_state.audit_result))
                
        except Exception as e:
            st.error(f"⚠️ Pipeline execution error: {e}")
            st.info("💡 Tip: Verify your OpenAI and Pinecone API keys in the .env file.")

# Persistent Rendering from Session State
if st.session_state.audit_result:
    result = st.session_state.audit_result
    res_container = result.get("result", result)
    status = res_container.get("status", "unknown")
    message = res_container.get("message", "No message provided")
    requires_hitl = result.get("requires_hitl", False)

    st.write("<br>", unsafe_allow_html=True)
    
    if not message and (requires_hitl or status == "pending_hitl_approval"):
        message = "High-severity risk or status contradiction detected. Escalated for human approval."

    # Status Banners
    if requires_hitl or status == "pending_hitl_approval":
        st.warning(f"🚨 **High-Severity Escalation (HITL Gate Active)**\n\n{message}")
    elif status == "rejected":
        st.error(f"❌ **Response Rejected by Safety Layer**\n\n{message}")
    elif status == "insufficient_evidence":
        st.info(f"ℹ️ **Insufficient Evidence**\n\n{message}")
    else:
        st.success(f"✅ **Audit Complete**\n\nStatus: OK (No High-Severity Escalation)")

    st.markdown("---")
    
    render_executive_summary(res_container.get("risks", []), st.session_state.retrieved_evidence, requires_hitl)
    st.markdown("---")
    render_risk_breakdown(res_container.get("risks", []), st.session_state.retrieved_evidence)

elif not run_inspection:
    st.info("👈 Use the sidebar to inspect retrieved evidence or run a full risk audit.")