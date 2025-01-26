import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List
from langchain_core.tools import tool

SCOPES = ["https://www.googleapis.com/auth/calendar"]


"""Shows basic usage of the Google Calendar API.
Prints the start and name of the next 10 events on the user's calendar.
"""
creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists("token.json"):
  creds = Credentials.from_authorized_user_file("token.json", SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
  if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
  else:
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", SCOPES
    )
    creds = flow.run_local_server(port=0)
  # Save the credentials for the next run
  with open("token.json", "w") as token:
    token.write(creds.to_json())

@tool
def create_event(
    start_time: str,
    end_time: str,
    location: str,
    attendees: List[str],
) -> dict:
    """Create a Google Calendar event.

    Args:
        start_time (str): The start time of the event.
        end_time (str): The end time of the event.
        location (str): The location of the event.
        attendees (List[str]): The list of attendees' emails.

    Returns:
        dict: The Google Calendar event.
    """
    try:
        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": "Event",
            "location": location,
            "description": "Event",
            "start": {"dateTime": start_time, "timeZone": "America/Los_Angeles"},
            "end": {"dateTime": end_time, "timeZone": "America/Los_Angeles"},
            "recurrence": ["RRULE:FREQ=DAILY;COUNT=1"],
            "attendees": [{"email": attendee} for attendee in attendees],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "popup", "minutes": 10},
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        print('Event created: %s' % (event.get('htmlLink')))
        return event.get('htmlLink')
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None



def get_events(date: dict):
    try:
        service = build("calendar", "v3", credentials=creds)
        events = service.events().list(calendarId='primary', timeMin = "2025-01-27T00:00:00-00:00", timeMax = "2025-01-27T23:59:59-00:00").execute()
        return events
    except HttpError as error:
        print(f"An error occurred: {error}")
  
