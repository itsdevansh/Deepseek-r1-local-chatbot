import os
import asyncio
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.state import CompiledStateGraph
from event_handler import create_event, get_events, update_event, delete_event
from langgraph.types import StateSnapshot
from langchain_core.messages import AIMessage, HumanMessage
from datetime import datetime

# Load environment variables
load_dotenv()

tools = [create_event, get_events, update_event, delete_event]

# Initialize the model
def init_model() -> ChatOpenAI:
    try:
        MODEL_NAME = os.getenv("MODEL_NAME")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        llm = ChatOpenAI(
            model=MODEL_NAME,
            temperature=0.3,
            api_key=OPENAI_API_KEY,
        )
        
        # llm.format = "json"
        print("Model initialized successfully:", llm)
        return llm
    except Exception as e:
        print(f"Model cannot be initialized: {e}")

llm = init_model()
    
# def human_in_the_loop(state: dict):
#     human = interrupt(state["messages"][-1].content)
#     # information = "It is a personal meeting from 1 pm to 2pm and no attendees."
#     state["messages"].append(HumanMessage(human))
#     return state

# Define the agent node
def agent_node(state: dict) -> dict:

    try:
        # Validate the state structure
        # if not isinstance(state, dict) or "context" not in state or "messages" not in state:
        #     raise ValueError("State must be a dictionary with 'context' and 'messages' keys")

        # llm = state["context"]["llm"]
        # tools = state["context"]["tools"]
        # if not llm or not tools:
        #     raise ValueError("LLM or tools missing from context")

        date = datetime.now().strftime("%Y-%m-%d")
        
        prompt = f"""
        You are a helpful assistant that can create, list, update, and delete google calendar events.
        You are in Eastern Standard Time Zone and today is {date}. Assume the user is asking for the same year if not mentioned.
        Extract all the information from the user message and for information that is missing, ask the user for it causing least friction.
        Assume data generously.
        While updating or deleting events, get all the events for the mentioned date from 12am to 11:59pm. Use the id of that particular event to perform the necessary action."""
    
        llm = init_model()

        graph_agent = create_react_agent(llm, tools=tools, state_modifier=prompt)
        result = graph_agent.invoke(state)
        # print("Agent result:", result)  # Debugging
        state["messages"].extend(result["messages"])

        return state
    
    except Exception as e:
        print(f"Error in agent_node: {e}")
        return state

# Print stream function
def print_stream(stream):
    try:
        for s in stream:
            if isinstance(s, dict):
                # Handle "branch" condition
                if "branch" in s:
                    print(f"Branch condition met: {s['branch']}")
                # Handle messages from "agent"
                elif "agent" in s and "messages" in s["agent"]:
                    message = s["agent"]["messages"][-1]
                    if "AIMessage" in str(type(message)):  # Check if it's an AIMessage
                        print(message.content)
                else:
                    print("Other stream output:", s)
            else:
                print("Unexpected stream format:", s)
    except Exception as e:
        print(f"Error in print_stream: {e}")
        
# Main workflow

def get_workflow() -> CompiledStateGraph:
    # User input message
    # user_message = "Can you create an event on 26 January 2025 for a meeting at 110 Stewart Street?"
    # user_message = "Can you list all the events I have on the 26 January 2025?"
    # user_message = "Can you delete all the event on the 27 January 2025?"
    # user_message = "Can you list all the events I have on the 27 January 2025? and then create an event on 27 jan 2025 from 5pm to 6pm for a meeting at 110 stewart street"
    # user_message = "Can you delete the Meeting on 26th Jan 2025?"

    # def route(state: dict):
    #     if "Human" in state["messages"][-1].content:
    #         return "Human_Input"
    #     else:
    #         return END

    # Create the workflow
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    # workflow.add_node("Human_Input", human_in_the_loop)
    workflow.add_edge(START, "agent")
    # workflow.add_edge("Human_Input","agent")
    # workflow.add_conditional_edges("agent", route)
    workflow.add_edge("agent", END)

    memory = MemorySaver()
    # Compile and execute
    graph = workflow.compile(checkpointer=memory)
    return graph


def run_chatbot(graph: CompiledStateGraph, state: MessagesState) -> StateSnapshot:

    config = {"configurable": {"thread_id": "1"}}

    for chunk in graph.stream(state, config=config):
        print(chunk)

    return graph.get_state(config=config)