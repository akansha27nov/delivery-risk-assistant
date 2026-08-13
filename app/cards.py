import streamlit as st
import datetime

def render_executive_summary(risks, evidence_pool, requires_hitl):
    header_col, date_col = st.columns([2, 1])
    with header_col:
        st.subheader("📈 Executive Summary Dashboard")
    with date_col:
        st.markdown(f"<div style='text-align: right; font-family: JetBrains Mono; font-size: 13px; color: #45464d;'>Analysis Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>", unsafe_allow_html=True)
    
    total_risks = len(risks)
    high_risks = sum(1 for r in risks if r.get('is_sev1', False) or r.get('is_contradiction', False))
    medium_risks = total_risks - high_risks
    
    risk_score = 100 - (high_risks * 15) - (medium_risks * 5)
    risk_score = max(0, risk_score) 
    
    if high_risks > 0 or requires_hitl:
        health_color = "🔴 Red"
    elif medium_risks > 0:
        health_color = "🟡 Yellow"
    else:
        health_color = "🟢 Green"

    docs_analyzed = len(set(c.get('location', 'unknown') for c in evidence_pool)) if evidence_pool else 0
    valid_risks = sum(1 for r in risks if r.get('valid', True))
    grounded_pct = (valid_risks / total_risks * 100) if total_risks > 0 else 100
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    kpi_col1.metric("Overall Delivery Health", health_color)
    kpi_col2.metric("Risk Score", f"{risk_score}/100")
    kpi_col3.metric("Grounded Findings", f"{grounded_pct:.0f}%")
    kpi_col4.metric("Documents Analysed", docs_analyzed)
    
    kpi_col5, kpi_col6, _, _ = st.columns(4)
    kpi_col5.metric("High Risks (SEV-1/Blockers)", high_risks)
    kpi_col6.metric("Medium/Low Risks", medium_risks)

def render_risk_breakdown(risks, evidence_pool):
    st.subheader(f"🛡️ Detailed Risk Breakdown ({len(risks)})")
    
    if not risks:
        st.info("No delivery risks matched the criteria in the provided source documents.")
        return
    
    evidence_map = {c["chunk_id"]: c for c in evidence_pool}

    for idx, r in enumerate(risks, 1):
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"### {idx}. {r.get('risk', 'Unnamed Risk')}")
                breakdown = r.get('confidence_breakdown', {})
                cite_check = "✓" if breakdown.get('citation_valid', True) else "✗"
                doc_count = breakdown.get('num_docs', len(r.get('citations', [])))
                ret_qual = breakdown.get('retrieval_quality', 'High')
                
                st.markdown(
                    f"<div style='font-family: JetBrains Mono; font-size: 13px; color: #45464d; margin-top: -10px; margin-bottom: 15px;'>"
                    f"Calculated from: Citation validation {cite_check} &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"Supporting evidence: {doc_count} docs &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"Retrieval quality: {ret_qual}</div>",
                    unsafe_allow_html=True
                )
                
            with col2:
                conf_score = r.get('evidence_confidence', r.get('confidence_score', 85))
                st.markdown(
                    f"<div style='text-align: right;'>"
                    f"<div style='font-family: JetBrains Mono; font-size: 12px; color: #45464d; text-transform: uppercase;'>Evidence Confidence</div>"
                    f"<div style='font-family: Inter; font-size: 36px; font-weight: 700; color: #1b1b1d; margin-top: -5px;'>{conf_score}%</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            
            tag = r.get('confidence_tag', 'estimated_from_source_data')
            st.markdown(f"`🏷️ Data Tag: {tag}`")
            st.markdown(f"<br>**EXPLANATION**<br>{r.get('explanation', 'No explanation provided.')}", unsafe_allow_html=True)
            
            impact = r.get('impact_breakdown', {})
            if impact:
                st.markdown("<br>**BUSINESS IMPACT**", unsafe_allow_html=True)
                imp_c1, imp_c2, imp_c3, imp_c4 = st.columns(4)
                
                metrics = [
                    ("🚚 Delivery", impact.get('delivery_impact', 'N/A')),
                    ("👥 Customer", impact.get('customer_impact', 'N/A')),
                    ("💵 Business/Revenue", impact.get('business_impact', 'N/A')),
                    ("⚙️ Team", impact.get('team_impact', 'N/A'))
                ]
                
                for col, (title, val) in zip([imp_c1, imp_c2, imp_c3, imp_c4], metrics):
                    with col:
                        st.markdown(f"<div style='background-color: #F8FAFC; padding: 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; height: 100%;'><span style='font-family: JetBrains Mono; font-size: 12px; font-weight: bold;'>{title}</span><br><br><span style='font-size: 14px; color: #45464d;'>{val}</span></div>", unsafe_allow_html=True)
            
            recs = r.get('recommendations', [])
            if recs:
                st.markdown("<br>**ACTIONABLE RECOMMENDATIONS**", unsafe_allow_html=True)
                for rec in recs:
                    st.markdown(f"- {rec}")

            st.write("<br>", unsafe_allow_html=True)

            citations = r.get('citations', [])
            if citations:
                with st.expander(f"🔍 FORENSIC EVIDENCE INSPECTOR"):
                    for cid in citations:
                        chunk_data = evidence_map.get(cid)
                        if chunk_data:
                            st.markdown(f"""
                            <div style="background-color: #ffffff; border: 1px solid #E2E8F0; border-radius: 0.25rem; padding: 0.75rem; margin-bottom: 0.5rem;">
                                <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.5rem; margin-bottom: 0.5rem;">
                                    <span style="font-family: JetBrains Mono; font-size: 13px; font-weight: bold; color: #000000;">Source: {chunk_data.get('location')}</span>
                                    <span style="font-family: JetBrains Mono; font-size: 13px; color: #45464d;">Rerank Score: {chunk_data.get('rerank_score', 0):.2f}</span>
                                </div>
                                <div style="font-family: JetBrains Mono; font-size: 13px; color: #1b1b1d;">
                                    {chunk_data.get('text')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.warning(f"Chunk ID `{cid}` was referenced by the model but not found in the active retrieved pool.")
            else:
                st.error("⚠️ **Uncited Risk:** This risk was flagged as invalid or missing grounded citations.")