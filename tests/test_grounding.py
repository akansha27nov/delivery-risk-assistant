"""
Phase 4: This is your evaluation layer, made concrete and automatable —
not just a manual eyeball check.

Two things to assert once agent.py is implemented:

1. Every citation on every returned risk maps to a real chunk_id that
   exists in the vector store (no hallucinated sources).
2. The single-source attrition risk (R3 in docs/ground_truth_risks.md)
   is NOT reported with citations from sprint_report.md or
   ticket_export.csv — only standup_transcript.txt. If the model cites
   those other docs for R3, that's a fabricated-corroboration failure,
   which is the specific failure mode this project is designed to catch.
"""

import pytest


def test_all_citations_resolve_to_real_chunks():
    # TODO Phase 4: run the graph on the sample corpus, assert every
    # citation on every risk resolves to a chunk_id that was actually
    # retrieved.
    pytest.skip("Implement once src/agent.py and src/graph.py are built")


def test_attrition_risk_is_single_sourced():
    # TODO Phase 4: assert the attrition/retention risk's citations are
    # all from standup_transcript.txt and nothing else.
    pytest.skip("Implement once src/agent.py and src/graph.py are built")
