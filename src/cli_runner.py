#!/usr/bin/env python3
"""
CLI Runner for Project Risk LangGraph Pipeline.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict, List

# Import your graph builder from graph.py
from graph import build_graph

DEFAULT_QUESTION = "What are this week's top delivery risks?"


def format_risk_item(risk: Dict[str, Any], overall_status: str) -> Dict[str, Any]:
    """
    Formats individual risk items and injects hybrid Notion status labels.
    """
    is_sev1 = risk.get("is_sev1", False)
    is_contradiction = risk.get("is_contradiction", False)
    is_high_sev = is_sev1 or is_contradiction

    # A risk is 'pending_hitl_approval' if the workflow routed to Telegram HITL and it's high severity
    is_pending = (overall_status == "pending_hitl_approval") and is_high_sev
    is_valid = risk.get("valid", False)

    if is_pending:
        item_status = "pending_hitl_approval"
        notion_label = "⏳ Pending human review"
        display_as_confirmed = False
    elif is_valid:
        item_status = "approved"
        notion_label = "✅ Verified"
        display_as_confirmed = True
    else:
        item_status = "rejected"
        notion_label = "❌ Rejected"
        display_as_confirmed = False

    return {
        "risk": risk.get("risk", ""),
        "explanation": risk.get("explanation", ""),
        "severity": "HIGH" if is_high_sev else "NORMAL",
        "is_sev1": is_sev1,
        "is_contradiction": is_contradiction,
        "valid": is_valid,
        "confidence_score": risk.get("confidence_score"),
        "impact_breakdown": risk.get("impact_breakdown", {}),
        "citations": risk.get("citations", []),
        "status": item_status,
        "notion_label": notion_label,
        "display_as_confirmed": display_as_confirmed
    }


def generate_notion_markdown(project: str, status: str, findings: List[Dict[str, Any]], message: str) -> str:
    """
    Generates a pre-formatted, publication-ready Executive Briefing document
    string formatted in Markdown for Notion page creation.
    """
    today_str = datetime.now().strftime("%B %d, %Y")
    project_upper = project.upper()

    md = f"# 🛡️ Executive Delivery Audit — Project {project_upper}\n"
    md += f"**Audit Date:** {today_str}\n\n"

    # Executive Status Banner
    if status == "pending_hitl_approval":
        md += "> ⚠️ **Executive Notice:** High-severity findings or status contradictions were detected during this audit. Findings awaiting verification are explicitly marked below.\n\n"
    elif status == "ok":
        md += "> ✅ **Audit Summary:** All extracted delivery risks have passed automated ground-truth and citation verification.\n\n"
    elif status == "rejected":
        md += f"> ❌ **Validation Failure:** {message}\n\n"
    elif status == "insufficient_evidence":
        md += f"> ℹ️ **Notice:** {message}\n\n"

    md += "---\n\n## 🚨 Key Audit Findings\n\n"

    if not findings:
        md += "_No active delivery risks were identified for this reporting cycle._\n"
        return md

    for idx, f in enumerate(findings, 1):
        label = f["notion_label"]
        risk_title = f["risk"]
        explanation = f["explanation"]
        impact = f.get("impact_breakdown", {})
        citations = ", ".join([f"`{c}`" for c in f.get("citations", [])]) or "None"

        md += f"### {idx}. {label}: {risk_title}\n"
        md += f"**Explanation:** {explanation}\n\n"

        if impact:
            delivery_impact = impact.get("delivery_impact", "None reported")
            business_impact = impact.get("business_impact", "None reported")
            md += f"* **Delivery Impact:** {delivery_impact}\n"
            md += f"* **Business Impact:** {business_impact}\n\n"

        md += f"**Evidence Citations:** {citations}\n\n"
        md += "---\n\n"

    return md


async def run_pipeline(project: str, question: str) -> Dict[str, Any]:
    """
    Executes the async LangGraph state machine and packages the JSON response.
    """
    graph = build_graph()

    # Invoke the state machine asynchronously (handles async retrieve_documents node)
    final_state = await graph.ainvoke({
        "project": project,
        "question": question
    })

    result = final_state.get("result", {})
    overall_status = result.get("status", "unknown")
    raw_risks = result.get("risks", [])
    message = result.get("message", "")

    # Format findings with hybrid state labels
    processed_findings = [format_risk_item(r, overall_status) for r in raw_risks]

    # Calculate summary metrics
    summary = {
        "total_risks": len(processed_findings),
        "verified": sum(1 for f in processed_findings if f["display_as_confirmed"]),
        "pending_review": sum(1 for f in processed_findings if f["status"] == "pending_hitl_approval"),
        "rejected": sum(1 for f in processed_findings if not f["valid"])
    }

    # Pre-render the full Markdown executive report
    report_md = generate_notion_markdown(project, overall_status, processed_findings, message)

    output_payload = {
        "status": overall_status,
        "project": project,
        "question": question,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "summary": summary,
        "findings": processed_findings,
        "report_title": f"🛡️ Executive Briefing — {project.upper()} [{datetime.now().strftime('%Y-%m-%d')}]",
        "report_markdown": report_md
    }

    return output_payload


def main():
    parser = argparse.ArgumentParser(
        description="Run risk assessment graph and generate Notion executive report payload."
    )
    parser.add_argument(
        "--project",
        type=str,
        required=True,
        help="Project identifier / namespace (e.g., atlas, nova, ORION)"
    )
    parser.add_argument(
        "--question",
        type=str,
        default=DEFAULT_QUESTION,
        help="Query to evaluate against documents"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Format output JSON with 2-space indentation"
    )

    args = parser.parse_args()

    try:
        results = asyncio.run(run_pipeline(project=args.project, question=args.question))
        indent = 2 if args.pretty else None
        print(json.dumps(results, indent=indent, default=str))

        if results["status"] in ["rejected", "insufficient_evidence"]:
            sys.exit(2)

        sys.exit(0)

    except Exception as e:
        error_payload = {
            "status": "error",
            "project": args.project,
            "error_message": str(e)
        }
        print(json.dumps(error_payload), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()