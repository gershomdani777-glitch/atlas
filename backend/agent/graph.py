from langgraph.graph import StateGraph, END
from .state import AgentState
from . import nodes as _nodes


def build_graph(
    perceive=_nodes.perceive,
    interpret=_nodes.interpret,
    classify_regime=_nodes.classify_regime,
    allocate_risk_check=_nodes.allocate_risk_check,
    execute=_nodes.execute,
    observe_outcome=_nodes.observe_outcome,
    adapt=_nodes.adapt,
):
    """Node functions are keyword-overridable so tests can compile a graph
    with e.g. a mocked `interpret` (no live Gemini call) or a no-op
    `perceive` (no live Redis) without touching production wiring."""
    workflow = StateGraph(AgentState)

    workflow.add_node("perceive", perceive)
    workflow.add_node("interpret", interpret)
    workflow.add_node("classify_regime", classify_regime)
    workflow.add_node("allocate_risk_check", allocate_risk_check)
    workflow.add_node("execute", execute)
    workflow.add_node("observe_outcome", observe_outcome)
    workflow.add_node("adapt", adapt)

    workflow.set_entry_point("perceive")

    workflow.add_edge("perceive", "interpret")
    workflow.add_edge("interpret", "classify_regime")
    workflow.add_edge("classify_regime", "allocate_risk_check")
    workflow.add_edge("allocate_risk_check", "execute")
    workflow.add_edge("execute", "observe_outcome")
    workflow.add_edge("observe_outcome", "adapt")
    workflow.add_edge("adapt", END)

    return workflow.compile()


atlas_app = build_graph()
