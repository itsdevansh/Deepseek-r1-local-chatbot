import streamlit as st
import os
from PIL import Image
import io
from chatbot import get_workflow, run_chatbot
from langchain_core.messages import AIMessage, HumanMessage
import pickle
import json
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

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
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

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

def authenticate():
    creds = None

    if os.path.exists(TOKEN_FILE):
      creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
      else:
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_FILE, SCOPES
        )
        creds = flow.run_local_server(port=0)
      # Save the credentials for the next run
      with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

    # If no valid credentials, authenticate user
    # if not creds or not creds.valid:
    #     if creds and creds.expired and creds.refresh_token:
    #         creds.refresh(Request())
    #     else:
    #         flow = Flow.from_client_secrets_file(
    #             CLIENT_SECRET_FILE, SCOPES, redirect_uri="http://localhost:8501/"
    #         )
    #         auth_url, _ = flow.authorization_url(prompt="consent")
    #         st.write(f"[Login with Google]({auth_url})")

    #         auth_code = st.text_input("Enter Authorization Code:")
    #         if st.button("Authenticate"):
    #             if auth_code:
    #                 flow.fetch_token(code=auth_code)
    #                 creds = flow.credentials
    #                 with open(TOKEN_FILE, "wb") as token:
    #                     pickle.dump(creds, token)
    #                 st.success("Authentication successful! You can now access Google Calendar.")
    #             else:
    #                 st.error("Please enter the authorization code.")

    return creds

def main():

    initialize_session_state()
    
    st.title("Google Event Manager")

    
    # Sidebar for model selection
    with st.sidebar:
        st.session_state.selected_model = st.selectbox(
            "Choose Model",
            ["Google Calendar Agent"],
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
    if st.button("Authenticate with Google"):
        creds = authenticate()
        if "auth_url" in st.session_state:
            st.write(f"[Login with Google]({st.session_state.auth_url})")
    
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