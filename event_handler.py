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
    summary: str, 
    location: str,
    description: str,
    start_time: str,
    end_time: str,
    attendees: List[str],
) -> str | None:
    """Create a Google Calendar event.

    Args:
        summary (str): The summary of the event.
        location (str): The location of the event.
        description (str): The description of the event.
        start_time (str): The start time of the event.
        end_time (str): The end time of the event.
        attendees (List[str]): The list of attendees' emails.

    Returns:
        str: The link to the created event.
    """
    try:
        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": summary,
            "location": location,
            "description": description,
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


@tool
def get_events(startDateTime: str, endDateTime: str) -> dict:
  """Get Google Calendar events.
  
  Args:
    startDateTime (str): The start time of the event.
    endDateTime (str): The end time of the event.
  
  Returns:
    dict: The Google Calendar events.
  """
  try:
      service = build("calendar", "v3", credentials=creds)
      events = service.events().list(calendarId='primary', timeMin = startDateTime, timeMax = endDateTime).execute()
      return events
  except HttpError as error:
      print(f"An error occurred: {error}")
      return {"error": error}
  
@tool
def update_event(
    eventId: str, 
    summary: str, 
    location: str,
    description: str,
    start_time: str,
    end_time: str,
    attendees: List[str],
) -> str:
  """Update a Google Calendar event.
  
  Args:
    eventId (str): The ID of the event to update.
    summary (str): The summary of the event.
    location (str): The location of the event.
    description (str): The description of the event.
    start_time (str): The start time of the event.
    end_time (str): The end time of the event.
    attendees (List[str]): The list of attendees' emails.
  
  Returns:
    str: The link to the updated event.
  """
  try:
      service = build("calendar", "v3", credentials=creds)
      event = service.events().get(calendarId='primary', eventId=eventId).execute()
      event['summary'] = summary
      event['location'] = location
      event['description'] = description
      event['start'] = {"dateTime": start_time, "timeZone": "America/Los_Angeles"}
      event['end'] = {"dateTime": end_time, "timeZone": "America/Los_Angeles"}
      event['attendees'] = [{"email": attendee} for attendee in attendees]
      updated_event = service.events().update(calendarId='primary', eventId=eventId, body=event).execute()
      print('Event updated: %s' % (updated_event.get('htmlLink')))
      return updated_event.get('htmlLink')
  except HttpError as error:
      print(f"An error occurred: {error}")
      return error
  
@tool
def delete_event(eventId: str) -> str:
  """
   Delete a Google Calendar event.
   
   Args:
       eventId (str): The ID of the event to delete.
       
    Returns:
        str: The link to the deleted event.
  """
  try:
    service = build("calendar", "v3", credentials=creds)
    event = service.events().get(calendarId='primary', eventId=eventId).execute()
    service.events().delete(calendarId='primary', eventId=eventId).execute()
    print('Event deleted: %s' % (event.get('htmlLink')))
    return event.get('htmlLink')
  except HttpError as error:
    print(f"An error occurred: {error}")
    return error
