import asyncio
import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Ensure the src directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from graph import build_graph
from retrieval import gather_evidence_async

load_dotenv()

st.set_page_config(
    page_title="Delivery Risk Assistant",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Delivery Risk Assistant")
st.markdown("Automated multi-angle risk extraction, cost/impact estimation, citation gating, and deterministic HITL routing.")

# ==========================================
# SIDEBAR: Configuration & Controls
# ==========================================
st.sidebar.header("1. Audit Configuration")
project_choice = st.sidebar.selectbox("Select Project Scope", options=["atlas", "nova"], index=0)
user_question = st.sidebar.text_input(
    "Audit Query", 
    value="What are this week's top delivery risks and blockers?"
)

st.sidebar.markdown("---")
st.sidebar.header("2. Execution Workflow")
run_inspection = st.sidebar.button("Step A: Inspect Retrieved Evidence", help="Fetch and view raw multi-angle chunks before running the agent.")
run_audit = st.sidebar.button("Step B: Run Full Risk Audit", type="primary", help="Run multi-angle retrieval, reranking, citation validation, and decision tree.")

# Maintain session state for retrieved evidence
if "retrieved_evidence" not in st.session_state:
    st.session_state.retrieved_evidence = []
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None

# ==========================================
# STEP A: EVIDENCE INSPECTION PANEL
# ==========================================
if run_inspection or run_audit:
    with st.spinner(f"Gathering and reranking evidence chunks for '{project_choice.upper()}'..."):
        # Run async evidence gathering
        evidence_chunks = asyncio.run(gather_evidence_async(project_choice, user_question))
        st.session_state.retrieved_evidence = evidence_chunks

if st.session_state.retrieved_evidence and not run_audit:
    st.subheader(f"🔍 Evidence Inspection Panel — Project: {project_choice.upper()}")
    st.markdown(f"Retrieved **{len(st.session_state.retrieved_evidence)}** unique chunks across multi-angle retrieval, sorted by Cohere relevance score.")
    
    for idx, chunk in enumerate(st.session_state.retrieved_evidence, 1):
        with st.expander(f"Chunk {idx}: `{chunk.get('chunk_id')}` (Location: {chunk.get('location')}) | Score: {chunk.get('rerank_score', chunk.get('score', 0)):.4f}"):
            st.markdown(f"**Source Text:**")
            st.info(chunk.get('text', 'No text found'))
            st.markdown(f"*Chunk ID:* `{chunk.get('chunk_id')}` | *Namespace:* `{project_choice}`")
            
    st.markdown("---")
    st.info("💡 Review the evidence above, then click **Step B: Run Full Risk Audit** in the sidebar when ready.")

# ==========================================
# STEP B: FULL AUDIT & DECISION ROUTING
# ==========================================
if run_audit:
    with st.spinner(f"Executing LangGraph pipeline for '{project_choice.upper()}'..."):
        app = build_graph()
        state = {
            "project": project_choice,
            "question": user_question
        }
        
        # Execute async graph invocation
        result = asyncio.run(app.ainvoke(state))
        st.session_state.audit_result = result

if st.session_state.audit_result:
    result = st.session_state.audit_result
    res_container = result.get("result", result)
    status = res_container.get("status", "unknown")
    message = res_container.get("message", "No message provided")
    requires_hitl = result.get("requires_hitl", False)
    risks = res_container.get("risks", [])
    evidence_pool = st.session_state.retrieved_evidence

    # Display Pipeline Status Banner
    st.subheader("📊 Audit Results & Decision Routing")
    
    if not message and (requires_hitl or status == "pending_hitl_approval"):
        message = "High-severity risk or status contradiction detected. Escalated for human approval via Telegram."

    if requires_hitl or status == "pending_hitl_approval":
        st.warning(f"🚨 **High-Severity Escalation Triggered (HITL Gate Active)**\n\n{message}")
    elif status == "rejected":
        st.error(f"❌ **Response Rejected by Safety Layer**\n\n{message}")
    elif status == "insufficient_evidence":
        st.info(f"ℹ️ **Insufficient Evidence**\n\n{message}")
    else:
        st.success(f"✅ **Audit Complete — Status: OK (No High-Severity Escalation)**")

    st.markdown("---")
    
    # Display Extracted Risks with Cited Text Inspector
    st.subheader(f"🛡️ Extracted & Grounded Risks ({len(risks)})")
    
    if not risks:
        st.info("No delivery risks matched the criteria in the provided source documents.")
    
    # Create lookup map for evidence text
    evidence_map = {c["chunk_id"]: c for c in evidence_pool}

    for idx, r in enumerate(risks, 1):
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"### {idx}. {r.get('risk', 'Unnamed Risk')}")
            with col2:
                tag = r.get('confidence_tag', 'directional_estimate')
                if tag == 'estimated_from_source_data':
                    st.success(f"🏷️ {tag}")
                else:
                    st.info(f"🏷️ {tag}")
            
            st.markdown(f"**Explanation:** {r.get('explanation', 'No explanation provided.')}")
            st.markdown(f"**Cost / Impact Estimate:** `{r.get('cost_estimate', 'N/A')}`")
            
            # Severity & Validation Metrics
            c1, c2, c3 = st.columns(3)
            with c1:
                is_sev1 = r.get('is_sev1', False)
                st.metric("SEV-1 Flag", "Active 🔴" if is_sev1 else "False 🟢")
            with c2:
                is_contra = r.get('is_contradiction', False)
                st.metric("Contradiction Flag", "Detected ⚠️" if is_contra else "False 🟢")
            with c3:
                is_valid = r.get('valid', True)
                st.metric("Citation Validation", "Valid ✅" if is_valid else "Invalid ❌")
                
            # Citations list & Inspectable Cited Source Text
            citations = r.get('citations', [])
            if citations:
                st.markdown(f"**Grounded Citations:** `{'`, `'.join(citations)}`")
                
                # Inspectable chunk text expander for each citation
                with st.expander(f"📖 Inspect Raw Text for Citations ({len(citations)})"):
                    for cid in citations:
                        chunk_data = evidence_map.get(cid)
                        if chunk_data:
                            st.markdown(f"**`{cid}`** (Location: *{chunk_data.get('location')}* | Score: *{chunk_data.get('rerank_score', 0):.3f}*):")
                            st.text(chunk_data.get('text'))
                        else:
                            st.warning(f"Chunk ID `{cid}` was referenced by the model but not found in the active retrieved pool.")
            else:
                st.error("⚠️ **Uncited Risk:** This risk was flagged as invalid or missing grounded citations.")
            
            st.markdown("---")
else:
    if not run_inspection:
        st.info("👈 Use the sidebar to inspect retrieved evidence or run a full risk audit.")