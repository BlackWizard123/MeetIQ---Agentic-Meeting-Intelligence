import os
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Path to your hardcoded token (generated once via OAuth flow)
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "../token.json")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Hardcoded manager email — update this to your Google account
MANAGER_EMAIL = "your_manager_email@gmail.com"


def _get_credentials() -> Credentials:
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(
            "token.json not found. Run generate_token.py once to create it."
        )
    with open(TOKEN_FILE, "r") as f:
        token_data = json.load(f)
    return Credentials.from_authorized_user_info(token_data, SCOPES)


def _get_calendar_service():
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


def _get_tasks_service():
    creds = _get_credentials()
    return build("tasks", "v1", credentials=creds)


def _parse_date(date_str: str) -> str:
    """
    Converts 'YYYY-MM-DD' or 'TBD' to a usable date string.
    Falls back to 7 days from now if TBD.
    """
    if date_str == "TBD" or not date_str:
        return (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
    return date_str


def create_calendar_event(meeting: dict) -> str:
    """
    Creates a Google Calendar event for a suggested meeting.
    Returns the created event ID.
    """
    service = _get_calendar_service()
    date_str = _parse_date(meeting.get("suggested_date", "TBD"))
    duration = meeting.get("duration_mins", 30)

    # Default to 10:00 AM on the suggested date
    start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0)
    end_dt = start_dt + timedelta(minutes=duration)

    # Build attendees list — all recipients + manager
    recipients = meeting.get("recipients", [])
    attendees = [{"email": MANAGER_EMAIL}]
    # Note: for the hackathon, we only have the manager's account
    # so recipients are mentioned in the description instead
    recipient_names = ", ".join(recipients) if recipients else "Team"

    event = {
        "summary": meeting.get("title", "Follow-up Meeting"),
        "description": (
            f"Purpose: {meeting.get('purpose', '')}\n\n"
            f"Agenda: {meeting.get('agenda', '')}\n\n"
            f"Intended participants: {recipient_names}\n\n"
            "Scheduled via Meeting Intelligence"
        ),
        "start": {"dateTime": start_dt.isoformat() + "Z", "timeZone": "UTC"},
        "end":   {"dateTime": end_dt.isoformat() + "Z",   "timeZone": "UTC"},
        "attendees": attendees,
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 15}],
        },
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    return created.get("id")


def create_task(task: dict) -> str:
    """
    Creates a Google Task for a team member's action item.
    Since we only have the manager's account, the task title mentions the assignee.
    Returns the created task ID.
    """
    service = _get_tasks_service()

    # Get or create the "Meeting Intelligence" task list
    task_list_id = _get_or_create_task_list(service, "Meeting Intelligence")

    due_date_str = _parse_date(task.get("due_date", "TBD"))
    due_dt = datetime.strptime(due_date_str, "%Y-%m-%d").replace(hour=9, minute=0)

    assignee = task.get("assignee", "Unassigned")
    priority = task.get("priority", "Medium")
    notes = task.get("notes", "")

    task_body = {
        "title": f"[{assignee}] {task.get('title', 'Task')}",
        "notes": (
            f"Assignee: {assignee}\n"
            f"Priority: {priority}\n"
            f"Notes: {notes}\n\n"
            "Created via Meeting Intelligence"
        ),
        "due": due_dt.isoformat() + "Z",
    }

    created = service.tasks().insert(tasklist=task_list_id, body=task_body).execute()
    return created.get("id")


def _get_or_create_task_list(service, list_name: str) -> str:
    """
    Returns the ID of a task list by name, creating it if it doesn't exist.
    """
    result = service.tasklists().list().execute()
    for tl in result.get("items", []):
        if tl.get("title") == list_name:
            return tl["id"]

    # Create new task list
    new_list = service.tasklists().insert(body={"title": list_name}).execute()
    return new_list["id"]