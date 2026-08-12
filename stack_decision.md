# 🛠️ Stack Decision & Rationale

**Primary Stack Choice:** **LangGraph (Python)**

For the Delivery Risk Assistant MVP, LangGraph has been selected as the primary orchestration and agentic workflow stack.

**Why LangGraph fits this problem:** Enterprise risk auditing requires strict deterministic routing, multi-angle parallel vector retrieval, stateful citation validation loops, and human-in-the-loop (HITL) safety gates.

1. **Complex State Management:** Delivery risk auditing requires maintaining a complex state across multiple operational steps (retrieving evidence, multi-angle synthesis, confidence calculation, citation validation, and HITL severity routing). LangGraph's typed state dictionary allows seamless data flow between nodes.

2. **Deterministic & Conditional Control Flows:** Unlike linear chain frameworks, LangGraph enables precise graph-based routing (e.g., conditionally gating high-severity or contradictory risks into human-in-the-loop review nodes while passing clean reports instantly).

3. **Deep Python Ecosystem Integration:** The system relies heavily on specialized data science and vector libraries (`pinecone-client`, `cohere`), which integrate natively into a Python-first framework.

4. **Rigorous Testability:** There is a test suite (`test_grounding.py`), a code-first graph architecture makes it straightforward to write integration tests validating citation precision, negative controls, and cross-project isolation.

**Why n8n is secondary for this MVP:** 
1. While n8n excels at linear webhook workflows (an exported workflow and screenshots are included in `workflow/` and `screenshots/`), managing deterministic branching and citation-gating logic, custom Cohere reranking arrays, and strict citation-gating logic becomes brittle in a visual node environment compared to pure Python graph definitions.
2. **Lack of Granular Code Control:** Implementing multi-angle asynchronous retrieval, custom retrieval orchestration and reranking logic, and dynamic Pydantic data validation (agent.py) becomes cumbersome and inflexible inside drag-and-drop visual workflow canvases.
3. **Testing & CI/CD Friction:** Automated testing of complex semantic assertions via pytest is considerably more robust and mature in a native Python code repository than in a visual automation platform.

## Where n8n is actually used

As a thin, optional scheduling and delivery layer — a weekly cron trigger that invokes the existing LangGraph pipeline and posts the audit to Notion ahead of the leadership meeting. It never touches retrieval, reasoning, or severity routing. See [n8n_notion_justification.md](n8n_notion_justification.md) for the full design rationale and the specific escalation-handling decision this required.