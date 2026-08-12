import streamlit as st

def apply_custom_theme():
    st.markdown("""
    <style>
    /* 1. Base Fonts from Design System */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* 2. Global Background & Typography */
    .stApp {
        background-color: #F8FAFC !important;
        font-family: 'Inter', sans-serif !important;
        color: #1b1b1d !important;
    }

    h1, h2, h3, h4, h5, h6, .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
        color: #1b1b1d !important;
    }

    /* Typography Overrides */
    h1 { font-size: 36px !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
    h2 { font-size: 24px !important; font-weight: 600 !important; }
    h3 { font-size: 18px !important; font-weight: 600 !important; }
    p { font-size: 14px !important; line-height: 20px !important; }

    /* 3. Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #f0edef !important;
        border-right: 1px solid #E2E8F0 !important;
    }

    /* Sidebar Inputs & Labels */
    [data-testid="stSidebar"] .stSelectbox label, 
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] .stFileUploader label {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: #000000 !important;
    }

    /* Sidebar Primary Action Buttons & Focus State Fix */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #000000 !important;
        color: #ffffff !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        border-radius: 0.25rem !important;
        width: 100%;
        border: none !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] button[kind="primary"]:focus,
    [data-testid="stSidebar"] button[kind="primary"]:active {
        background-color: #565e74 !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* 4. Executive Summary Metrics Cards */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 0.25rem !important;
        padding: 1.25rem !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
    }
    [data-testid="stMetricLabel"] * {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        color: #45464d !important;
    }

    /* Metric Font Size Fix (Targeting nested divs) */
    [data-testid="stMetricValue"], 
    [data-testid="stMetricValue"] > div,
    [data-testid="stMetricValue"] p {
        font-family: 'Inter', sans-serif !important;
        font-size: 36px !important;
        font-weight: 700 !important;
        color: #1b1b1d !important;
        letter-spacing: -0.02em !important;
        line-height: normal !important;
    }

    /* 5. Success Banner (Audit Results) */
    [data-testid="stNotification"] {
        background-color: rgba(108, 248, 187, 0.2) !important;
        border: 1px solid #6cf8bb !important;
        border-radius: 0.5rem !important;
        padding: 1.5rem !important;
    }
    div[data-testid="stNotification"] p {
        color: #006c49 !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
    }

    /* 6. Data Tag & Metadata Formatting */
    code {
        font-family: 'JetBrains Mono', monospace !important;
        background-color: rgba(108, 248, 187, 0.1) !important;
        color: #006c49 !important;
        border: 1px solid rgba(108, 248, 187, 0.3) !important;
        border-radius: 0.25rem !important;
        padding: 0.25rem 0.5rem !important;
        font-size: 12px !important;
    }

    /* 7. Detailed Risk Breakdown UI & Impact Cards */
    div.stMarkdown p strong {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: #000000 !important;
    }

    /* 8. Expanders (Forensic Evidence Inspector) */
    [data-testid="stExpander"] {
        background-color: #fcf8fa !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 0.5rem !important;
    }
    [data-testid="stExpander"] summary {
        background-color: #fcf8fa !important;
        border-bottom: 1px solid #E2E8F0 !important;
    }
    [data-testid="stExpander"] summary p {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: #1b1b1d !important;
    }
    </style>
    """, unsafe_allow_html=True)