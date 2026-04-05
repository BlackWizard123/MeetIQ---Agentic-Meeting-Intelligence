import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

from agents.memo_agent import run_memo_agent
from agents.task_agent import run_task_agent
from agents.meeting_agent import run_meeting_agent
from agents.thread_agent import run_thread_agent
from services.storage_service import save_meeting, load_history, load_meeting
from services.calendar_service import create_calendar_event, create_task
from services.sheets_service import update_sheet

app = FastAPI(title="Meeting Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic models ────────────────────────────────────────────────────────

class Task(BaseModel):
    id: str
    title: str
    assignee: str
    due_date: str
    priority: str
    notes: Optional[str] = ""

class Meeting(BaseModel):
    id: str
    title: str
    purpose: str
    suggested_date: str
    duration_mins: int
    recipients: List[str]
    agenda: str

class Memo(BaseModel):
    title: str
    date: str
    attendees: List[str]
    summary: str
    decisions: List[str]
    blockers: List[str]
    next_steps: List[str]

class FinalizeRequest(BaseModel):
    memo: Memo
    tasks: List[Task]
    meetings: List[Meeting]

class ScheduleRequest(BaseModel):
    meeting_id: str
    tasks: List[Task]
    meetings: List[Meeting]


# ── API Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/process-transcript")
async def process_transcript(file: UploadFile = File(...)):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")

    content = await file.read()
    transcript = content.decode("utf-8")

    if len(transcript.strip()) < 50:
        raise HTTPException(status_code=400, detail="Transcript is too short")

    try:
        memo     = run_memo_agent(transcript)
        tasks    = run_task_agent(transcript)
        meetings = run_meeting_agent(transcript)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"memo": memo, "tasks": tasks, "meetings": meetings}


@app.post("/api/finalize")
def finalize(request: FinalizeRequest):
    memo_dict     = request.memo.model_dump()
    tasks_list    = [t.model_dump() for t in request.tasks]
    meetings_list = [m.model_dump() for m in request.meetings]

    meeting_id = save_meeting(
        memo=memo_dict,
        tasks=tasks_list,
        meetings=meetings_list,
    )

    sheet_url = None
    try:
        sheet_url = update_sheet(
            meeting_id=meeting_id,
            memo=memo_dict,
            tasks=tasks_list,
            meetings=meetings_list,
        )
    except Exception as e:
        print(f"[Sheets] Warning: could not update sheet — {e}")

    return {"meeting_id": meeting_id, "status": "saved", "sheet_url": sheet_url}


@app.post("/api/schedule")
def schedule(request: ScheduleRequest):
    results = {"tasks": [], "meetings": []}

    for task in request.tasks:
        try:
            event_id = create_task(task.model_dump())
            results["tasks"].append({"id": task.id, "status": "scheduled", "event_id": event_id})
        except Exception as e:
            results["tasks"].append({"id": task.id, "status": "failed", "error": str(e)})

    for meeting in request.meetings:
        try:
            event_id = create_calendar_event(meeting.model_dump())
            results["meetings"].append({"id": meeting.id, "status": "scheduled", "event_id": event_id})
        except Exception as e:
            results["meetings"].append({"id": meeting.id, "status": "failed", "error": str(e)})

    return results


@app.get("/api/history")
def get_history():
    return load_history()


@app.get("/api/history/{meeting_id}")
def get_meeting_briefing(meeting_id: str):
    try:
        past_meeting = load_meeting(meeting_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")

    try:
        briefing = run_thread_agent(past_meeting)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "meeting_id": meeting_id,
        "meta": {
            "title":     past_meeting["memo"].get("title"),
            "date":      past_meeting["memo"].get("date"),
            "attendees": past_meeting["memo"].get("attendees", []),
        },
        "briefing": briefing,
    }


# ── Serve Frontend (must be LAST) ──────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# --------------------------------------------------------------------------------

# import os
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from pydantic import BaseModel
# from typing import List, Optional

# from agents.memo_agent import run_memo_agent
# from agents.task_agent import run_task_agent
# from agents.meeting_agent import run_meeting_agent
# from agents.thread_agent import run_thread_agent
# from services.storage_service import save_meeting, load_history, load_meeting
# from services.calendar_service import create_calendar_event, create_task
# from services.sheets_service import update_sheet

# app = FastAPI(title="Meeting Intelligence API")

# # Allow frontend (served separately during dev) to call the API
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Serve frontend as static files
# FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")
# if os.path.exists(FRONTEND_DIR):
#     app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# # ── Pydantic models ────────────────────────────────────────────────────────────

