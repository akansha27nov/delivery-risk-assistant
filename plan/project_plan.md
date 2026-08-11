# AI Delivery Evidence Auditor — Project Plan

## 1. Use Case

**Project**: AI Delivery Evidence Auditor — a citation-gated evidence-auditing pipeline that surfaces delivery risks and status contradictions from project artefacts, with deterministic escalation to a human for the highest-stakes findings.

**Problem statement**: Programme leaders spend hours a week manually piecing together delivery risk from sprint reports, tickets, postmortems, and status emails — and status can quietly diverge from reality between what's reported up and what's actually happening in the tracker, with no automated check catching the gap before it reaches leadership.

**Existing solutions**: Jira/Linear-style dashboards are systems of record — they show what's been entered, not whether a status report actually matches the evidence underneath it, and they have no mechanism to cross-reference a sprint report against a standup transcript or an incident postmortem. Generic LLM chat (paste documents, ask for a summary) has no structural guarantee against fabricating a claim or blending unrelated context into one confident-sounding answer. Manual PM synthesis is the actual status quo — reading everything by hand, with no structural check for contradictions between what's reported and what's recorded elsewhere.

**Target users**: Engineering managers, delivery/programme leads, and the leadership they report to (as the recipient of the escalated findings).

**Verify**:
- **MVP level**: every risk claim traces back to a cited source chunk (rejected if it can't); cited evidence must also pass a context-consistency check so information from unrelated projects/teams cannot be stitched together; severity routing (direct report vs. human approval) is determined by an explicit binary decision tree, not an LLM judgment call; behavior is validated against a fixed synthetic test corpus with known planted risks and known negative controls.
- **Final Product level**: a real delivery lead runs this against their own project's actual documents for a full sprint cycle, and it changes what they escalate or notice earlier than they otherwise would have — in preference to their existing manual status-review habit.

**Current process**: Manual synthesis — reading standups, ticket exports, and status docs by hand, with no structural check for contradictions between what's reported up and what's actually recorded elsewhere.

**Industry alignment**: Software delivery / engineering programme management — an operations-intelligence problem.

**Competitors and competitive advantage**: The nearest existing tools are Jira/Linear dashboards and generic LLM summarization. Neither structurally prevents hallucination, neither cross-references status claims against underlying evidence, and neither has a deterministic, inspectable rule for deciding what needs a human's eyes before it reaches leadership. This system's edge is specific and testable: citation-or-reject grounding enforced in code (not just prompted for), a context-consistency guardrail that rejects evidence stitched together from unrelated projects, and a binary decision tree for severity escalation that is explainable and unit-testable rather than an opaque model judgment call.

**User story**: As an engineering manager, I want to ask "what are this week's top delivery risks" across my project's sprint reports, tickets, and transcripts, so that I get a grounded, evidence-cited answer instead of spending hours cross-referencing documents by hand — and so that status-vs-reality contradictions are caught automatically instead of surfacing only after a deadline slips.

**Acceptance criteria**:
- Given a project's documents contain a blocked, critical-path ticket with a named deadline, when the audit runs, then that risk is surfaced with citations to the specific ticket and any corroborating source, and marked as corroborated only if genuinely multi-sourced.
- Given a status document claims "on track / no blockers" while another document in the same project describes a specific, unresolved, dated problem, when the audit runs, then the contradiction itself is surfaced as a risk, citing both the status claim and the evidence that contradicts it.
- Given two cited chunks describe unrelated projects or teams (e.g. a document was uploaded into the wrong namespace), when a risk would cite both, then that risk is rejected before reaching the report, with the specific mismatch explained.
- Given a risk is tagged SEV-1 or a status contradiction, when severity routing runs, then it is escalated to a human via Telegram for approval before being included in the final report, rather than being reported directly.
- Given a resolved/closed issue is described in a source document, when the audit runs, then it is not reported as a current risk.

---

## 2. Technology Stack

**Framework answers**:
- Needs external knowledge: Yes → RAG (Pinecone).
- Interacts with external systems: Yes → tool integrations (Pinecone, Cohere Rerank, Telegram Bot API — beyond the core LLM).
- Needs multi-step reasoning: Yes → LangGraph, with **deterministic conditional routing rather than a ReAct tool-use loop**. The two decisions in this pipeline that matter most for trust (severity escalation, evidence-context consistency) are implemented as explicit, testable rules specifically *because* they're high-stakes — the same rationale a ReAct loop would need to earn its way past. A ReAct-style loop was considered for the evidence-gathering step itself (letting the model decide which queries to issue and when it has "enough"), but rejected for MVP: it would trade a validated, deterministic multi-angle retrieval sweep (already tuned and tested against a known ground-truth corpus) for a non-deterministic loop whose stopping behavior is harder to test and explain. Same principle applied consistently, not just to severity.
- Integrates with business systems: **Yes, scoped narrowly.** LangGraph remains primary orchestration for all reasoning; n8n is adopted as a thin, optional scheduling and delivery layer — a weekly Schedule Trigger that invokes the existing pipeline and posts the result to Notion ahead of a recurring leadership meeting. This is not orchestration duplication: n8n never touches retrieval, reasoning, or the severity decision tree, it only triggers the already-complete pipeline on a cadence and formats/delivers the output. Chosen because n8n's native cron trigger and Notion integration remove the need to hand-build scheduling and delivery infrastructure for this project.
- Autonomous: **Partially, by design.** Autonomous end-to-end for the majority path (retrieval through report generation); a deliberate human checkpoint (Telegram HITL) exists specifically for the highest-stakes findings (SEV-1, contradictions). Full autonomy everywhere except where the cost of an autonomous mistake is highest.

**Stack**:
- Core LLM: OpenAI — evidence extraction and report-text synthesis only, never the severity/routing decision.
- RAG: Pinecone (vector DB, one namespace per project for hard isolation), OpenAI embeddings, custom chunking pipeline, Cohere Rerank.
- Structured output: Pydantic-enforced schemas for risk items and the four-dimensional `ImpactBreakdown`.
- Agent framework: LangGraph — single pipeline, not multi-agent. Nodes are functionally separated (ingest/retrieve → validate evidence → decision tree → HITL where required → generate report) but built as one coherent graph.
- Orchestration: LangGraph conditional edges implementing the binary severity decision tree.
- UI: Streamlit — dynamic document ingestion, workflow visualisation, executive summary, evidence inspection.
- Human-in-the-loop: Telegram Bot API for approval of high-severity findings.
- Workflow visualisation: LangGraph's native Mermaid/PNG export.
- File ingestion: interactive `.md` / `.txt` / `.csv` upload pipeline that chunks, embeds, and upserts into the target Pinecone namespace without disturbing existing vectors.
- Scheduled delivery: n8n workflow (Schedule Trigger → Execute Command → Notion node) that runs the pipeline across all projects every Thursday morning and posts a combined report to Notion ahead of the leadership meeting, with any risk still awaiting Telegram HITL approval at post time clearly labeled "Pending human review" rather than presented as confirmed.

**Justification**:
- Moving severity routing to an explicit binary decision tree (not an LLM judgment call) makes the highest-stakes decision in the pipeline fully deterministic and auditable — testable with fixed inputs/outputs, and free of LLM inconsistency on the one step where consistency matters most.
- A single pipeline keeps the architecture proportional to the actual problem; the underlying node separation preserves the same "separation of concerns" a multi-agent framing would claim, without overstating the architecture.
- Pinecone namespaces (not just metadata filters) give physical evidence isolation between projects.

**Alternatives considered and dropped**:
- **LLM-based severity classification** — dropped in favor of the binary decision tree; a rule-based gate is more defensible and testable for a high-stakes escalation decision.
- **Multi-agent framing** — dropped; the underlying node separation is preserved without being marketed as separate agents.
- **n8n as primary or secondary orchestration** — dropped for MVP; explicitly optional per the brief once LangGraph is primary, and would add integration surface without changing the core story. Revisit only if a real live-ticketing-system trigger becomes a requirement (see Nice-to-have).
- **ReAct-style agentic retrieval loop** — dropped for MVP in favor of a deterministic multi-angle retrieval sweep, validated against a known ground-truth corpus; same explainability rationale applied to severity routing, applied consistently to evidence-gathering.
- **Live Jira/Slack/email integrations** — excluded from MVP; synthetic artefacts are sufficient to demonstrate and evaluate the concept, confirmed acceptable by the instructor.

---

## 3. MVP Scope

**MVP features (must have)**:
- Single LangGraph pipeline: ingest/retrieve → evidence validation → deterministic severity decision → conditional Telegram HITL → report generation.
- RAG ingestion and retrieval: documents chunked, embedded (OpenAI), stored in Pinecone (per-project namespace), retrieved and reranked (Cohere).
- Citation-or-reject validation: unsupported or invalidly cited findings are rejected before reporting.
- Context-aware evidence-consistency guardrail: cited evidence must belong to a compatible project/team context; cross-project contamination is rejected, not stitched into a risk.
- Binary decision tree: explicit rule checks; `is_sev1` or `is_contradiction` routes a finding to escalation.
- Telegram HITL approval gate for high-severity findings.
- Four-dimensional business impact breakdown (Delivery, Customer, Business/Revenue, Team) via Pydantic-enforced schema.
- Transparent evidence-confidence score: a deterministic heuristic (citation validity, source corroboration, Cohere rerank *percentile* — not an absolute score threshold — plus a base weight).
- Actionable recommendations per risk.
- Executive summary dashboard and interactive evidence inspector (raw chunks, source locations, rerank scores).
- Dynamic document ingestion (`.md` / `.txt` / `.csv`) into an existing project's live namespace.
- Synthetic/fake test data for all scenarios, confirmed acceptable by the instructor.

**Excluded from MVP**: live ticketing-system integration, multi-run trend analysis, multi-format/stakeholder-differentiated reports, real (non-synthetic) enterprise data, n8n orchestration, agentic ReAct retrieval loop.

**Justification**: proves the core value question — can grounded, contradiction-aware risk auditing be done reliably and explainably at all — before investing in infrastructure (live connectors, trend analysis) whose value depends on the core reasoning working correctly. The riskiest part isn't infrastructure, it's whether grounding and context-consistency hold up under adversarial testing; that was validated directly before expanding scope further.

**MVP specific success metrics**:
- No risk reaches the final report without a valid, existing citation.
- No risk reaches the final report if its citations describe inconsistent project contexts.
- Known negative controls (a resolved issue, an unrelated-project document) do not produce false-positive risks.
- Severity routing correctly escalates known SEV-1 and contradiction cases, and does not escalate the known clean case.

---

## 4. Risk Assessment

| Category | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| Technical | Binary decision tree misses a real severity signal outside its explicit rules | Medium | Medium | Documented as a known MVP boundary; a supplementary soft-signal LLM check is a possible v2 extension, not pretended to be exhaustive now |
| Technical | Cost-analysis step fabricates a dollar figure with no source basis | Medium | High | Four-dimensional impact structure plus confidence tagging; unsupported numeric claims are rejected structurally, same mechanism as citation validation |
| Technical | Evidence from an unrelated project/team is combined into a valid-looking risk | Medium | High | Context-aware evidence-consistency guardrail checks entity/context compatibility before a risk can be accepted; incompatible evidence is rejected with the specific mismatch shown |
| Technical | Dynamically uploaded documents get assigned to the wrong project namespace | Low–Medium | High | Controlled namespace/project selection at upload time; deliberately tested with a mis-scoped document |
| Technical | HITL gate over- or under-triggers relative to the intended severity threshold | Medium | Medium | Tested against fixed synthetic cases with known expected routing outcomes |
| Technical | Telegram approval step blocks the pipeline indefinitely with no response | Low | Medium | Timeout with a defined fallback state (marked pending, not silently dropped) |
| Data | Synthetic evaluation does not represent production enterprise variability | Medium | Medium | Explicit in documentation: the MVP demonstrates architecture and controlled behavior, not production-scale detection accuracy; a diverse synthetic corpus with deliberate edge cases mitigates but doesn't remove this |
| Business/Scope | Overstating what the system guarantees (e.g. claiming detection accuracy it hasn't measured) | Medium | High | Structural guarantees (code-enforced) kept explicitly separate from judgment-based detection quality in all documentation |

---

## 5. Implementation Plan

**Risk-first order**: the highest-risk open question wasn't infrastructure, it was whether citation-gating and context-consistency actually hold up against a real failure case rather than a hypothetical one. That was deliberately stress-tested — by uploading a real, unrelated-project document into the live corpus and confirming the system caught it — before further scope was added.

| Version | Main version goal | Hypothesis tested | Proof of hypothesis | Scope |
|---|---|---|---|---|
| V0 | Prove grounded extraction is viable | Risks can be extracted from real documents with every claim traceable to a real source chunk | Manual review: citations resolve to real chunk text, no fabricated sources | Ingestion, chunking, embedding, single-query retrieval, citation validation |
| V1 | Prove retrieval quality is sufficient | A single generic query surfaces the right evidence across risk categories | Found false: single-query retrieval missed whole risk categories (scope creep, status contradictions) | Multi-angle retrieval (pooled, deduplicated, reranked), Cohere rerank integration |
| V2 | Prove reasoning catches what retrieval alone can't | The reasoning layer can detect contradictions and scope creep given the right evidence, not just list retrieved facts | Verified against planted ground-truth cases: contradiction case caught, scope-creep case caught, negative control (resolved issue) correctly not flagged | Structured risk schema, four-dimensional impact breakdown, confidence tagging, percentile-based evidence-confidence scoring |
| V3 | Prove trust mechanisms hold under adversarial testing | Grounding and context checks catch a real failure, not just a designed test case | **Found true the hard way**: an unrelated-project document uploaded into the live corpus was cited alongside real evidence as if corroborating one claim. Context-consistency guardrail built and verified to catch and reject this exact case | Binary severity decision tree, Telegram HITL routing, context-aware evidence-consistency guardrail, dynamic document upload |
| V4 | Prove the system is demo and evaluation-ready | A fixed synthetic test suite with known expected outcomes passes end-to-end, and the system is explainable to someone other than the builder | *In progress* | Automated evaluation harness, saved sample reports, README as product case study, demo preparation |

**Timeline**: 5-day core build window

**Dependencies**: V1's multi-angle retrieval depends on V0's chunking/citation pipeline being stable; V2's reasoning layer depends on V1 supplying genuinely relevant evidence; V3's trust guardrails depend on V2's structured risk schema; V4's evaluation depends on V3's guardrails being stable enough to test against fixed cases.

**Resources needed**: solo project; existing OpenAI, Pinecone, Cohere keys; Telegram Bot API token (free tier). Budget is low — LLM calls for extraction/synthesis are the only recurring cost; the decision tree and consistency guardrail are rule-based with no API cost.

---

## 6. Success Metrics

**Delivery / technical (structural guarantees, code-enforced)**:
- No risk reaches the final report without passing citation validation.
- No risk reaches the final report if its evidence fails the context-consistency check.
- Every impact estimate is structurally represented and confidence-qualified (no ungrounded numeric claims pass silently).
- Severity routing (`is_sev1`, `is_contradiction`) runs through explicit rules, not an LLM judgment call.
- High-severity findings pass through Telegram HITL before reaching a final report.
- Every finding is inspectable: retrieved chunk, source location, and rerank score are all visible to the user.

**As a user (detection-quality / evaluation metrics)**:
- The known contradiction case and known SEV-1 case are correctly routed to HITL.
- The known clean/no-risk case is not escalated (no false-positive HITL trigger).
- The known cross-project contamination case is correctly rejected by the context-consistency guardrail.
- At least one full end-to-end run completes successfully across the synthetic corpus with correctly cited risks and appropriately tagged impact estimates.
- A reviewer can trace any reported finding back to its exact source text without needing to trust the system's own summary of it.
