import os, json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE    = os.path.join(os.path.dirname(__file__), "../token.json")
MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "")
MANAGER_NAME  = os.getenv("MANAGER_NAME", "hariharan-projectmanager")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

def _creds():
    with open(TOKEN_FILE) as f:
        return Credentials.from_authorized_user_info(json.load(f), SCOPES)

def _calendar(): return build("calendar", "v3", credentials=_creds())
def _tasks():    return build("tasks",    "v1", credentials=_creds())

def _parse_date(date_str: str) -> str:
    """Simple date-only parser for tasks. Returns YYYY-MM-DD."""
    if not date_str or date_str.strip().upper() == "TBD":
        from datetime import timedelta
        return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    s = date_str.strip()
    # Handle datetime-local format — take date part only
    if "T" in s:
        s = s.split("T")[0]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        from datetime import timedelta
        return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

def _parse_datetime(date_str: str) -> datetime:
    """
    Parse date or datetime string into a datetime object (IST).
    Accepts: YYYY-MM-DDTHH:MM  or  YYYY-MM-DD
    Falls back to 7 days from now at 10:00 AM if invalid/TBD.
    """
    fallback = datetime.now() + timedelta(days=7)
    fallback = fallback.replace(hour=10, minute=0, second=0, microsecond=0)

    if not date_str or date_str.strip().upper() == "TBD":
        return fallback
    s = date_str.strip()
    # datetime-local format: 2025-04-10T14:30
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M")
    except ValueError:
        pass
    # date-only format: 2025-04-10
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(hour=10, minute=0)
    except ValueError:
        return fallback


def create_calendar_event(meeting: dict) -> str:
    """
    Creates a Google Calendar event for a suggested meeting.
    Always uses manager email as the organizer/attendee.
    Recipients are listed in the description (no dummy emails needed).
    Returns the created event ID.
    """
    svc      = _calendar()
    start_dt = _parse_datetime(meeting.get("suggested_date", "TBD"))
    duration = int(meeting.get("duration_mins", 30))
    end_dt   = start_dt + timedelta(minutes=duration)

    recipients     = meeting.get("recipients", [])
    recipient_text = ", ".join(recipients) if recipients else "Team"

    # Only add attendees with valid emails — always just the manager for real invites
    attendees = []
    if MANAGER_EMAIL and "@" in MANAGER_EMAIL:
        attendees.append({"email": MANAGER_EMAIL})

    event = {
        "summary": meeting.get("title", "Follow-up Meeting"),
        "description": (
            f"Purpose: {meeting.get('purpose', '')}\n\n"
            f"Agenda:\n{meeting.get('agenda', '')}\n\n"
            f"Intended participants: {recipient_text}\n\n"
            "📅 Scheduled via MeetIQ — Meeting Intelligence"
        ),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Kolkata"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 15}],
        },
    }

    # Only include attendees field if we have valid emails
    if attendees:
        event["attendees"] = attendees

    created = svc.events().insert(calendarId="primary", body=event).execute()
    return created.get("id")


def create_task(task: dict) -> str:
    """
    Creates a Google Task under the 'MeetIQ Tasks' list.
    Task title includes the assignee name since we only have the manager's account.
    Returns the created task ID.
    """
    svc          = _tasks()
    task_list_id = _get_or_create_task_list(svc, "MeetIQ Tasks")

    date_str = _parse_date(task.get("due_date", "TBD"))
    due_dt   = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=9, minute=0)

    assignee = task.get("assignee", "Unassigned")
    priority = task.get("priority", "Medium")
    notes    = task.get("notes", "")
    checker  = task.get("checker", MANAGER_NAME)

    body = {
        "title": f"[{assignee}] {task.get('title', 'Task')}",
        "notes": (
            f"Assignee: {assignee}\n"
            f"Priority: {priority}\n"
            f"Checker: {checker}\n"
            f"Due: {date_str}\n"
            f"Notes: {notes}\n\n"
            "Created via MeetIQ"
        ),
        "due": due_dt.isoformat() + "Z",
    }

    created = svc.tasks().insert(tasklist=task_list_id, body=body).execute()
    return created.get("id")


def _get_or_create_task_list(svc, name: str) -> str:
    result = svc.tasklists().list().execute()
    for tl in result.get("items", []):
        if tl.get("title") == name:
            return tl["id"]
    new_list = svc.tasklists().insert(body={"title": name}).execute()
    return new_list["id"]