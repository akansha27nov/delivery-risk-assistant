# Ground Truth — Planted Risks

**Do not ingest this file into the RAG pipeline.** It exists purely to evaluate the assistant's
output: does it surface these risks, and does it cite the correct source documents for each?

This is your answer key for the "Top 3 delivery risks this week" output and for the citation
validator. A good run should surface R1, R2, and R4 as the top risks (R3 is the interesting edge
case — see note below).

| ID | Risk | Correct source(s) | Notes |
|----|------|--------------------|-------|
| R1 | Critical-path ticket ATL-142 blocked 9 days on external partner dependency; threatens Aug 14 launch | `sprint_report.md`, `ticket_export.csv`, `standup_transcript.txt` | Corroborated across all 3 docs — good test of multi-source citation |
| R2 | Uncontrolled mid-sprint scope addition (ATL-158/159/160) without timeline renegotiation | `sprint_report.md`, `ticket_export.csv`, `stakeholder_email.md`, `standup_transcript.txt` | Also corroborated across sources |
| R3 | Attrition/retention risk — engineer (Sara) signaling burnout and looking at other roles | `standup_transcript.txt` ONLY | **Single-source, sensitive.** Use this to test that the agent (a) doesn't fabricate corroboration from other docs, and (b) handles a people-risk with appropriate tone — not overclaiming ("employee will quit") but flagging it accurately ("signaled they are exploring other opportunities"). Good talking point in interviews about responsible AI use in people contexts. |
| R4 | Declining velocity (38 → 29 → 22 pts) over 3 sprints; QA capacity gap (1 QA engineer vs. usual 2) | `sprint_report.md`, `ticket_export.csv` (ATL-162 blocked reason) | Quantitative trend risk |

## Batch 2 — Team Nova / Checkout Redesign

A second, noisier corpus: `nova_sprint_report.md`, `nova_incident_postmortem.md`,
`nova_slack_thread.txt`, `nova_retro_notes.md`, `nova_exec_status_email.md`. This batch tests
different failure modes than Batch 1 — retrieval robustness against irrelevant chatter, and
whether the agent's reasoning goes beyond keyword-spotting into actual judgement.

| ID | Risk | Correct source(s) | Notes |
|----|------|--------------------|-------|
| R5 | Unassigned, undated remediation ticket (NOV-204) for a SEV-1 payment defect; redesign introduces two new retry paths that inherit the same defect if unfixed before Sept 1 launch | `nova_incident_postmortem.md`, `nova_slack_thread.txt`, `nova_retro_notes.md` | Tests whether the agent connects an incident report to a *future* launch risk, not just a past-tense event |
| R6 | Payments v2 API hard deprecation (2026-08-20) lands before the Sept 1 launch, ahead of the team's own v3 migration pace | `nova_slack_thread.txt`, `nova_retro_notes.md` | Buried in the Slack thread among off-topic chat (game talk, coffee run, plant jokes, emoji reactions) — good test of whether reranking actually filters noise rather than just truncating by position |
| R8 | **Status misrepresentation risk:** the exec status email reports "no blockers to flag" and full green status the same week that R5 and R6 were actively being discussed as unresolved risks by the same author (Tom) in the retro and Slack | `nova_exec_status_email.md` vs. `nova_incident_postmortem.md`, `nova_slack_thread.txt`, `nova_retro_notes.md` | **The hardest test case.** This isn't a risk stated in any single document — it's a *contradiction* the agent has to detect by comparing sources. A shallow system that just extracts stated risks per-document will miss this entirely. Also a strong interview talking point: this is the exact "someone has to manually piece it together" problem from the pitch. |

### Negative control (expanded)

- No document mentions budget overruns or a third-party vendor contract dispute — if the
  assistant surfaces either, that's a hallucination.
- **NOV-175 (CI pipeline flakiness) is explicitly resolved** in both `nova_sprint_report.md` and
  `nova_retro_notes.md`. If the assistant lists this as a current risk, that's a recency failure —
  it retrieved a chunk but didn't register that the chunk describes a *closed* issue. This is a
  more subtle trap than "no evidence exists" and worth calling out separately in your eval report.
