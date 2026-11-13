"""Shared LangGraph workflow for the local travel support chat."""

import re
from typing import TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from claims import claim_with_policy


class SupportState(TypedDict, total=False):
    question: str
    claim_id: str
    route: str
    clarification: str
    result: dict


def route_question(state: SupportState) -> dict:
    question = state["question"]
    ids = set(re.findall(r"\bRK-[0-9]{4}\b", question.upper()))
    if len(ids) > 1:
        return {"route": "clarify", "clarification": "Bitte frage jeweils nach einem Vorgang."}
    if ids:
        return {"route": "claim", "claim_id": ids.pop()}
    if re.search(r"\b(?:status|bearbeitungsstand|stand)\b|\bRK-", question, re.IGNORECASE):
        return {"route": "clarify", "clarification": "Wie lautet die Vorgangsnummer? Beispiel: RK-1042."}
    return {"route": "policy"}


def answer_travel_question(library, owner: str, question: str) -> dict:
    """Run one request with the identity supplied by the authenticated caller."""
    question = question.strip()
    if not 1 <= len(question) <= 2000:
        raise ValueError("Bitte eine Frage mit 1 bis 2.000 Zeichen eingeben.")

    @tool
    def get_claim_status(claim_id: str) -> dict | None:
        """Read one claim and its supporting policy for the current account."""
        return claim_with_policy(library, owner, claim_id)

    @tool
    def search_policy(query: str) -> list[dict]:
        """Find authorized policy excerpts for the current account."""
        return [{"title": hit.title, "excerpt": hit.text} for hit in library.search(owner, query)]

    def lookup(state: SupportState) -> dict:
        claim = get_claim_status.invoke({"claim_id": state["claim_id"]})
        if claim is None:
            return {"result": {"status": "not_found", "answer": "Kein sichtbarer Vorgang gefunden.", "sources": []}}
        return {"result": {
            "status": "answered",
            "answer": f"{claim['status']}. {claim['deduction_reason']}",
            "sources": [{"title": claim["policy_title"], "excerpt": claim["policy_excerpt"]}],
        }}

    def retrieve(state: SupportState) -> dict:
        hits = search_policy.invoke({"query": state["question"]})
        if not hits:
            return {"result": {"status": "not_found", "answer": "Kein passender Beleg gefunden.", "sources": []}}
        return {"result": {"status": "answered", "answer": hits[0]["excerpt"], "sources": hits[:1]}}

    def clarify(state: SupportState) -> dict:
        return {"result": {"status": "clarify", "answer": state["clarification"], "sources": []}}

    graph = StateGraph(SupportState)
    graph.add_node("route", route_question)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", lambda state: state["route"], ["claim", "policy", "clarify"])
    for name, handler in (("claim", lookup), ("policy", retrieve), ("clarify", clarify)):
        graph.add_node(name, handler)
        graph.add_edge(name, END)

    # Local claim and policy data must never enter a hosted tracing service.
    from langsmith import tracing_context

    with tracing_context(enabled=False):
        return graph.compile().invoke({"question": question})["result"]
