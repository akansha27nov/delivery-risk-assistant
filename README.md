# AI Delivery Risk Assistant

An AI Delivery Risk Assistant that reads real project artefacts, retrieves the most relevant evidence, and surfaces delivery risks with citable proof instead of generic status summaries.

The core principle: **If a risk cannot be directly grounded in source chunks, it is not reported.**

---

## What It Does

- Loads project documents from `knowledge_base/` and maps each file to a project namespace through `project_manifest.json`.
- Splits text and CSV rows into citable chunks.
- Embeds chunks into Pinecone using OpenAI embeddings.
- Runs multi-angle retrieval, then reranks the candidate evidence with Cohere.
- Extracts up to three risks with structured OpenAI output.
- Validates citations and routes high-severity findings or status contradictions to human review.
- Provides a Streamlit UI for inspection and live document uploads into an existing project namespace.

## Pipeline

1. Ingest source files and live uploads.
2. Chunk content into stable evidence units.
3. Embed chunks and store them in Pinecone project namespaces.
4. Retrieve evidence across multiple risk angles.
5. Rerank the candidate pool with Cohere.
6. Extract risks with the LLM.
7. Validate citations, context, and contradiction grounding.
8. Route to a Markdown report, Notion delivery, or Telegram HITL escalation.

---

## 📄 Sample Reports

The system programmatically generates executive markdown reports in the `samples/` folder:
- **Project Atlas:** [`samples/atlas_risk_report.md`](samples/atlas_risk_report.md)
- **Project Nova:** [`samples/nova_risk_report.md`](samples/nova_risk_report.md)

## 🎥 Demo Assets

