import asyncio
import os
import sys
import datetime
import streamlit as st
from dotenv import load_dotenv

# Ensure the src directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from graph import build_graph
from retrieval import gather_evidence_async
from ingestion import build_document_from_upload
from chunking import chunk_documents
from embedding import add_document_to_project

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

# ==========================================
# UPLOAD: Add a new document into the selected project's live index
# ==========================================
if "upload_status" not in st.session_state:
    st.session_state.upload_status = None

with st.sidebar.expander(f"➕ Upload a document into '{project_choice}'", expanded=False):
    uploaded_file = st.file_uploader(
        "Add a new sprint report, ticket export, or transcript",
        type=["md", "txt", "csv"],
        help=(
            "Embeds this document directly into the "
            f"'{project_choice}' project's live knowledge base, "
            "without touching any other project or document."
        ),
        key=f"uploader_{project_choice}",
    )
    add_doc_clicked = st.button(
        "Add to Knowledge Base",
        disabled=uploaded_file is None,
        key="add_to_kb",
    )

    if add_doc_clicked and uploaded_file is not None:
        with st.spinner(f"Embedding '{uploaded_file.name}' into '{project_choice}'..."):
            try:
                raw_text = uploaded_file.getvalue().decode("utf-8")
                doc = build_document_from_upload(uploaded_file.name, raw_text, project_choice)
                new_chunks = chunk_documents([doc])
                add_document_to_project(new_chunks, project_choice)
                st.session_state.upload_status = {
                    "ok": True,
                    "message": (
                        f"Added '{uploaded_file.name}' — {len(new_chunks)} new chunk(s) "
                        f"embedded into '{project_choice}'."
                    ),
                }
                # Any evidence/results already on screen were retrieved before
                # this document existed -- clear them so a stale audit can't
                # be mistaken for one that reflects the new document.
                st.session_state.retrieved_evidence = []
                st.session_state.audit_result = None
            except (UnicodeDecodeError, ValueError) as e:
                st.session_state.upload_status = {"ok": False, "message": str(e)}
            except Exception as e:
                st.session_state.upload_status = {
                    "ok": False,
                    "message": f"Embedding failed: {e}",
                }

    if st.session_state.upload_status:
        if st.session_state.upload_status["ok"]:
            st.success(st.session_state.upload_status["message"])
        else:
            st.error(st.session_state.upload_status["message"])

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
    # ==========================================
    # NEW: EXECUTIVE SUMMARY DASHBOARD
    # ==========================================
    st.subheader("📈 Executive Summary Dashboard")
    st.caption(f"**Analysis Timestamp:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Calculate KPIs
    total_risks = len(risks)
    high_risks = sum(1 for r in risks if r.get('is_sev1', False) or r.get('is_contradiction', False))
    medium_risks = total_risks - high_risks
    
    # Heuristic Risk Score (Base 100, deduct for risks)
    risk_score = 100 - (high_risks * 15) - (medium_risks * 5)
    risk_score = max(0, risk_score) # Prevent negative scores
    
    # Overall Health Logic
    if high_risks > 0 or requires_hitl:
        health_color = "🔴 Red"
    elif medium_risks > 0:
        health_color = "🟠 Amber"
    else:
        health_color = "🟢 Green"

    # Documents Analyzed (Count unique source locations)
    docs_analyzed = len(set(c.get('location', 'unknown') for c in evidence_pool)) if evidence_pool else 0
    
    # Grounded Findings (%)
    valid_risks = sum(1 for r in risks if r.get('valid', True))
    grounded_pct = (valid_risks / total_risks * 100) if total_risks > 0 else 100
    
    # Render KPI Cards
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    kpi_col1.metric("Overall Delivery Health", health_color)
    kpi_col2.metric("Risk Score", f"{risk_score}/100")
    kpi_col3.metric("Grounded Findings", f"{grounded_pct:.0f}%")
    
    kpi_col4, kpi_col5, kpi_col6 = st.columns(3)
    kpi_col4.metric("High Risks (SEV-1/Blockers)", high_risks)
    kpi_col5.metric("Medium/Low Risks", medium_risks)
    kpi_col6.metric("Documents Analysed", docs_analyzed)

    st.markdown("---")
    
    # ==========================================
    # EXTRACTED RISKS SECTION (Updated Header)
    # ==========================================
    st.subheader(f"🛡️ Detailed Risk Breakdown ({len(risks)})")
    
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
                conf_score = r.get('evidence_confidence', r.get('confidence_score', 85))
                st.metric(
                    "Evidence Confidence", 
                    f"{conf_score}%",
                    help="Evidence Confidence indicates how strongly this finding is supported by retrieved project documents. It is calculated from citation validation, the number of independent supporting documents, and retrieval relevance scores. It is not generated by the language model."
                )
            # Render Transparent Breakdown Details
            breakdown = r.get('confidence_breakdown', {})
            cite_check = "✓" if breakdown.get('citation_valid', True) else "✗"
            doc_count = breakdown.get('num_docs', len(r.get('citations', [])))
            ret_qual = breakdown.get('retrieval_quality', 'Medium')
            
            st.markdown(
                f"<small style='color: grey;'>Calculated from: "
                f"&nbsp;&nbsp;Citation validation {cite_check} "
                f"&nbsp;|&nbsp; Supporting evidence: {doc_count} docs "
                f"&nbsp;|&nbsp; Retrieval quality: {ret_qual}</small>",
                unsafe_allow_html=True
            )
            
            # Display Confidence Tag Badge below
            tag = r.get('confidence_tag', 'directional_estimate')
            if tag == 'estimated_from_source_data':
                st.success(f"🏷️ Data Tag: {tag}")
            else:
                st.info(f"🏷️ Data Tag: {tag}")
            
            st.markdown(f"**Explanation:** {r.get('explanation', 'No explanation provided.')}")
            impact = r.get('impact_breakdown', {})
            if impact:
                st.markdown("**Business Impact:**")
                st.markdown(f"- **Delivery:** {impact.get('delivery_impact', 'N/A')}")
                st.markdown(f"- **Customer:** {impact.get('customer_impact', 'N/A')}")
                st.markdown(f"- **Business/Revenue:** {impact.get('business_impact', 'N/A')}")
                st.markdown(f"- **Team:** {impact.get('team_impact', 'N/A')}")
            
            # Display Actionable Recommendations
            recs = r.get('recommendations', [])
            if recs:
                st.markdown("**Actionable Recommendations:**")
                for rec in recs:
                    st.markdown(f"- {rec}")
                    
            # Severity & Validation Metrics
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                is_sev1 = r.get('is_sev1', False)
                st.metric("SEV-1 Flag", "Active 🔴" if is_sev1 else "False 🟢")
            with c2:
                is_contra = r.get('is_contradiction', False)
                st.metric("Contradiction Flag", "Detected ⚠️" if is_contra else "False 🟢")
            with c3:
                is_valid = r.get('valid', True)
                st.metric("Citation Validation", "Valid ✅" if is_valid else "Invalid ❌")
            with c4:
                is_context_consistent = r.get('context_consistent', True)
                st.metric(
                    "Context Consistency",
                    "Consistent ✅" if is_context_consistent else "Mismatch ❌",
                )

            if not r.get('context_consistent', True):
                st.error(
                    "⚠️ **Context mismatch:** the cited chunks describe unrelated "
                    "projects/systems and do not actually corroborate each other.\n\n"
                    f"{r.get('context_mismatch_detail', '')}"
                )

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