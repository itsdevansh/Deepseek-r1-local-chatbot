import os
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from event_handler import create_event, get_events, update_event, delete_event
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables
load_dotenv()

# Initialize the model
def init_model() -> ChatOllama:
    try:
        MODEL_NAME = os.getenv("MODEL_NAME")
        llm = ChatOllama(
            model=MODEL_NAME,
            temperature=0.3,
        )
        # llm.format = "json"
        print("Model initialized successfully:", llm)
        return llm
    except Exception as e:
        print(f"Model cannot be initialized: {e}")

# Define the agent node
def agent_node(state: dict) -> dict:
#     prompt = ChatPromptTemplate.from_messages(
#     [
#         ("system", "You are a helpful assistant. Respond only in Spanish."),
#         ("human", "{input}"),
#         ("placeholder", "{agent_scratchpad}"),
#     ]
# )
    try:
        # Validate the state structure
        if not isinstance(state, dict) or "context" not in state or "messages" not in state:
            raise ValueError("State must be a dictionary with 'context' and 'messages' keys")

        llm = state["context"].get("llm")
        tools = state["context"].get("tools")
        if not llm or not tools:
            raise ValueError("LLM or tools missing from context")
        
        prompt = """
        You can in Los Angeles time zone.
        You are a helpful assistant that can create, list, update, and delete google calendar events.
        Extract all the information from the user message and for information that is missing, ask the user for it causing least friction.
        Assume data generously.
        While updating or deleting events, get all the events for the mentioned date from 12am to 11:59pm. Use the id of that particular event to perform the necessary action."""
        
        memory = MemorySaver()
        graph_agent = create_react_agent(llm, tools=tools, checkpointer=memory, state_modifier=prompt)
        
        result = graph_agent.invoke(state)
        print("Agent result:", result)  # Debugging
        state["messages"].extend(result["messages"])
        return state
    except Exception as e:
        print(f"Error in agent_node: {e}")
        return state

# Print stream function
def print_stream(stream):
    for s in stream:
        print("Stream output:", s)
        if "agent" in s and "messages" in s["agent"]:
            message = s["agent"]["messages"][-1]
            print("Message content:", message)
        else:
            print("No 'messages' key in stream output:", s)

# Main workflow
if __name__ == "__main__":
    llm = init_model()

    # Tools for handling events
    tools = [create_event, get_events, update_event, delete_event]

    # User input message
    # user_message = "Can you create an event on 26 January 2025 from 1 PM to 2 PM for a meeting at 110 Stewart Street?"
    user_message = "Can you list all the events I have on the 26 January 2025?"
    # user_message = "Can you delete all the event on the 27 January 2025?"
    # user_message = "Can you list all the events I have on the 27 January 2025? and then create an event on 27 jan 2025 from 5pm to 6pm for a meeting at 110 stewart street"
    # user_message = "Can you delete the Meeting on 26th Jan 2025?"
    # Initialize workflow state
    initial_state = {
        "messages": [("user", user_message)],
        "context": {
            "llm": llm,
            "tools": tools,
        },
    }

    # Create the workflow
    workflow = StateGraph(dict)
    workflow.add_node("agent", agent_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)

    # Compile and execute
    graph = workflow.compile()
    events = graph.stream(initial_state, config={"configurable": {"thread_id": "1"}})

    # Print results
    print_stream(events)