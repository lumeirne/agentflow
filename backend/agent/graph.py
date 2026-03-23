"""LangGraph graph definition — wires nodes and edges for the AgentFlow agent."""

from langgraph.graph import StateGraph, END

from backend.agent.state import AgentState
from backend.agent.nodes import planner_node, executor_node, human_approval_node, reviewer_node


def _route_after_planner(state: AgentState) -> str:
    """Decide next node after planner."""
    if state.get("error"):
        return END
    if not state.get("plan"):
        return END
    return "executor"


def _route_after_executor(state: AgentState) -> str:
    """Decide next node after executor."""
    if state.get("requires_approval"):
        return "human_approval"

    plan = state.get("plan", [])
    index = state.get("current_step_index", 0)

    if index >= len(plan):
        return "reviewer"
    return "executor"


def _route_after_approval(state: AgentState) -> str:
    """Decide next node after human_approval."""
    plan = state.get("plan", [])
    index = state.get("current_step_index", 0)

    if index >= len(plan):
        return "reviewer"
    return "executor"


def build_agent_graph() -> StateGraph:
    """Construct and compile the LangGraph agent graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("reviewer", reviewer_node)

    # Set entry point
    graph.set_entry_point("planner")

    # Add conditional edges
    graph.add_conditional_edges("planner", _route_after_planner)
    graph.add_conditional_edges("executor", _route_after_executor)
    graph.add_conditional_edges("human_approval", _route_after_approval)

    # Reviewer always goes to END
    graph.add_edge("reviewer", END)

    return graph.compile()
