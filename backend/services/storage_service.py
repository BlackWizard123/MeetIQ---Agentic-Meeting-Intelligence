import json, os, uuid
from datetime import datetime, date

DATA_DIR     = os.path.join(os.path.dirname(__file__), "../data")
MEETINGS_DIR = os.path.join(DATA_DIR, "meetings")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

def _ensure():
    os.makedirs(MEETINGS_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE,"w") as f: json.dump([],f)

class _Encoder(json.JSONEncoder):
    """Handles date, datetime objects from PostgreSQL."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return str(obj)[:10]
        return super().default(obj)

def _dump(data):
    return json.dumps(data, cls=_Encoder, indent=2)

def save_meeting(memo, tasks, meetings, project_name=None):
    _ensure()
    mid       = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().isoformat()
    record    = {"id":mid,"timestamp":timestamp,
                 "memo":memo,"tasks":tasks,"meetings":meetings,
                 "briefing":None}
    with open(os.path.join(MEETINGS_DIR,f"{mid}.json"),"w") as f:
        f.write(_dump(record))
    history = load_history()
    history.append({"id":mid,"title":memo.get("title","Untitled"),
                    "date":memo.get("date",timestamp[:10]),
                    "attendees":memo.get("attendees",[]),
                    "project": project_name or memo.get("project") or "Unknown Project",
                    "timestamp":timestamp})
    with open(HISTORY_FILE,"w") as f:
        f.write(_dump(history))
    return mid

def load_history():
    _ensure()
    with open(HISTORY_FILE) as f: return json.load(f)

def load_meeting(mid):
    _ensure()
    fp = os.path.join(MEETINGS_DIR,f"{mid}.json")
    if not os.path.exists(fp): raise FileNotFoundError(f"Meeting {mid} not found")
    with open(fp) as f: return json.load(f)

def save_briefing(mid, briefing):
    _ensure()
    fp = os.path.join(MEETINGS_DIR,f"{mid}.json")
    if not os.path.exists(fp): return
    with open(fp) as f: record = json.load(f)
    record["briefing"] = briefing
    with open(fp,"w") as f: f.write(_dump(record))

def load_briefing(mid):
    try:
        return load_meeting(mid).get("briefing")
    except: return None

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