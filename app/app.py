import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Ensure the src directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from graph import build_graph

load_dotenv()

st.set_page_config(
    page_title="Delivery Risk Assistant",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Delivery Risk Assistant")
st.markdown("Automated risk extraction, cost/impact estimation, and deterministic decision-tree routing.")

# Sidebar Controls
st.sidebar.header("Configuration")
project_choice = st.sidebar.selectbox("Select Project", options=["atlas", "nova"], index=0)
user_question = st.sidebar.text_input(
    "Audit Query", 
    value="What are this week's top delivery risks?"
)

run_audit = st.sidebar.button("Run Risk Audit", type="primary")

if run_audit:
    with st.spinner(f"Analyzing project documents for '{project_choice.upper()}'..."):
        app = build_graph()
        state = {
            "project": project_choice,
            "question": user_question
        }
        result = app.invoke(state)
        
        # Handle state response mapping flexibly
        res_container = result.get("result", result)
        status = res_container.get("status", "unknown")
        message = res_container.get("message", "No message provided")
        requires_hitl = result.get("requires_hitl", False)
        risks = res_container.get("risks", [])

    # Display Pipeline Status Banner
    st.subheader("Audit Results & Decision Routing")
    
    # Safely extract or generate message
    message = res_container.get("message") or result.get("message")
    if not message and (requires_hitl or status == "pending_hitl_approval"):
        message = "High-severity risk or status contradiction detected. Escalated for human approval via Telegram."

    if requires_hitl or status == "pending_hitl_approval":
        st.warning(f"🚨 **High-Severity Escalation Triggered (HITL Gate Active)**\n\n{message}")
    elif status == "rejected":
        st.error(f"❌ **Response Rejected by Safety Layer**\n\n{message}")
    elif status == "insufficient_evidence":
        st.info(f"ℹ️ **Insufficient Evidence**\n\n{message}")
    else:
        st.success(f"✅ **Audit Complete — Status: OK**")

    st.markdown("---")
    
    # Display Extracted Risks
    st.subheader(f"Extracted Risks ({len(risks)})")
    
    if not risks:
        st.info("No delivery risks matched the criteria in the provided source documents.")
    
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
            
            # Severity Badges
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
                
            # Citations list
            citations = r.get('citations', [])
            if citations:
                st.markdown(f"**Grounded Citations:** `{'`, `'.join(citations)}`")
            
            st.markdown("---")
else:
    st.info("👈 Select a project and click **Run Risk Audit** in the sidebar to begin.")