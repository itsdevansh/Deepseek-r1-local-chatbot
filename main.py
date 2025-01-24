import os
from langchain_ollama.llms import OllamaLLM
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
import io

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME")

model = OllamaLLM(model=MODEL_NAME)

print(model)

st.set_page_config(page_title="Multimodal Chatbot", layout="wide")

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "DeepSeek-r1"

def process_message(message, uploaded_file):
    response = f"Model {st.session_state.selected_model} response to: {message}"
    if uploaded_file:
        response += " (with uploaded media)"
    return response

def main():
    initialize_session_state()
    
    st.title("Multimodal Chatbot")
    
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
    uploaded_file = st.file_uploader("Upload image or file", type=["jpg", "jpeg", "png", "pdf"])
    
    if user_input := st.chat_input("Send a message"):
        # Display user message
        with st.chat_message("user"):
            if uploaded_file:
                image = Image.open(uploaded_file)
                st.image(image)
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_input,
                    "image": uploaded_file
                })
            else:
                st.write(user_input)
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_input
                })
        
        # Generate and display assistant response
        response = process_message(user_input, uploaded_file)
        with st.chat_message("assistant"):
            st.write(response)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response
            })

if __name__ == "__main__":
    main()