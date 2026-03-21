from langgraph.graph import StateGraph, END

from agents.notification.agent import notification_node
from agents.notification.state import NotificationState

def build_notification_graph():
    graph = StateGraph(NotificationState)
    graph.add_node("notification", notification_node)
    graph.set_entry_point("notification")
    graph.add_edge("notification", END)
    return graph.compile()

notification_graph = build_notification_graph()
