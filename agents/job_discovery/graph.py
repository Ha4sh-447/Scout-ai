from langgraph.graph import END, StateGraph

from agents.job_discovery.agent import deduplicate_node, deduplicate_raw_node, parse_node, scrape_node
from agents.job_discovery.state import JobDiscoveryState


def build_job_discovery_graph():
    graph = StateGraph(JobDiscoveryState)

    # Nodes
    graph.add_node("scrape",                scrape_node)
    graph.add_node("deduplicate_raw",       deduplicate_raw_node)
    graph.add_node("parse",                 parse_node)
    graph.add_node("deduplicate",           deduplicate_node)
 
    graph.set_entry_point("scrape")
    graph.add_edge("scrape",                "deduplicate_raw")
    graph.add_edge("deduplicate_raw",       "parse")
    graph.add_edge("parse",                 "deduplicate")
    
    # Conditional edge for adaptive freshness
    graph.add_conditional_edges(
        "deduplicate",
        lambda state: "scrape" if state.get("status") == "retry_fresher" else END
    )

    return graph.compile()


job_discovery_graph = build_job_discovery_graph()
