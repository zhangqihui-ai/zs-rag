from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes import (
    generate_node,
    grade_node,
    retrieve_node,
    rewrite_node,
    route_node,
    should_retrieve_after_route,
    should_rewrite_or_generate,
)
from .state import AgenticRAGState


def build_agentic_rag_graph():
    graph = StateGraph(AgenticRAGState)
    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("route")
    graph.add_conditional_edges(
        "route",
        should_retrieve_after_route,
        {"retrieve": "retrieve", "generate": "generate"},
    )
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        should_rewrite_or_generate,
        {"rewrite": "rewrite", "generate": "generate"},
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", END)
    return graph.compile()
