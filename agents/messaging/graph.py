from langgraph.graph import StateGraph, END

from agents.messaging.agent import messaging_node
from agents.messaging.state import MessagingState

def build_messaging_graph():
    graph = StateGraph(MessagingState)
    graph.add_node("messaging", messaging_node)
    graph.set_entry_point("messaging")
    graph.add_edge("messaging", END)

    return graph.compile()

messaging_graph = build_messaging_graph()
