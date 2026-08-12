# n8n + Notion Integration — Justification & Implementation

## Why n8n at all, given LangGraph is the primary stack

LangGraph is primary here (see `planning.md`, Section 2), which makes n8n explicitly optional — the brief allows "a thin n8n webhook/trigger... but the brains stay in LangGraph."

n8n is adopted for: **scheduled, unattended delivery of the audit to Notion ahead of a recurring leadership meeting.** This plays to what each tool is actually good at:

- **LangGraph** does 100% of the reasoning — retrieval, citation validation, context-consistency checking, severity routing. n8n never touches any of this.
- **n8n** does what it's built for: a native cron trigger and a native Notion integration, without hand-building scheduling or delivery infrastructure that isn't the point of this project.

This is not orchestration duplication. It's the brief's own "thin optional helper" pattern, scoped to a real capability gap: nothing in the Streamlit app runs on its own — someone has to remember to click "Run Full Risk Audit." The n8n layer closes that gap.

## What was built

**`src/cli_runner.py`** — a programmatic entrypoint that invokes the compiled LangGraph (`build_graph().ainvoke(...)`) and returns a structured JSON payload: status, findings (each annotated with a hybrid Notion status — verified / rejected / pending human review), and a pre-rendered report. This is also the project's CLI/API entrypoint requirement from the brief,
independent of the Notion use case — it can be run standalone for testing without the UI.

**`src/api.py`** — a minimal FastAPI wrapper exposing `POST /run-audit`, so n8n (or anything else) can trigger a run over HTTP without needing to shell out to Python directly.

**`workflows/Risk auditor.json`** — the n8n workflow itself:

```
Schedule Trigger (weekly, Thursday 8am)
        │
        ▼
   Projects (atlas, nova)
        │
        ▼
Fetch project data (HTTP Request → api.py /run-audit, once per project)
        │
        ▼
     Aggregate
        │
        ▼
Create a master report (Code node — combines both projects into one payload)
        │
        ▼
Create report page in Notion
        │
        ▼
Send chunk data to append in Notion page (Code node — hard-caps each block
under Notion's 2000-char rich_text limit, then appends via the Notion node)
```

## Design decision: the hybrid HITL/Notion escalation model

The tool's core trust guarantee is that high-severity findings require human approval via Telegram before reaching leadership. A naive scheduled-delivery design threatens that guarantee two different ways:

- **Post automatically, always** — breaks the guarantee outright; an unapproved high-severity finding could reach the Notion report before anyone has reviewed it.
- **Wait for Telegram approval before posting** — protects the guarantee, but risks the report simply not existing when the Thursday meeting starts if the approver is slow or misses the notification. This defeats the actual purpose of scheduling the report in the first place.

**Decision: post on schedule, every time, with unapproved findings explicitly labeled.** Any risk still in `pending_hitl_approval` status at post time is marked **"⏳ Pending human review"** in Notion, visually and textually distinct from verified findings — never presented as a settled fact. This reuses the `pending_hitl_approval` status the state machine already produces for the Streamlit UI; Notion is a second, honest home for the same status, not a different
guarantee. The report is always there for the meeting, and it never claims more certainty than the system actually has.

## Verification

Confirmed working end-to-end against the real Atlas and Nova test corpora: multi-project combined report posts to a single Notion page on trigger, hybrid pending-labels render correctly for Nova's high-severity findings, and Atlas's rejected findings (citation/context mismatches) render with their specific rejection reasons rather than being silently dropped.
