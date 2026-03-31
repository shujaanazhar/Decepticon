"""Google Calendar watcher — finds upcoming Google Meet links."""

import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")


def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def get_upcoming_meets(lookahead_minutes=10):
    """Return list of (event_title, meet_url, start_time) for meets starting soon."""
    service = get_calendar_service()
    now = datetime.datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + datetime.timedelta(minutes=lookahead_minutes)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    meets = []
    for event in events_result.get("items", []):
        meet_url = event.get("hangoutLink")
        if not meet_url:
            # also check conferenceData
            conf = event.get("conferenceData", {})
            for ep in conf.get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    meet_url = ep.get("uri")
                    break
        if meet_url:
            start = event["start"].get("dateTime", event["start"].get("date"))
            meets.append({
                "title": event.get("summary", "Untitled Meeting"),
                "url": meet_url,
                "start": start,
                "event_id": event["id"],
            })
    return meets
