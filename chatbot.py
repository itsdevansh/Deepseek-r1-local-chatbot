import os
from langchain_ollama.llms import OllamaLLM
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
import io

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME")

def init_model(MODEL_NAME: str) -> OllamaLLM: 
    try:
        model = OllamaLLM(model=MODEL_NAME)
        print(model)
    except Exception as e:
        print(f"Model cannot be initialized: {e}")