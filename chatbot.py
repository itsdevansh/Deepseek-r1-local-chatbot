import os
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
from langchain_core.prompts import ChatPromptTemplate
import io
import json
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END, MessagesState
from event_handler import create_event, get_events, update_event, delete_event

load_dotenv()


def init_model() -> ChatOllama:
    try:
        MODEL_NAME = os.getenv("MODEL_NAME")
        llm = ChatOllama(
            model="llama3.2:latest",
            temperature=0.3,
            # other params...
        )
        llm.format = "json"
        print(llm)
        return llm
    except Exception as e:
        print(f"Model cannot be initialized: {e}")



def agent(llm: ChatOllama, user_message: str):
    tools = [create_event, get_events, update_event, delete_event]
    memory = MemorySaver()
    graph = create_react_agent(llm, tools=tools, checkpointer=memory)
    return graph


def print_stream(stream):
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()



if __name__ == "__main__":
    # events = get_events({})
    # for event in events['items']:
    #     print(event['summary'])
    llm = init_model()
    config = {"configurable": {"thread_id": "1"}}
    inputs = {"messages": [("user", "Can you create an event on 26 january 2025 from 1pm tp 2pm? for a meeting at 110 stewart street")]}
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent",agent)
    workflow.add_edge("START",agent)
    workflow.add_edge("agent",END)
    graph = agent(llm, inputs)
    print_stream(graph.stream(inputs, config=config, stream_mode="values"))