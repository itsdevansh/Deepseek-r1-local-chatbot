import streamlit as st
from PIL import Image
import io
from chatbot import get_workflow, run_chatbot
from langchain_core.messages import AIMessage, HumanMessage

st.set_page_config(page_title="Google Event Manager", layout="wide")

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "Google Calendar Agent"
    if "graph" not in st.session_state:
        st.session_state.graph = get_workflow() 
    if "config" not in st.session_state:
        st.session_state.config = {"configurable": {"thread_id": "1"}}
    if "state" not in st.session_state:
        st.session_state.state = st.session_state.graph.get_state(config=st.session_state.config)

def process_message(message):
    if st.session_state.state.values == {}:
        st.session_state.state.values["messages"] = [HumanMessage(message)]
    else:
        st.session_state.state.values["messages"].append(HumanMessage(message))
    updated_state = run_chatbot(st.session_state.graph, st.session_state.state.values)
    st.session_state.state.values['messages'].append(updated_state.values["messages"][-1])
    response = st.session_state.state.values["messages"][-1].content
    response = f"Model {st.session_state.selected_model} response to: {response}"
    return response

def main():

    initialize_session_state()
    
    st.title("Google Event Manager")
    
    # Sidebar for model selection
    with st.sidebar:
        st.session_state.selected_model = st.selectbox(
            "Choose Model",
            ["DeepSeek-r1"],
            index=0
        )
    
    # Chat interface
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message.get("image"):
                    st.image(message["image"])
                st.write(message["content"])
    
    # Input area
    # uploaded_file = st.file_uploader("Upload image or file", type=["jpg", "jpeg", "png", "pdf"])
    
    if user_input := st.chat_input("Send a message"):
        # Display user message
        with st.chat_message("user"):
            st.write(f"You: {user_input}")
            st.session_state.messages.append({
                "role": "user",
                "content": user_input
            })
    
        # Generate and display assistant response
        response = process_message(user_input)
        with st.chat_message("assistant"):
            st.write(response)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response
            })

if __name__ == "__main__":
    main()