- **Demo recording:** [`demo_recording.mov`](https://docs.google.com/presentation/d/1ZYCJ6ScpqKs9wYU-YQi_pPyOKsvRL28zBnUs2gTPEjA/edit?slide=id.p1#slide=id.p1)
- **Slide deck (PDF):** [`docs/AI_Delivery_Risk_Assistant_Deck.pdf`](docs/AI_Delivery_Risk_Assistant_Deck.pdf)

---

## 🚀 Future GTM Sprints

See [`gtm_future_sprints.md`](gtm_future_sprints.md) for the complete Go-To-Market roadmap, including:
- **Sprint 1 (Pilot Validation):** Targeting 1–2 engineering managers or delivery leads (warm network intro).
- **Sprint 2 (Enterprise Slack & Jira Native Integration):** Targeting Engineering Managers, Tech Leads, and VP of Engineering.
- **Sprint 3 (Executive Cross-Project Portfolio Dashboard & Predictive Analytics):** Targeting Chief Technology Officer (CTO), VP of Product Delivery, and Director of Engineering Operations.

---

## 🧩 System Architecture & Execution Workflow

### 🏗️ System Architecture

```text
                    +----------------------+
                    |   Streamlit UI       |
                    |   app/ui.py          |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |      FastAPI         |
                    |    POST /run-audit   |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |  CLI / n8n Trigger   |
                    |  cli_runner.py       |
                    +----------+-----------+
                               |
                               v
                 +----------------------------------+
                 |     graph.py / LangGraph         |
                 | deterministic audit state machine|
                 +-----------------+----------------+
                                   |
        +--------------------------+---------------------------+
        |                          |                           |
        v                          v                           v
+------------------+   +------------------------+   +------------------------+
| ingestion.py     |   | retrieval.py           |   | agent_analysis.py      |
| load documents   |-->| multi-angle Pinecone   |-->| OpenAI risk extraction |
| project mapping  |   | retrieval + rerank     |   | + dedupe               |
+------------------+   +------------------------+   +------------------------+
        |                          |                           |
        v                          v                           v
+------------------+   +------------------------+   +------------------------+
| chunking.py      |   | embedding.py           |   | agent_validation.py    |
| stable chunks    |   | OpenAI -> Pinecone     |   | citations/context/HITL |
+------------------+   +------------------------+   +------------------------+
                                   |
                                   v
                    +------------------------------+
                    | Outputs                      |
                    | - samples/*.md               |
                    | - Notion via n8n             |
                    | - Telegram alerts            |
                    +------------------------------+
```

The **AI Delivery Risk Assistant** runs on a central **LangGraph** deterministic state machine (`graph.py`) that orchestrates retrieval, evaluation, and downstream reporting across multiple interfaces and integrations. Please check [system architecture here](docs/architecture_diagram.svg)

* **Entrypoints:**
  * **Streamlit UI:** Interactive dashboard for uploading documents, inspecting chunks, and running audits (`app/ui.py`).
  * **FastAPI:** RESTful endpoint (`POST /run-audit`) for programmatic execution.
  * **CLI:** Local terminal execution script (`src/cli_runner.py`).
  * **n8n Schedule Trigger:** Automated weekly cron trigger running every Thursday.
* **External Services & Stack:**
  * **OpenAI:** Generates vector embeddings and powers structured LLM extraction.
  * **Pinecone:** Multi-tenant vector database separated by per-project namespaces.
  * **Cohere Rerank (`rerank-v3.5`):** Cross-encoder reranking to filter candidate evidence pools.
  * **Telegram Bot API:** Real-time push notifications for human approval requests.
* **Outputs:** Generates local **Markdown Reports** (`samples/*.md`), automated **Notion Pages** (via n8n), and **Telegram Alerts** for flagged risks.

---
### 🔄 Execution Flow & Decision Tree

The underlying [Workflow Diagram](docs/workflow_diagram.png) executes through a strict, node-based decision tree to prevent hallucinated risks and enforce safety gates:

1. **Retrieval Gate (`retrieve_documents`):** Checks if candidate evidence exists for the prompt. If none is found, it terminates early at `ask_for_more_documents`.
2. **Analysis & Citation Validation (`analyse_risks` → `validate_citations`):** Extracts risks with source citations. If citation validation fails (unsupported or hallucinated claims), the graph routes to `reject_response`.
3. **Severity & HITL Escalation (`evaluate_severity`):** Validated risks are evaluated for severity.
   * **SEV-1 / High Severity:** Triggers deterministic human-in-the-loop routing via `route_to_hitl`.
   * **Standard Audit:** Directly outputs the final audit summary via `generate_report`.

---

## 🛠️ Tools & API Integrations

The system integrates four external services:
1. **OpenAI API (`gpt-4o-mini` / `text-embedding-3-small`):** Structured JSON risk extraction and vector embedding.
2. **Pinecone Vector Database:** Multi-project namespace storage for project document chunks.
3. **Cohere Rerank API (`rerank-v3.5`):** Reranks candidate evidence vectors for high precision.
4. **Telegram Bot API:** Instant alert routing for Human-in-the-Loop approval when high-severity risks or contradictions occur.

---

## ⚙️ Environment Variables

Create a `.env` file at the repository root with the following keys:

```env
# Required Services
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
COHERE_API_KEY=your_cohere_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

## Repository Layout
```
.
├── app/
│   ├── cards.py               # UI cards for executive summary and risk breakdown
│   ├── sidebar.py             # Streamlit sidebar controls and upload flow
│   ├── theme.py                # Theme helpers used by the Streamlit UI
│   └── ui.py                  # Streamlit web UI entrypoint
├── src/
│   ├── agent.py               # Compatibility facade that re-exports the agent API
│   ├── agent_analysis.py      # OpenAI risk extraction, parsing, and deduplication helpers
│   ├── agent_models.py        # Pydantic schemas for extracted risks and impact breakdowns
│   ├── agent_validation.py    # Citation, context, and contradiction validation logic
│   ├── api.py                 # FastAPI wrapper for triggering audits
│   ├── chunking.py            # Converts documents into citable evidence units with stable chunk IDs
│   ├── cli_runner.py          # Command-line audit runner
│   ├── config.py              # Environment and model configuration
│   ├── embedding.py           # Pinecone index management
│   ├── graph.py               # LangGraph state machine definition and HITL routing
│   ├── ingestion.py           # Document loader for .md, .txt, and .csv sources
│   ├── logger.py              # Shared console and file logger configuration
│   ├── prompts.py             # System prompts used by the LLM agent
│   ├── reporting.py           # Programmatic Markdown report builder
│   ├── rerank.py              # Cohere reranking helper
│   └── retrieval.py           # Multi-angle retrieval over project namespaces
├── tests/                      # contains unit tests plus grounded integration checks.
├── samples/                    # System-generated audit reports
│   ├── atlas_risk_report.md
│   └── nova_risk_report.md
├── knowledge_base/             # Demo project artifact files
├── docs/                       # Internal documentation & ground truth files
├── scripts/                    # Individual test scripts for some code
├── workflow/                   # n8n workflow `.json`
├── screenshots/                # n8n workflow screenshot
├── plan/                       # contains project plan and elevator pitch
├── gtm_future_sprints.md       # Go-To-Market expansion strategy
├── stack_decision.md           # Stack selection rationale (LangGraph vs. n8n)
├── requirements.txt            # Python dependencies
└── README.md                   # System documentation

```

## Setup

```bash
pip install -r requirements.txt
```

---

## 🌐 Live API Deployment

The backend FastAPI service is deployed live on **Render** to provide a persistent, secure HTTPS endpoint for automated integrations (such as the **n8n** workflow).

* **Base URL:** `https://delivery-risk-api.onrender.com`
* **Interactive OpenAPI Docs:** [`https://delivery-risk-api.onrender.com/docs`](https://delivery-risk-api.onrender.com/docs)
* **Primary Audit Endpoint:** `POST /run-audit`

### ⚡ Key Infrastructure Notes
* **Automated CI/CD:** Any updates pushed to the `main` branch automatically trigger a build and redeployment on Render.
* **Instance Cold Starts:** Render's free tier automatically spins down after 15 minutes of inactivity. The initial incoming request after a sleep period may experience a **30–50 second delay** while the container boots up.

## Run The Project

### Streamlit UI (Primary MVP Entrypoint)

```bash
streamlit run app/ui.py
```

The UI lets you choose a project namespace, inspect retrieved evidence, run the full audit, and upload a new document into the selected project namespace.

- Select a project namespace (atlas or nova).
- Inspect raw reranked evidence vectors.
- Trigger full audit pipeline and view KPI dashboard.
- Reports automatically update in `samples/`.

### CLI Audit

```bash
cd src
python cli_runner.py --project atlas --pretty
```

Replace `atlas` with `nova` to run the other demo corpus. The CLI prints a JSON payload plus a pre-rendered markdown briefing.

### Rebuild The Demo Corpus (Knowledge Base Vector Index)

```bash
cd src
python ingestion.py
python chunking.py
python embedding.py
```

The embedding step needs live API access and will create or refresh the Pinecone index if needed.

## Testing

Run the fast unit tests from the repository root:

```bash
pytest tests/test_unit_*.py tests/test_agent.py
```

Run the live grounded integration checks from `src/` when the API keys and network access are available:

```bash
cd src
pytest ../tests/test_grounding.py -v
```

If you want to run the full suite, include the grounding test only when the external services are configured.

## Data Notes

- `knowledge_base/` contains the synthetic demo corpus for two projects: `atlas` and `nova`.
- `project_manifest.json` is the source of truth for which files belong to each project.
- The corpora are intentionally small and structured to exercise blockers, scope creep, resolved issues, and status contradictions.
- `docs/ground_truth_risks.md` exists for evaluation only.

## Output Behavior & Guardrails

- **Strict Grounding:** Every reported risk must include valid chunk_id references from retrieved evidence.
- **False Positive Elimination:** Resolved or historical issues are filtered out from current risk metrics.
- **HITL Routing:** High-severity risks (SEV-1) or status contradictions trigger human approval workflows.
- The **Streamlit app** includes a live upload flow that adds a new file into an existing project namespace without clearing the rest of the index.

---

## 📖 Terminology & Glossary

This section breaks down the core concepts, UI metrics, and system terminology used throughout the **Delivery Risk Assistant**.

### 🎛️ System & Inputs
* **Project Scope:** Namespace isolation in the vector database (e.g., `atlas`, `nova`) ensuring evidence and search contexts remain completely separated between projects or teams.
* **Knowledge Base:** The underlying vector store (Pinecone) holding embedded text chunks from uploaded sprint reports, ticket exports, and meeting transcripts.
* **Inspect Evidence:** An intermediate transparency check that displays retrieved candidate text chunks and their rerank scores *before* running full LLM risk extraction.

### 📊 Dashboard & Metrics
* **Human-in-the-Loop (HITL):** A deterministic safety gate. If the pipeline detects SEV-1 blockers or severe data contradictions, it pauses or escalates alerts to human managers (via Telegram) for manual review.
* **Delivery Health:** A high-level visual pulse check using a traffic light system:
  * 🔴 **RED (Critical):** Contains SEV-1 blockers or active HITL escalations.
  * 🟡 **YELLOW (Warning):** Contains medium or low-severity delivery risks to monitor.
  * 🟢 **GREEN (Clear):** No significant delivery risks or blockers flagged.
* **Risk Score:** A normalized score out of 100 representing project health. Points are automatically deducted based on the volume and severity of detected risks.
* **Grounded Findings:** An anti-hallucination metric showing the percentage of extracted claims that are directly backed up by verified source document citations.
* **SEV-1 (Severity-1):** Critical-path blockers (e.g., missing API credentials, blocked launch dependencies) that directly threaten target delivery dates.

### 🛡️ Risk Analysis & Verification
* **Evidence Confidence:** A percentage score calculating how strongly the retrieved evidence supports a specific risk finding, based on document depth and semantic relevance.
* **Data Tag:** A provenance label attached to findings (e.g., `directional_estimate`, `explicit_fact`) that tells executives whether a claim is an exact source statement or a calculated AI projection.
* **Business Impact Grid:** A 4-axis breakdown evaluating how a technical risk impacts **Delivery**, **Customer Experience**, **Business/Revenue**, and **Team Morale**.
* **Forensic Evidence Inspector:** An expandable "receipts" panel providing direct access to the exact raw text chunks, source file locations, and citation metadata used by the LLM.
* **Rerank Score:** A semantic relevance score generated by **Cohere Rerank** (`rerank-v3.5`) used to prioritize candidate evidence chunks before LLM processing.
