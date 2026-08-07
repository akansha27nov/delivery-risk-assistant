# Project Plan (Revised per instructor feedback)

## 1. Use Case

**Problem statement:** Programme leaders spend hours a week manually piecing together delivery risk from sprint reports, tickets, postmortems, and status emails — and status can quietly diverge from reality between what's reported up and what's actually happening in the tracker, with no automated check catching the gap before it reaches leadership.

**Target users:** Engineering managers, delivery/programme leads, and the leadership they report to (as the recipient of the executive briefing).

**Verify:** Every risk claim in the final report traces back to a cited source chunk — if it can't cite one, it doesn't get to say it. Severity routing (does this go straight into the report, or does it require human approval first) is determined by an explicit binary decision tree, not a model judgment call — so the routing logic is inspectable and explainable.

**Current process:** Manual synthesis — reading standups, ticket exports, and status docs by hand, with no structural check for contradictions between what's reported and what's actually recorded elsewhere.

*(Note: uses synthetic/fake sprint and postmortem data — confirmed acceptable by instructor, no real company data required.)*

---

## 2. Technology Stack

- **Core LLM:** OpenAI, used for evidence extraction and report-text synthesis only — not for the severity/routing decision (see below).
- **RAG components:** Pinecone (vector DB), OpenAI embeddings, existing chunking pipeline, Cohere rerank.
- **Agent framework:** LangGraph — **single pipeline**, not a multi-agent architecture (per instructor feedback). Nodes remain functionally separated (ingest/retrieve → validate citations → decision tree → generate report) but are framed and built as one coherent graph, not as independently-branded agents.
- **Orchestration:** LangGraph conditional edges implementing the binary decision tree for severity routing.
- **Tools/integrations:** Telegram Bot API for the human-in-the-loop approval step (confirmed with instructor — Telegram, not Slack).

**Justification:**
- Moving severity routing to an explicit binary decision tree (rather than an LLM judgment call) makes the highest-stakes decision in the pipeline — whether a risk requires human approval before reaching leadership — fully deterministic and auditable. This is a stronger design than the original LLM-judgment version: it's explainable, testable with fixed inputs/outputs, and doesn't inherit LLM inconsistency on the one step where consistency matters most.
- A single pipeline (not multiple agents) keeps the architecture proportional to the actual problem — three distinct "agents" implied more independent complexity than the workflow actually has; one graph with clear node boundaries communicates the same separation of concerns without overstating the architecture.
- Telegram: lightweight bot API integration, no workspace approval overhead, well-suited to a single-approver MVP.

**Alternatives considered:**
- LLM-based severity classification — dropped in favor of the binary decision tree specifically because a rule-based gate is more defensible and testable for a high-stakes escalation decision.
- Multi-agent framing — dropped per instructor feedback; the underlying node separation is preserved, just not marketed as separate agents.

**Trade-offs:**
- A rule-based decision tree is less flexible than an LLM judgment call — it won't catch severity signals outside its explicit rules (e.g. a contradiction phrased in a way the rules don't check for). Accepted trade-off: for the MVP, explainability and testability outweigh the marginal recall a more flexible LLM classifier might add. This is an explicit, documented boundary rather than an unexamined gap — a natural v2 extension (see below).

---

## 3. MVP Scope

**Brainstormed feature list:** single-pipeline citation-gated risk auditing; binary decision-tree severity routing; per-risk cost/impact estimation; Telegram HITL approval gate; agent operating-cost tracking; stakeholder-differentiated report formats; risk trend tracking across runs; live ticketing-system ingestion.

**Must-have (MVP):**
- Single LangGraph pipeline: ingest/retrieve → validate citations → binary decision tree for severity → (conditionally) Telegram HITL approval → generate report.
- Citation-or-reject validation (already built).
- Binary decision tree with explicit, testable steps (see Section 5 for the exact rule sequence).
- Per-risk cost/impact estimation with a confidence tag distinguishing source-grounded estimates from directional ones.
- Telegram approval gate, triggered only by the decision tree's high-severity branch.
- Synthetic/fake data for all test scenarios.

