import os
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
from langchain_core.prompts import ChatPromptTemplate
import io
import json


from event_handler import create_event, get_events

load_dotenv()


def init_model() -> ChatOllama:
    try:
        MODEL_NAME = os.getenv("MODEL_NAME")
        llm = ChatOllama(
            model=MODEL_NAME,
            temperature=0.3,
            # other params...
        )
        llm.format = "json"
        print(llm)
        return llm
    except Exception as e:
        print(f"Model cannot be initialized: {e}")


def llm_create_event(llm: ChatOllama, user_input: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an agent that creates google calendar events. Your output should be in the following format:{{
      "summary": " ",
      "location": " ",
      "description": " ",
      "start": {{
        "dateTime": " ",
        "timeZone": "America/Los_Angeles",
      }},
      "end": {{
        "dateTime": " ",
        "timeZone": "America/Los_Angeles",
      }},
      "recurrence": [
        "RRULE:FREQ=DAILY;COUNT=1"
      ],
      "attendees": [
        {{"email": " "}},
      ],
      "reminders": {{
        "useDefault": False,
        "overrides": [
          {{"method": "email", "minutes": 24 * 60}},
          {{"method": "popup", "minutes": 10}},
        ],
      }},
    }}
    From the user input, see if you can extract relevant information and for information that is missing, you can ask the user questions that you think are necessary to create the event. Remember to cause least friction to the user. Only ask information with technical details, any details that can be inferred from the user input, should be inferred geneously.
    """,
            ),
            ("human", "{input}"),
        ]
    )

    chain = prompt | llm

    a = chain.invoke(
        {
            "input": user_input
        }
    )
    response = a.content
    return response


if __name__ == "__main__":
    # events = get_events({})
    # for event in events['items']:
    #     print(event['summary'])
    llm = init_model()
    user_input = "Can you create an event on 5th February 2025 11:00 AM - 2:00 PM to attend a conference at Unviersity of Ottawa with no attendees?"
    data = llm_create_event(llm, user_input)
    print(json.loads(data))
    link = create_event(json.loads(data))
    print(link)