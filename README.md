# AI Delivery Risk Assistant

An AI agent that reads real project artefacts (sprint reports, ticket exports, meeting
transcripts) and surfaces grounded, cited delivery risks — instead of a status report someone
has to manually assemble by hand.

Every risk claim the assistant makes must be traceable back to a specific source chunk. If it
can't cite one, it doesn't get to say it. That constraint — not the RAG pipeline itself — is the
point of this project.

## The problem

Programme leaders spend hours a week reading standups, tickets, and status docs to manually piece
together what's actually at risk. This assistant automates that synthesis, and treats
hallucination as a defect to be caught, not an acceptable trade-off.

## User flow

```
1. Upload Documents
        ↓
2. Build Knowledge Base
        ↓
3. Analyse Delivery Risks
        ↓
4. Inspect Evidence
```

## Pipeline (LangGraph)

```
                 START
                   │
                   ▼
          Load User Question
                   │
                   ▼
          Retrieve Documents
                   │
                   ▼
         Enough Evidence?
          ┌───────────────┐
          │               │
         No              Yes
          │               │
          ▼               ▼
   Ask for More      Analyse Risks
   Documents               │
                            ▼
                  Validate Citations
                            │
                            ▼
             Citation Missing?
               ┌─────────────┐
               │             │
              Yes           No
               │             │
               ▼             ▼
        Reject Response   Generate Report
               │             │
               └──────┬──────┘
                      ▼
                     END
```

## Repo structure

```
delivery-risk-assistant/
├── knowledge_base/                    # Sample project artefacts (the RAG corpus)
│   ├── sprint_report.md            # Batch 1 — Team Atlas / Rewards Partner
│   ├── ticket_export.csv
│   ├── standup_transcript.txt
│   ├── stakeholder_email.md
│   ├── nova_sprint_report.md       # Batch 2 — Team Nova / Checkout Redesign
│   ├── nova_incident_postmortem.md
│   ├── nova_slack_thread.txt
│   ├── nova_retro_notes.md
│   └── nova_exec_status_email.md
├── docs/
│   └── ground_truth_risks.md   # Answer key for evaluation — NOT ingested into the pipeline
├── src/
│   ├── ingestion.py           # Load + normalize source docs — DONE (Phase 2, Step 1)
│   ├── chunking.py            # Split into citable chunks — DONE (Phase 2, Step 2)
│   ├── embedding.py           # OpenAI embeddings -> Pinecone — DONE (Phase 2, Step 3; run locally, needs your API keys)
│   ├── retrieval.py           # Query Pinecone (Phase 3)
│   ├── rerank.py             # Cohere Rerank (Phase 3)
│   ├── agent.py              # LangGraph nodes: analyse risks, validate citations (Phase 4)
│   ├── graph.py              # Wires the LangGraph state machine together (Phase 4)
│   └── app.py                # UI — 4-step flow (Phase 5)
├── tests/
│   └── test_grounding.py     # Checks output against docs/ground_truth_risks.md (Phase 4)
├── requirements.txt
└── .env.example
```

## Sample corpus

The `knowledge_base/` folder contains two synthetic project narratives, all fabricated, with risks
intentionally planted so output can be checked against a known answer key.

**Batch 1 — Team Atlas / Rewards Partner launch** (sprint report, ticket export, standup
transcript, stakeholder email):
1. A critical-path ticket blocked 9 days on an external dependency
2. Uncontrolled mid-sprint scope addition
3. An attrition/retention signal from a single team member (single-source — tests that the
   assistant doesn't fabricate corroboration, and handles people-sensitive content responsibly)
4. Declining sprint velocity + a QA capacity gap

**Batch 2 — Team Nova / Checkout Redesign** (sprint report, incident postmortem, noisy Slack
export, retro notes, exec status email) — deliberately harder:
5. An unassigned, undated remediation ticket for a SEV-1 incident that threatens the launch
6. A hard external API deprecation deadline landing before launch, buried in off-topic Slack chat
   (tests retrieval/rerank robustness against noise)
7. A negative control: an explicitly *resolved* issue (CI flakiness) that should never be
   reported as a current risk (tests recency handling, not just retrieval)
8. A status-misrepresentation risk that only shows up as a *contradiction* between the exec status
   email and other sources — the single hardest case in the corpus, and the one closest to the
   actual "someone has to manually piece it together" problem from the pitch

See `docs/ground_truth_risks.md` for the full answer key and why each risk is a useful test case.

## Build status

- [x] **Phase 1** — Repo scaffold + sample documents
- [x] **Phase 2** — Ingestion, chunking, embedding
- [ ] **Phase 3** — Retrieval + rerank
- [ ] **Phase 4** — LangGraph agent reasoning + citation validation
- [ ] **Phase 5** — UI + packaging (4-step flow, README demo, walkthrough video)

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OpenAI, Pinecone, and Cohere API keys
```

## Verify Phase 2 locally

```bash
cd src
python ingestion.py     # confirms all 9 files load correctly
python chunking.py      # confirms 38 chunks are produced with clean citations
python embedding.py     # embeds via OpenAI, upserts into Pinecone, runs a
                         # sanity-check query (needs OPENAI_API_KEY +
                         # PINECONE_API_KEY — the one step that can't be
                         # tested without real API access)
```
