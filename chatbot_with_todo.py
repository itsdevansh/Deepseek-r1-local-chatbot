# main.py
import os
from datetime import datetime
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot
from langchain_core.messages import AIMessage, HumanMessage
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
# Import the calendar tools from our event_handler module.
from event_handler import create_event, get_events, update_event, delete_event, init_google_calendar

# ------------------------------------------------------------------------------
# 1. Load environment variables and initialize the LLM model
# ------------------------------------------------------------------------------
load_dotenv()
TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def init_model() -> ChatOpenAI:
    try:
        MODEL_NAME = os.getenv("MODEL_NAME")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        llm = ChatOpenAI(
            model=MODEL_NAME,
            temperature=0.3,
            api_key=OPENAI_API_KEY,
        )
        print("Model initialized successfully:", llm)
        return llm
    except Exception as e:
        print(f"Model cannot be initialized: {e}")

llm = init_model()

# ------------------------------------------------------------------------------
# 2. Define the agent node
#
#    If the user's message appears to be a to‑do list (detected via keywords), the prompt instructs
#    the LLM to extract individual tasks, estimate durations, and call the tool "create_event"
#    for each scheduled task. Otherwise, it falls back to normal calendar operations.
# ------------------------------------------------------------------------------
def agent_node(state: dict) -> dict:
    try:
        user_message = state["messages"][-1].content
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Check if the message likely contains a to‑do list.
        if any(keyword in user_message.lower() for keyword in ["todo", "to-do", "task list", "schedule my tasks"]):
            prompt = f"""
You are an intelligent assistant that manages a Google Calendar using API tools.
You can call only one tool at a time, once you create one event you have to call again if you want to create another event.
The user has provided a to-do list. Your task is to:
  1. Parse the following to-do list input and extract each task.
  2. Fetch the events of the day, analyse the free time slots, and schedule the tasks.
  3.. For each task, assign a reasonable duration and schedule it during the day.
  4. For each scheduled task, call the tool "create_event" with these parameters:
     - summary: the task description.
     - location: an empty string if not provided.
     - description: "Scheduled from to-do list".
     - start_time: the scheduled start time in ISO format (YYYY-MM-DDTHH:MM:SS) based on today ({today_str}).
     - end_time: the scheduled end time in ISO format.
     - attendees: an empty list.
Output the tool calls in valid JSON.
User input: "{user_message}"
Today's date is {today_str}.
"""
            graph_agent = create_react_agent(
                llm,
                tools=[create_event, get_events, update_event, delete_event],
                state_modifier=prompt
            )
            result = graph_agent.invoke(state)
            state["messages"].extend(result["messages"])
            return state

        # Fallback: Use the standard prompt for calendar management.
        prompt = f"""
You are a helpful assistant that manages Google Calendar events. Today is {today_str}.
Extract all necessary information from the user message and use appropriate tools (create_event, get_events, update_event, delete_event)
to create, list, update, or delete calendar events. Ask follow-up questions if any required details are missing.
"""
        graph_agent = create_react_agent(
            llm,
            tools=[create_event, get_events, update_event, delete_event],
            state_modifier=prompt
        )
        result = graph_agent.invoke(state)
        state["messages"].extend(result["messages"])
        return state

    except Exception as e:
        print(f"Error in agent_node: {e}")
        return state

# ------------------------------------------------------------------------------
# 3. (Optional) A helper to print streaming output for debugging.
# ------------------------------------------------------------------------------
def print_stream(stream):
    try:
        for s in stream:
            if isinstance(s, dict):
                if "branch" in s:
                    print(f"Branch condition met: {s['branch']}")
                elif "agent" in s and "messages" in s["agent"]:
                    message = s["agent"]["messages"][-1]
                    if "AIMessage" in str(type(message)):
                        print(message.content)
                else:
                    print("Other stream output:", s)
            else:
                print("Unexpected stream format:", s)
    except Exception as e:
        print(f"Error in print_stream: {e}")

# ------------------------------------------------------------------------------
# 4. Build the workflow graph
# ------------------------------------------------------------------------------
def get_workflow() -> CompiledStateGraph:
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)
    return graph

# ------------------------------------------------------------------------------
# 5. Main runner: Initialize Google Calendar and run the agent workflow.
# ------------------------------------------------------------------------------
def run_chatbot(graph: CompiledStateGraph, state: MessagesState, creds) -> StateSnapshot:
    init_google_calendar(creds)
    config = {"configurable": {"thread_id": "1"}}
    for chunk in graph.stream(state, config=config):
        print(chunk)
    return graph.get_state(config=config)

# ------------------------------------------------------------------------------
# 6. For local testing: simulate a to-do list input.
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Replace the below with your actual Google Calendar credentials.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    # creds = {"dummy": "credentials"}
    
    # Example user message containing a to-do list.
    initial_message = HumanMessage(
        content="My to-do list: Buy groceries, Call John, Finish report, Exercise"
    )
    state = MessagesState(messages=[initial_message])
    
    workflow_graph = get_workflow()
    final_state = run_chatbot(workflow_graph, state, creds)
    print("Final state:", final_state)
