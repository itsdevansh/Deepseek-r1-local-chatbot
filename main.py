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

# Configure page settings with dark theme support
st.set_page_config(
    page_title="Calendar Assistant",
    page_icon="📅",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Modern UI styling with better contrast
st.markdown("""
    <style>
    /* Header text fix */
    .stApp header {
        background-color: transparent !important;
    }
    
    /* Calendar Assistant title */
    [data-testid="stHeader"] {
        color: #ffffff !important;
    }
    
    h1 {
        color: #ffffff !important;
        font-weight: 500;
    }
    
    /* Sidebar text fixes */
    [data-testid="stSidebar"] {
        color: #ffffff;
    }
    
    [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] .stSelectbox label {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] .stSelectbox span {
        color: #ffffff !important;
    }
    
    /* Warning/status messages in sidebar */
    [data-testid="stSidebar"] .stAlert {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
    }
    
    .st-warning {
        color: #ffffff !important;
    }
    
    .st-success {
        color: #ffffff !important;
    }
    </style>
""", unsafe_allow_html=True)

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # if "selected_model" not in st.session_state:
    #     st.session_state.selected_model = "Google Calendar Agent"
    if "graph" not in st.session_state:
        st.session_state.graph = get_workflow() 
    if "config" not in st.session_state:
        st.session_state.config = {"configurable": {"thread_id": "1"}}
    if "state" not in st.session_state:
        st.session_state.state = st.session_state.graph.get_state(config=st.session_state.config)
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

def process_message(message, creds):
    if st.session_state.state.values == {}:
        st.session_state.state.values["messages"] = [HumanMessage(message)]
    else:
        st.session_state.state.values["messages"].append(HumanMessage(message))
    updated_state = run_chatbot(st.session_state.graph, st.session_state.state.values, creds)
    st.session_state.state.values['messages'].append(updated_state.values["messages"][-1])
    response = st.session_state.state.values["messages"][-1].content
    return response

def authenticate():
    creds = None
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
    st.session_state.authenticated = True
    st.session_state.creds = creds
    

def main():
    initialize_session_state()
    
    # Main container
    st.title("📅 Calendar Assistant")
    
    # Sidebar with improved styling
    # with st.sidebar:
    #     st.markdown("### Assistant Settings")
    #     st.selectbox(
    #         "Choose Model",
    #         ["Google Calendar Agent"],
    #         index=0,
    #         key="selected_model"
    #     )
    
    # Main chat interface
    if not st.session_state.authenticated:
        st.markdown("""
            <div class="welcome-container">
                <h2>👋 Welcome to Calendar Assistant!</h2>
                <p style="color: #666666; margin: 1rem 0;">Connect your Google Calendar to get started</p>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔗 Connect Calendar", use_container_width=True):
                authenticate()
    
    # Chat messages
    for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message.get("image"):
                    st.image(message["image"])
                st.markdown(message["content"])
    
    # Chat input
    if st.session_state.authenticated:
        st.success("✓ Connected to Calendar")
        
        with st.container():
            col1, col2 = st.columns([1, 8])
            with col1:
                mic_clicked = st.button("🎤", use_container_width=True)
            with col2:
                user_input = st.chat_input("Ask about your calendar...")
        
        if user_input:
            with st.chat_message("user"):
                st.markdown(user_input)
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_input
                })

            with st.chat_message("assistant"):
                response = process_message(user_input, st.session_state.creds)
                st.markdown(response)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })
            
          

if __name__ == "__main__":
    main()