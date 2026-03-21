from langgraph.graph import StateGraph, END

from agents.resume_matching.agent import resume_matching_node
from agents.resume_matching.state import ResumeMatchingState


def build_resume_matching_graph():
    """
    Minimal single-node graph for resume matching.
    Kept as a separate graph (not merged into job_discovery) so it can be:
      - run independently in tests
      - invoked by the orchestrator after job discovery completes
      - extended later (e.g. add a skill_extraction node before matching)
    """
    graph = StateGraph(ResumeMatchingState)
    graph.add_node("resume_matching", resume_matching_node)
    graph.set_entry_point("resume_matching")
    graph.add_edge("resume_matching", END)
    return graph.compile()


resume_matching_graph = build_resume_matching_graph()
