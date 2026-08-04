"""
Phase 4: Wire the LangGraph state machine:

    START -> Load User Question -> Retrieve Documents -> Enough Evidence?
      -- No  --> Ask for More Documents --> END
      -- Yes --> Analyse Risks -> Validate Citations -> Citation Missing?
                   -- Yes --> Reject Response --------------------> END
                   -- No  --> Generate Report ----------------------> END

Reuse the LangGraph wiring pattern from:
  github.com/akansha27nov/Wire-IDE-to-the-protocol-era
"""


def build_graph():
    """
    Assemble the StateGraph with nodes for each step above and the two
    conditional edges ("Enough Evidence?" and "Citation Missing?").
    Return the compiled graph, ready for app.py to invoke.
    """
    raise NotImplementedError
