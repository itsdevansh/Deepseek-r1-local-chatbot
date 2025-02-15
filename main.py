import streamlit as st
import os
from PIL import Image
import io
from chatbot_with_todo import get_workflow, run_chatbot
from langchain_core.messages import AIMessage, HumanMessage
import pickle
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from streamlit_extras.stylable_container import stylable_container
import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import tempfile
from openai import OpenAI
import queue

TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class AudioRecorder:
    def __init__(self):
        self.fs = 44100  # Sample rate
        self.recording = False
        self.audio_queue = queue.Queue()
        
    def callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_queue.put(indata.copy())
    
    def start_recording(self):
        self.recording = True
        self.audio_data = []
        self.stream = sd.InputStream(
            samplerate=self.fs,
            channels=1,
            callback=self.callback
        )
        self.stream.start()
    
    def stop_recording(self):
        self.recording = False
        self.stream.stop()
        self.stream.close()
        
        # Combine all audio data
        while not self.audio_queue.empty():
            self.audio_data.append(self.audio_queue.get())
        
        if not self.audio_data:
            return None
            
        audio_data = np.concatenate(self.audio_data, axis=0)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        wav.write(temp_file.name, self.fs, audio_data)
        return temp_file.name

def transcribe_audio(audio_file_path):
    client = OpenAI()
    with open(audio_file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcription.text

def speak_text(text):
    client = OpenAI()
    speech_file_path = "speech.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
    )
    response = response.read()
    st.audio(response, format="audio/wav", autoplay=True)

    # audio_file = open(speech_file_path, "rb")
    # audio_bytes = audio_file.read()
    # return audio_bytes


# Configure page settings with dark theme support
st.set_page_config(
    page_title="Calendar Assistant",
    page_icon="📅",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Add CSS for the audio recording button
st.markdown("""
    <style>
    /* Existing styles */
    .stApp header {
        background-color: transparent !important;
    }
    
    [data-testid="stHeader"] {
        color: #ffffff !important;
    }
    
    h1 {
        color: #ffffff !important;
        font-weight: 500;
    }
    
    /* Audio recording styles */
    .record-button {
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        background-color: #ff4b4b;
        color: white;
        border: none;
        cursor: pointer;
        transition: background-color 0.3s;
    }
    
    .record-button.recording {
        background-color: #ff3333;
        animation: pulse 1.5s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
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
    if "recording" not in st.session_state:
        st.session_state.recording = False
    if "transcribed_text" not in st.session_state:
        st.session_state.transcribed_text = None
    if "recording_icon" not in st.session_state:
        st.session_state.recording_icon = ":material/mic:"

class AudioRecorder:
    def __init__(self):
        self.fs = 44100  # Sample rate
        self.recording = False
        self.audio_queue = queue.Queue()
        
    def callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_queue.put(indata.copy())
    
    def start_recording(self):
        self.recording = True
        self.audio_data = []
        self.stream = sd.InputStream(
            samplerate=self.fs,
            channels=1,
            callback=self.callback
        )
        self.stream.start()
    
    def stop_recording(self):
        self.recording = False
        self.stream.stop()
        self.stream.close()
        
        # Combine all audio data
        while not self.audio_queue.empty():
            self.audio_data.append(self.audio_queue.get())
        
        if not self.audio_data:
            return None
            
        audio_data = np.concatenate(self.audio_data, axis=0)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        wav.write(temp_file.name, self.fs, audio_data)
        return temp_file.name

def transcribe_audio(audio_file_path):
    client = OpenAI()
    with open(audio_file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcription.text

def process_message(message, creds) -> str:
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
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRET_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")
                return
    
    st.session_state.authenticated = True
    st.session_state.creds = creds

def main():
    try:
        initialize_session_state()
    except Exception as e:
        st.error(f"Initialization error: {str(e)}")
        return
    
    st.title("📅 Calendar Assistant")
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
    
    # Chat input with audio recording
    if st.session_state.authenticated:
        with stylable_container(
        key="bottom_content",
        css_styles="""
            {
                position: fixed;
                bottom: 0;
                opacity: 1;
                padding: 30px;
                background-color: #0e1117;
            }
            """,
        ):
            col1, col2 = st.columns([1, 10])
            with col1:
                if st.button(icon=st.session_state.recording_icon, label="", key="mic", type='primary'):
                    if not st.session_state.recording:
                # Start recording
                        st.session_state.recording = True
                        st.session_state.recording_icon = ":material/stop_circle:"
                        st.session_state.audio_recorder = AudioRecorder()
                        st.session_state.audio_recorder.start_recording()
                        st.rerun()
                    else:
                        # Stop recording
                        audio_file = st.session_state.audio_recorder.stop_recording()
                        st.session_state.recording = False
                        st.session_state.recording_icon = ":material/mic:"
                        if audio_file:
                            with st.spinner(""):
                                transcription = transcribe_audio(audio_file)
                                print(transcription)
                                st.session_state.transcribed_text = transcription
                                os.unlink(audio_file)  # Clean up temporary file
                            st.rerun()
            with col2:
                user_input = st.chat_input("Ask about your calendar...")       
            
        
        if user_input or st.session_state.transcribed_text:
            if user_input:
                text = user_input
                audio = False
            if st.session_state.transcribed_text:
                text = st.session_state.transcribed_text
                st.session_state.transcribed_text = None
                audio = True
            with st.chat_message("user"):
                st.markdown(text)
                st.session_state.messages.append({
                    "role": "user",
                    "content": text
                })

            with st.chat_message("assistant"):
                response = json.loads(process_message(text, st.session_state.creds))['response_for_user']
                if audio:
                    speak_text(response)
                st.markdown(response)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
            })

if __name__ == "__main__":
    main()