**Should-have (v2):**
- A supplementary LLM-based "soft signal" check running alongside the binary tree — flagging cases the deterministic rules might miss, surfaced as a lower-confidence suggestion rather than an automatic escalation. This directly addresses the binary tree's known recall trade-off without giving up its explainability for the primary path.
- Agent operating-cost tracking (tokens/API cost per run).

**Nice-to-have (v3+):**
- Live ingestion from Jira/Linear APIs.
- Multi-run risk trend tracking.
- Stakeholder-differentiated report formats.

**Excluded from MVP:** live ticketing integration, trend analysis across runs, multi-format reports, real (non-synthetic) data sourcing.

---

## 4. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Binary decision tree misses a real severity signal outside its explicit rules | Medium | Medium | Documented as a known MVP boundary, not hidden; v2 adds a supplementary soft-signal LLM check rather than pretending the rule set is exhaustive |
| Cost-analysis step fabricates a dollar figure with no source basis | Medium | High | Every cost estimate carries a `confidence_tag` (`estimated_from_source_data` vs. `directional_estimate`); reject ungrounded numeric claims structurally, same mechanism as citation validation |
| HITL gate over- or under-triggers relative to the intended severity threshold | Medium | Medium | Test the decision tree explicitly against a fixed synthetic test set with known expected outcomes before considering it tuned — not just eyeballing outputs |
| Telegram approval step blocks the pipeline indefinitely with no response | Low | Medium | Timeout with a defined fallback state (marked pending, not silently dropped) |
| Overstating what the system guarantees (e.g. claiming 100% detection accuracy) | Medium | High | Success metrics explicitly separate structural guarantees from judgment-based detection quality (see Section 6) — corrected per instructor feedback |

---

## 5. Implementation Plan

**Phase 1 — Setup and data preparation (Day 1):**
- Finalize the synthetic test corpus (sprint reports, postmortems, one known contradiction case, one known SEV-1 case, one known clean/no-risk case).
- Confirm the exact binary decision tree rule sequence, e.g.:
  1. Does the claim have a citation? No → reject.
  2. Does the cited source actually support the claim? No → reject.
  3. Does another source contradict this claim? Yes → route to HITL.
  4. Is the source explicitly tagged SEV-1 (or equivalent)? Yes → route to HITL.
  5. Otherwise → include directly in report.

**Phase 2 — Core pipeline development (Day 2–3):**
- Build/confirm citation validation node (existing).
- Implement the binary decision tree as explicit conditional edges, not an LLM call.
- Build cost/impact estimation with confidence tagging.

**Phase 3 — Integration and testing (Day 4):**
- Integrate Telegram Bot API.
- Run the pipeline against the fixed synthetic test set; verify the decision tree produces the expected routing outcome on each known case (contradiction → HITL, SEV-1 → HITL, clean case → direct inclusion).

**Phase 4 — Deployment and monitoring (Day 5):**
- Documentation, README update reflecting single-pipeline architecture.
- Demo preparation.

**Timeline:** 5-day window.

**Key milestones:** decision tree rules finalized (end Day 1), pipeline running end-to-end without HITL (end Day 2), HITL gate integrated and passing all known test cases (end Day 4).

**Dependencies:** Phase 2 depends on Phase 1's rule sequence being locked; Phase 3's testing depends on Phase 2's decision tree being stable.

**Resources needed:**
- **Team:** solo project.
- **Tools/services:** existing OpenAI, Pinecone, Cohere keys; new Telegram Bot API token (free).
- **Budget:** low — primarily LLM calls for extraction/synthesis; the decision tree itself is free (rule-based, no API cost).

---

## 6. Success Metrics

**Structural guarantees (code-enforced, not a model accuracy claim):**
- No risk reaches the final report without passing the citation-check filter — this is a hard rule in code, true by construction, not a claim about how often the model gets it right.
- No cost estimate reaches the report without a confidence tag — same mechanism.

**Detection-quality metrics (evaluated against the fixed synthetic test set, realistic thresholds):**
- The decision tree correctly routes the known contradiction case and the known SEV-1 case to the HITL gate.
- The decision tree does not route the known clean/no-risk case to HITL (no false-positive escalation on the negative control).
- At least one full end-to-end run completes successfully across the synthetic test corpus, producing a report with correctly cited risks and appropriately tagged cost estimates.

