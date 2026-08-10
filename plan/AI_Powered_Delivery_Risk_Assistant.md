# 🛡️ AI-Powered Delivery Evidence Auditor

## The Problem: The "Watermelon" Status Report

**Status reports have a watermelon problem: green on the outside, red on the inside.**

Imagine a programme lead receives a weekly status report saying a project is on track.

But somewhere else, in a ticket export, there's a critical dependency that's blocked. And in a standup transcript, an engineer says they don't expect to make the deadline.

All of that information exists. 

Existing delivery platforms are getting increasingly good at analysing the data inside the systems they connect to. My hypothesis is that an important gap remains between those systems and the narrative information around them — status reports, meeting transcripts, postmortems and other unstructured artefacts.

I'm interested in whether AI can audit that narrative against the underlying evidence rather than simply summarising it.

And that's the problem I want to explore with my **AI Delivery Evidence Auditor**

---

# The Proposal

The idea is to take project artefacts such as sprint reports, ticket exports, standup transcripts and status documents, and use AI to cross-reference them and surface the delivery risks that might otherwise be missed.

I'm particularly interested in three types of signals:

1. **Delivery risks** — things like blocked dependencies, capacity problems or deadlines at risk.

2. **Scope risks** — for example, work being added during a sprint without a corresponding change to the timeline.

3. **Status contradictions** — where the official status says one thing, but the underlying evidence suggests something different.

But there is a second problem I want the project to address.

# How do we trust an AI-generated risk?

I don't want to build another chatbot where the user simply has to trust the model's answer.

My design principle is:

**If the system can't show me the evidence behind a risk, it shouldn't report that risk.**

So I'm proposing a RAG-based architecture that retrieves relevant evidence and then validates that every finding has a traceable citation.

I'm also planning a **context-consistency** check because there's an interesting failure mode here: two pieces of information can both be individually true but belong to completely different projects or teams. The system shouldn't combine them into one risk simply because they appear semantically related.

For high-stakes findings, such as a SEV-1 incident or a contradiction between reported status and underlying evidence, I also don't want the AI making the final escalation decision autonomously.

The proposal is therefore to have a deterministic decision layer and a human approval step before those findings reach the leadership report.

# The proposed technology

I'm planning to use **Pinecone and Cohere for retrieval, LangGraph for workflow orchestration, Pydantic for structured outputs, and Streamlit for the interface,** with Telegram providing the human-in-the-loop approval mechanism.

But the technology isn't the hypothesis I'm trying to prove.

The hypothesis is whether AI can reliably connect distributed project evidence while remaining grounded and explainable enough to support delivery decisions.

I don't have access to real company Jira or Slack data, so the initial version will use **synthetic but deliberately designed project artefacts** — including known risks, clean cases and contradiction cases.

That actually gives me something valuable for the MVP: I can define the expected outcome beforehand and evaluate whether the system gets it right.

# MVP Goal
My goal isn't to claim that the AI will detect every possible delivery risk.

**The goal of the MVP is to demonstrate whether we can use AI to connect distributed project evidence while putting explicit controls around grounding, context and high-stakes decisions.**

If that works, the next step would be a pilot with real project data and eventually live integrations with systems such as Jira or Slack.

---

# Conclusion

So the question I'm ultimately exploring is not:

**"Can AI summarize project information?"**

It's:

**"How can we safely use AI to improve operational decision-making without treating the AI itself as the source of truth?"**

