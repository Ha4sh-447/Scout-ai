from langgraph.graph import StateGraph, END

from agents.ranking.agent import ranking_node
from agents.ranking.state import RankingState


def build_ranking_graph():
    graph = StateGraph(RankingState)
    graph.add_node("ranking", ranking_node)
    graph.set_entry_point("ranking")
    graph.add_edge("ranking", END)

    return graph.compile()


ranking_graph = build_ranking_graph()
