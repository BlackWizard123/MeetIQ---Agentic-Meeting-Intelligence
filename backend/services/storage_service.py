import json, uuid, os
from datetime import datetime, date

from google.cloud import storage as gcs
from google.oauth2.credentials import Credentials

BUCKET_NAME = os.getenv("GCS_BUCKET", "meetiq-data")
MEETINGS_PREFIX = "meetings/"
HISTORY_KEY     = "history.json"

_client = None

def _gcs():
    global _client
    if _client is None:
        _client = gcs.Client()
    return _client

def _bucket():
    return _gcs().bucket(BUCKET_NAME)


class _Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return str(obj)[:10]
        return super().default(obj)

def _dump(data):
    return json.dumps(data, cls=_Encoder, indent=2)


def _read(key: str):
    blob = _bucket().blob(key)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())

def _write(key: str, data):
    blob = _bucket().blob(key)
    blob.upload_from_string(_dump(data), content_type="application/json")


def save_meeting(memo, tasks, meetings, project_name=None):
    mid       = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().isoformat()
    record    = {
        "id": mid, "timestamp": timestamp,
        "memo": memo, "tasks": tasks, "meetings": meetings,
        "briefing": None,
    }
    _write(f"{MEETINGS_PREFIX}{mid}.json", record)

    history = load_history()
    history.append({
        "id":        mid,
        "title":     memo.get("title", "Untitled"),
        "date":      memo.get("date", timestamp[:10]),
        "attendees": memo.get("attendees", []),
        "project":   project_name or memo.get("project") or "Unknown Project",
        "timestamp": timestamp,
    })
    _write(HISTORY_KEY, history)
    return mid


def load_history():
    data = _read(HISTORY_KEY)
    return data if data is not None else []


def load_meeting(mid):
    data = _read(f"{MEETINGS_PREFIX}{mid}.json")
    if data is None:
        raise FileNotFoundError(f"Meeting {mid} not found")
    return data


def save_briefing(mid, briefing):
    data = _read(f"{MEETINGS_PREFIX}{mid}.json")
    if data is None: return
    data["briefing"] = briefing
    _write(f"{MEETINGS_PREFIX}{mid}.json", data)


def load_briefing(mid):
    try:
        return load_meeting(mid).get("briefing")
    except:
        return None

# ---------------------------------------------------

# import json
# import os
# import uuid
# from datetime import datetime

# DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
# MEETINGS_DIR = os.path.join(DATA_DIR, "meetings")
# HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


# def _ensure_dirs():
#     os.makedirs(MEETINGS_DIR, exist_ok=True)
#     if not os.path.exists(HISTORY_FILE):
#         with open(HISTORY_FILE, "w") as f:
#             json.dump([], f)


# def save_meeting(memo: dict, tasks: list, meetings: list) -> str:
#     """
#     Saves a finalized meeting to disk. Returns the generated meeting ID.
#     """
#     _ensure_dirs()
#     meeting_id = str(uuid.uuid4())[:8]
#     timestamp = datetime.utcnow().isoformat()

#     record = {
#         "id": meeting_id,
#         "timestamp": timestamp,
#         "memo": memo,
#         "tasks": tasks,
#         "meetings": meetings,
#     }

#     # Save full record
#     filepath = os.path.join(MEETINGS_DIR, f"{meeting_id}.json")
#     with open(filepath, "w") as f:
#         json.dump(record, f, indent=2)

#     # Update history index (sidebar list)
#     history = load_history()
#     history.append({
#         "id": meeting_id,
#         "title": memo.get("title", "Untitled Meeting"),
#         "date": memo.get("date", timestamp[:10]),
#         "attendees": memo.get("attendees", []),
#         "timestamp": timestamp,
#     })
#     with open(HISTORY_FILE, "w") as f:
#         json.dump(history, f, indent=2)

#     return meeting_id


# def load_history() -> list:
#     """Returns the list of all past meetings (summary only, for sidebar)."""
#     _ensure_dirs()
#     with open(HISTORY_FILE, "r") as f:
#         return json.load(f)


# def load_meeting(meeting_id: str) -> dict:
#     """Returns the full record for a single past meeting."""
#     _ensure_dirs()
#     filepath = os.path.join(MEETINGS_DIR, f"{meeting_id}.json")
#     if not os.path.exists(filepath):
#         raise FileNotFoundError(f"Meeting {meeting_id} not found")
#     with open(filepath, "r") as f:
#         return json.load(f)