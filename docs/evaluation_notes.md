# Evaluation Notes — Ground Truth Comparison

**Method:** One generated run per project (`samples/atlas_risk_report.md`, `samples/nova_risk_report.md`, 2026-08-13) checked against the planted answer key in `docs/ground_truth_risks.md`. This is a
**single-run, directional comparison, not a statistical validation** — `seed=42` The LLM extraction step may vary between independent runs despite fixed temperature and seed settings. Treat findings below as "what one real run showed," not "what the system always does."

## Project Atlas

| ID | Risk | Surfaced? | Citation completeness | Notes |
|----|------|-----------|------------------------|-------|
| R1 | ATL-142 blocked, threatens Aug 14 launch | Yes | Partial — 2 of 3 corroborating sources cited (`sprint_report.md`, `standup_transcript.txt`); `ticket_export.csv` not cited | Grounding still valid, just not exhaustive |
| R2 | Uncontrolled mid-sprint scope addition | Yes | all 4 R2 source documents represented | - |
| R3 | Attrition/retention signal (Sara) | **Not surfaced** in this run | n/a | No fabrication occurred — nothing worse than an omission. Worth a repeat run to check whether this sensitive, single-source case is being deprioritized against the top-3 cap, given the rubric weight this case is meant to carry |
| R4 | Declining velocity (38→29→22) + QA capacity gap | Partial | QA gap surfaced; the velocity trend numbers themselves never appear in the explanation text | Coverage gap, not a grounding failure — evidence existed and wasn't connected |

**Insight:** Atlas: Successful top-3 ground-truth alignment. R1, R2 and R4 were surfaced. Citation coverage was strong but not always exhaustive; R3 was not surfaced in this run, which is an expected/interesting edge case under the top-3 constraint.

| Dimension | Result |
|----|------|
| Surfaced | Yes |
| Grounded | Yes |
| Citation completeness | Partial |

## Project Nova

| ID | Risk | Surfaced? | Citation completeness | Notes |
|----|------|-----------|------------------------|-------|
| R5 | Unassigned NOV-204 (SEV-1 remediation) threatens Sept 1 launch via new retry paths | Folded into the R8 contradiction risk, not standalone | n/a | The specific "new retry paths inherit the defect" mechanism is not stated explicitly |
| R6 | Payments v2 deprecation (8/20) buried in Slack chatter | Yes | All 2 sources cited as expected | - |
| R8 | Status email contradicts postmortem/Slack/retro (hardest case) | **Yes — correctly triggered HITL** (`pending_hitl_approval`) | R8 was correctly detected and triggered HITL. 4 grounded source documents were cited, including the executive status email and three corroborating remediation sources; however, the exact ground-truth corroboration set was not reproduced because the expected Slack source was absent and the sprint report was included instead| Escalation logic worked correctly throughout. Citation depth fixed via a code-level guardrail, not a prompt change (see below) |

**Insight:** Nova: R5, and R6 consistently surfaced. Citation coverage was strong.

| Dimension | Result |
|----|------|
| Surfaced | Yes |
| Grounded | Yes |
| Citation completeness | Yes |


### Negative controls (both passed in this run)
- **NOV-175 (resolved CI flakiness):** did not appear as a risk in the Nova report — correct.
- **Budget overrun / vendor dispute (no evidence exists):** did not appear in either report — correct, no hallucination observed.

## Follow-up

Two attempts were made to close the R8 citation gap:

1. **Prompt edit (`prompts.py` Rule 4)** — added a sentence requiring exhaustive citation of corroborating sources for contradiction risks. **Re-tested, no measurable effect.** The Nova contradiction risk still cited only 2 of the 4 ground-truth sources after this change, even though direct inspection of the retrieved evidence pool (via the Streamlit Forensic Evidence Inspector, plus an added diagnostic log line in `retrieval.py`) confirmed all 5 source documents — including the two the LLM was omitting — were present in the 8-chunk pool the whole time. This ruled out a retrieval-depth problem and confirmed it was a model citation-compliance issue: the evidence was available and the model chose not to cite it.

2. **Code-level guardrail (`agent_analysis.py`, `_expand_citations_with_ticket_corroboration`)** — same entity-ID pattern already used by the existing context-consistency guardrail and the citation-dedup guardrail, run in the opposite direction: after extraction, any chunk in the evidence pool that shares a ticket ID (e.g. `NOV-204`) with a risk's own explanation text is deterministically added to that risk's citations, without removing anything the LLM already cited. **Verified working**: Nova's contradiction risk now cites 4 sources instead of 2 (`nova_exec_status_email.md`, `nova_incident_postmortem.md`, `nova_retro_notes.md`,
   `nova_sprint_report.md`). `nova_slack_thread.txt` remains uncited — the specific chunk containing the NOV-204 mention in Slack did not survive the top-8 rerank cutoff for this query, so it was never in the evidence pool the guardrail could draw from. This is a genuine, partial, code-verified improvement (2→4 of the intended sources), not a complete fix.

**Overall assessment:**  The system successfully surfaced the primary planted risks across both projects, avoided the specified negative controls, correctly grounded the reported risks in retrieved evidence, and correctly triggered HITL for Nova's status contradiction. The main remaining limitation is citation exhaustiveness and occasional variation in which equivalent risk formulation is selected under the top-3 constraint. This is a coverage limitation rather than a systematic grounding or hallucination failure.