# class Task(BaseModel):
#     id: str
#     title: str
#     assignee: str
#     due_date: str
#     priority: str
#     notes: Optional[str] = ""

# class Meeting(BaseModel):
#     id: str
#     title: str
#     purpose: str
#     suggested_date: str
#     duration_mins: int
#     recipients: List[str]
#     agenda: str

# class Memo(BaseModel):
#     title: str
#     date: str
#     attendees: List[str]
#     summary: str
#     decisions: List[str]
#     blockers: List[str]
#     next_steps: List[str]

# class FinalizeRequest(BaseModel):
#     memo: Memo
#     tasks: List[Task]
#     meetings: List[Meeting]

# class ScheduleRequest(BaseModel):
#     meeting_id: str
#     tasks: List[Task]
#     meetings: List[Meeting]


# # ── Endpoints ──────────────────────────────────────────────────────────────────

# @app.get("/api/health")
# def health():
#     return {"status": "ok"}


# @app.post("/api/process-transcript")
# async def process_transcript(file: UploadFile = File(...)):
#     """
#     Accepts a .txt transcript file.
#     Runs all 3 agents in sequence and returns memo, tasks, and meetings.
#     """
#     if not file.filename.endswith(".txt"):
#         raise HTTPException(status_code=400, detail="Only .txt files are supported")

#     content = await file.read()
#     transcript = content.decode("utf-8")

#     if len(transcript.strip()) < 50:
#         raise HTTPException(status_code=400, detail="Transcript is too short")

#     try:
#         memo = run_memo_agent(transcript)
#         tasks = run_task_agent(transcript)
#         meetings = run_meeting_agent(transcript)
#     except ValueError as e:
#         raise HTTPException(status_code=500, detail=str(e))

#     return {
#         "memo": memo,
#         "tasks": tasks,
#         "meetings": meetings,
#     }


# @app.post("/api/finalize")
# def finalize(request: FinalizeRequest):
#     """
#     Saves the manager-approved memo, tasks, and meetings to storage.
#     Also appends the data to the master Google Sheet.
#     Returns the meeting_id and the sheet URL.
#     """
#     memo_dict     = request.memo.model_dump()
#     tasks_list    = [t.model_dump() for t in request.tasks]
#     meetings_list = [m.model_dump() for m in request.meetings]

#     meeting_id = save_meeting(
#         memo=memo_dict,
#         tasks=tasks_list,
#         meetings=meetings_list,
#     )

#     # Update Google Sheets — non-fatal if it fails
#     sheet_url = None
#     try:
#         sheet_url = update_sheet(
#             meeting_id=meeting_id,
#             memo=memo_dict,
#             tasks=tasks_list,
#             meetings=meetings_list,
#         )
#     except Exception as e:
#         print(f"[Sheets] Warning: could not update sheet — {e}")

#     return {
#         "meeting_id": meeting_id,
#         "status": "saved",
#         "sheet_url": sheet_url,
#     }


# @app.post("/api/schedule")
# def schedule(request: ScheduleRequest):
#     """
#     Pushes finalized tasks and meetings to Google Calendar.
#     """
#     results = {"tasks": [], "meetings": []}

#     for task in request.tasks:
#         try:
#             event_id = create_task(task.model_dump())
#             results["tasks"].append({"id": task.id, "status": "scheduled", "event_id": event_id})
#         except Exception as e:
#             results["tasks"].append({"id": task.id, "status": "failed", "error": str(e)})

#     for meeting in request.meetings:
#         try:
#             event_id = create_calendar_event(meeting.model_dump())
#             results["meetings"].append({"id": meeting.id, "status": "scheduled", "event_id": event_id})
#         except Exception as e:
#             results["meetings"].append({"id": meeting.id, "status": "failed", "error": str(e)})

#     return results


# @app.get("/api/history")
# def get_history():
#     """Returns the list of all past meetings for the sidebar."""
#     return load_history()


# @app.get("/api/history/{meeting_id}")
# def get_meeting_briefing(meeting_id: str):
#     """
#     Returns a thread-agent briefing for a specific past meeting.
#     """
#     try:
#         past_meeting = load_meeting(meeting_id)
#     except FileNotFoundError:
#         raise HTTPException(status_code=404, detail="Meeting not found")

#     try:
#         briefing = run_thread_agent(past_meeting)
#     except ValueError as e:
#         raise HTTPException(status_code=500, detail=str(e))

#     return {
#         "meeting_id": meeting_id,
#         "meta": {
#             "title": past_meeting["memo"].get("title"),
#             "date": past_meeting["memo"].get("date"),
#             "attendees": past_meeting["memo"].get("attendees", []),
#         },
#         "briefing": briefing,
#     }