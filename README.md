# Delivery Evidence Auditor

An AI evidence auditor that reads real project artefacts, retrieves the most relevant evidence, and surfaces delivery risks with citable proof instead of generic status summaries.

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

1. Ingest source files
2. Chunk content into evidence units
3. Embed and store chunks in Pinecone namespaces
4. Retrieve evidence across multiple risk angles
5. Rerank the retrieved pool
6. Extract risks with the LLM
7. Validate citations and severity
8. Generate a report or escalate to human review

---

## 📄 Sample Reports

The system programmatically generates executive markdown reports in the `samples/` folder:
- **Project Atlas:** [`samples/atlas_risk_report.md`](samples/atlas_risk_report.md)
- **Project Nova:** [`samples/nova_risk_report.md`](samples/nova_risk_report.md)

---

## 🚀 Future GTM Sprints

See [`gtm_future_sprints.md`](gtm_future_sprints.md) for the complete Go-To-Market roadmap, including:
- **Sprint 1 (Jira & Slack Direct Connectors):** Targeting VP of Engineering / Delivery Leads.
- **Sprint 2 (Automated Executive Briefings & Telegram HITL Approval):** Targeting Operations & Program Managers.
- **Sprint 3 (SOC2/Compliance Audit Trails):** Targeting Chief Information Security Officers (CISOs).

---

## 🧩 Architecture & Pipeline Overview

```
[Inbound Artifacts] (.md, .txt, .csv)
                │
                ▼
Document Ingestion & Chunking (Stable chunk_ids)
                │
                ▼
Vector Embedding (OpenAI) ➔ Pinecone Namespaces
                │
                ▼
Multi-Angle Retrieval ➔ Cohere Reranking
                │
                ▼
Structured LLM Risk Extraction (Grounded Citations)
                │
                ▼
Citation Validation & Context Verification Loop
├── Valid ➔ Generate Markdown Report (/samples)
└── SEV-1 / Contradiction ➔ Escalated via Telegram HITL
```

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

# Optional Configurations
PINECONE_INDEX=delivery-evidence-auditor
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Optional Human-In-The-Loop Alerts
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

## Repository Layout
```
.
├── app/
│   |── ui.py                  # Streamlit Web UI Entrypoint
│   ├── cards.py                
│   ├── sidebar.py 
│   └── theme.py 
├── src/
│   ├── agent.py                # LLM risk extraction & citation validation logic
│   ├── api.py                  # FastAPI wrapper for triggering audits
│   ├── chunking.py             # Converts documents into citable evidence units with stable `chunk_id` values.
│   ├── cli_runner.py           # Command-line audit runner
│   ├── embedding.py            # Pinecone index management
│   ├── graph.py                # LangGraph state machine definition
│   ├── ingestion.py            # Document loader (.md, .txt, .csv) sources from `knowledge_base/`
│   ├── reporting.py            # Programmatic Markdown report builder
│   └── retrieval.py            # Multi-angle retrieval & Cohere reranking
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

## Requirements

The project uses the packages listed in `requirements.txt`, including:

- LangChain and LangGraph
- OpenAI
- Pinecone
- Cohere
- Streamlit
- FastAPI and pytest

## Environment Variables

Create a `.env` file at the repository root with at least:

- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `COHERE_API_KEY`

Optional variables:

- `PINECONE_INDEX` defaulting to `delivery-risk-assistant`
- `LLM_MODEL` defaulting to `gpt-4o-mini`
- `EMBEDDING_MODEL` defaulting to `text-embedding-3-small`
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for human-in-the-loop alerts

## Setup

```bash
pip install -r requirements.txt
```

## Run The Project

### Streamlit UI (Primary MVP Entrypoint)

```bash
streamlit run app/app.py
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
