from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from .state import AnalysisState
from . import nodes


def build_graph(llm):
    g = StateGraph(AnalysisState)
    g.add_node("scope", nodes.scope)
    for name in ("lab", "symptom", "cycle"):
        g.add_node(f"{name}_agent", nodes.make_specialist(name, llm))
    g.add_node("discordance", nodes.discordance)
    g.add_node("debate", nodes.make_debate(llm))
    g.add_node("critic", nodes.make_critic(llm))
    g.add_node("report", nodes.report)
    g.add_edge(START, "scope")
    for name in ("lab", "symptom", "cycle"):
        g.add_edge("scope", f"{name}_agent")
    g.add_edge(["lab_agent", "symptom_agent", "cycle_agent"], "discordance")
    g.add_conditional_edges(
        "discordance",
        lambda s: "debate" if (s.get("discordance") or {}).get("conflict") else "critic",
        {"debate": "debate", "critic": "critic"},
    )
    g.add_edge("debate", "critic")
    g.add_edge("critic", "report")
    g.add_edge("report", END)
    return g.compile()
