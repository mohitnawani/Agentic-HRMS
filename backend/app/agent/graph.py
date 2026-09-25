"""Compiled LangGraph skeleton for Agentic HRMS request routing."""

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.action_agent import action_agent_node
from app.agent.nodes.database_agent import database_agent_node
from app.agent.nodes.memory import load_memory_node, save_memory_node
from app.agent.nodes.rag_agent import rag_agent_node
from app.agent.nodes.response_generator import response_generator_node
from app.agent.state import AgentInput, AgentOutput, AgentRuntimeContext, AgentState
from app.agent.supervisor import route_from_supervisor, supervisor_node


def build_agent_graph():
    builder = StateGraph(
        AgentState,
        context_schema=AgentRuntimeContext,
        input_schema=AgentInput,
        output_schema=AgentOutput,
    )
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("rag_agent", rag_agent_node)
    builder.add_node("database_agent", database_agent_node)
    builder.add_node("action_agent", action_agent_node)
    builder.add_node("response_generator", response_generator_node)
    builder.add_node("save_memory", save_memory_node)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "rag_agent": "rag_agent",
            "database_agent": "database_agent",
            "action_agent": "action_agent",
            "response_generator": "response_generator",
        },
    )
    builder.add_edge("rag_agent", "response_generator")
    builder.add_edge("database_agent", "response_generator")
    builder.add_edge("action_agent", "response_generator")
    builder.add_edge("response_generator", "save_memory")
    builder.add_edge("save_memory", END)
    return builder.compile(name="agentic-hrms-supervisor")


agent_graph = build_agent_graph()
