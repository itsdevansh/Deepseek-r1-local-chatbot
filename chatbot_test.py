import os
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END, MessagesState
from event_handler import create_event, get_events, update_event, delete_event
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import interrupt, Command
from langchain_core.messages import AIMessage, HumanMessage
# Load environment variables
load_dotenv()

tools = [create_event, get_events, update_event, delete_event]

# Initialize the model
def init_model() -> ChatOpenAI:
    try:
        MODEL_NAME = os.getenv("MODEL_NAME")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=OPENAI_API_KEY,
        )
        
        # llm.format = "json"
        print("Model initialized successfully:", llm)
        return llm
    except Exception as e:
        print(f"Model cannot be initialized: {e}")

# def parse_next_node(aimessage:str):
#     if "Human" in aimessage:
#         return "Human_Input"
#     else:
#         return "End"
    
def human_in_the_loop(state: dict):
    human = interrupt(state["messages"][-1].content)
    # information = "It is a personal meeting from 1 pm to 2pm and no attendees."
    state["messages"].append(HumanMessage(human))
    return state

# Define the agent node
def agent_node(state: dict):

    try:
        # Validate the state structure
        # if not isinstance(state, dict) or "context" not in state or "messages" not in state:
        #     raise ValueError("State must be a dictionary with 'context' and 'messages' keys")

        # llm = state["context"]["llm"]
        # tools = state["context"]["tools"]
        # if not llm or not tools:
        #     raise ValueError("LLM or tools missing from context")
        
        prompt = """
        You are a helpful assistant that can create, list, update, and delete google calendar events.
        You are in Eastern Standard Time Zone.
        Extract all the information from the user message and for information that is missing, ask the user for it causing least friction. Whenever you need data from the user, always ask the question starting with the phrase 'Human'."
        Assume data generously
        While updating or deleting events, get all the events for the mentioned date from 12am to 11:59pm. Use the id of that particular event to perform the necessary action."""
    
        graph_agent = create_react_agent(llm, tools=tools, state_modifier=prompt)
        result = graph_agent.invoke(state)
        print("Agent result:", result)  # Debugging
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
if __name__ == "__main__":
    llm = init_model()

    # Tools for handling events
    tools = [create_event, get_events, update_event, delete_event]

    # User input message
    user_message = "Can you create an event on 26 January 2025 for a meeting at 110 Stewart Street?"
    # user_message = "Can you list all the events I have on the 26 January 2025?"
    # user_message = "Can you delete all the event on the 27 January 2025?"
    # user_message = "Can you list all the events I have on the 27 January 2025? and then create an event on 27 jan 2025 from 5pm to 6pm for a meeting at 110 stewart street"
    # user_message = "Can you delete the Meeting on 26th Jan 2025?"
    # Initialize workflow state
    next_node = "agent"
    initial_state = {"context":{"llm": llm, "tools": tools}, "messages":[HumanMessage(user_message)], "next": next_node}
    initial_state = {
        "messages": [("user", user_message)],
    }

    def route(state: dict):
        if "Human" in state["messages"][-1].content:
            return "Human_Input"
        else:
            return END

    # Create the workflow
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("Human_Input", human_in_the_loop)
    workflow.add_edge(START, "agent")
    workflow.add_edge("Human_Input","agent")
    workflow.add_conditional_edges("agent", route)
    # workflow.add_edge("agent", END)

    memory = MemorySaver()
    # Compile and execute
    graph = workflow.compile(checkpointer=memory)

    # events = graph.stream(initial_state, config={"configurable": {"thread_id": "1"}})

    # Print results
    # print_stream(events)

    config = {"configurable": {"thread_id": "1"}}

    # Using stream() to directly surface the `__interrupt__` information.
    for chunk in graph.stream(initial_state, config=config):
        print(chunk)
    
    # Resume using Command
    while "__interrupt__" in chunk:
        for chunk in graph.stream(Command(resume=input("Enter additional info: ")), config=config):
            print(chunk)