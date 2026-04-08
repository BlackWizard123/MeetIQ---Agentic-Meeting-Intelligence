import os, json as _json
from datetime import date, datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

from database import init_db, get_conn, get_cursor
from agents.memo_agent import run_memo_agent
from agents.task_agent import run_task_agent
from agents.meeting_agent import run_meeting_agent
from agents.thread_agent import run_thread_agent
from services.storage_service import (save_meeting, load_history, load_meeting,
                                       save_briefing, load_briefing)
from services.calendar_service import create_calendar_event, create_task
from services.sheets_service import update_sheet, update_task_tracker
from routers.projects_router import router as projects_router

MANAGER_EMAIL = os.getenv("MANAGER_EMAIL","")
MANAGER_NAME  = os.getenv("MANAGER_NAME","hariharan-projectmanager")

app = FastAPI(title="Meeting Intelligence API")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
app.include_router(projects_router)

@app.on_event("startup")
def startup(): init_db()

# ── Models ─────────────────────────────────────────────────────────────────
class Task(BaseModel):
    id: str
    title: str
    description: Optional[str]=""
    assignee: str
    assignee_email: Optional[str]=""
    companion: Optional[str]=""
    guide: Optional[str]=""
    checker: Optional[str]="hariharan-projectmanager"
    due_date: str
    assigned_date: Optional[str]=""
    total_days: Optional[int]=None
    priority: str
    notes: Optional[str]=""
    escalation_details: Optional[str]=""
    skills_required: Optional[List[str]]=[]
    skill_match: Optional[str]=""

class Meeting(BaseModel):
    id: str; title: str; purpose: str; suggested_date: str
    duration_mins: int; recipients: List[str]; agenda: str

class Memo(BaseModel):
    title: str; date: str; attendees: List[str]
    project: Optional[str]=""
    summary_points: Optional[List[str]]=[]
    key_decisions: Optional[List[str]]=[]
    blockers: Optional[List[str]]=[]
    risks: Optional[List[str]]=[]
    dependencies: Optional[List[str]]=[]
    next_steps: Optional[List[str]]=[]
    manager_actions: Optional[List[str]]=[]
    open_questions: Optional[List[str]]=[]
    highlights: Optional[List[str]]=[]
    follow_up_required: Optional[bool]=False

class FinalizeRequest(BaseModel):
    memo: Memo; tasks: List[Task]; meetings: List[Meeting]
    project_id: Optional[int]=None; project_name: Optional[str]=""

class ScheduleRequest(BaseModel):
    meeting_id: str; tasks: List[Task]; meetings: List[Meeting]

# ── Helpers ────────────────────────────────────────────────────────────────
def _get_employees(project_id):
    if not project_id: return []
    conn = get_conn(); cur = get_cursor(conn)
    cur.execute("""
        SELECT e.id,e.name,e.email,e.role,e.band,e.level,e.skills,
               COUNT(t.id) FILTER (WHERE t.status!='done') AS active_task_count
        FROM employees e
        LEFT JOIN tasks t ON t.assignee_id=e.id AND t.status!='done'
        WHERE e.project_id=%s GROUP BY e.id
    """,(project_id,))
    rows = cur.fetchall()
    result = []
    for r in rows:
        e = dict(r)
        e["workload_pct"] = min(100, e["active_task_count"]*20)
        cur.execute("SELECT title,priority,status,due_date FROM tasks WHERE assignee_id=%s AND status!='done'",(e["id"],))
        e["current_tasks"] = [dict(t) for t in cur.fetchall()]
        cur.execute("SELECT title FROM tasks WHERE assignee_id=%s AND status='done'",(e["id"],))
        e["completed_tasks"] = [dict(t) for t in cur.fetchall()]
        result.append(e)
    cur.close(); conn.close()
    return result

# ── Endpoints ──────────────────────────────────────────────────────────────
@app.get("/api/health")
def health(): return {"status":"ok"}


@app.post("/api/process-transcript")
async def process_transcript(file: UploadFile=File(...), project_id: Optional[int]=None):
    if not file.filename.endswith(".txt"):
        raise HTTPException(400,"Only .txt files are supported")
    transcript = (await file.read()).decode("utf-8")
    if len(transcript.strip()) < 50:
        raise HTTPException(400,"Transcript is too short")
    employees = _get_employees(project_id)
    try:
        memo     = run_memo_agent(transcript)
        tasks    = run_task_agent(transcript, employees)
        meetings = run_meeting_agent(transcript)
    except ValueError as e:
        raise HTTPException(500, str(e))
    return {"memo":memo,"tasks":tasks,"meetings":meetings,"employees":employees}


@app.post("/api/finalize")
def finalize(request: FinalizeRequest):
    memo_dict     = request.memo.model_dump()
    tasks_list    = [t.model_dump() for t in request.tasks]
    meetings_list = [m.model_dump() for m in request.meetings]
    project_name  = request.project_name or memo_dict.get("project","Unknown")

    meeting_id = save_meeting(memo=memo_dict,tasks=tasks_list,meetings=meetings_list,project_name=project_name)

    # Save tasks to DB
    if request.project_id:
        try:
            conn = get_conn(); cur = get_cursor(conn)
            for t in tasks_list:
                def resolve(name):
                    if not name: return None
                    cur.execute("SELECT id FROM employees WHERE name ILIKE %s AND project_id=%s",(name,request.project_id))
                    r = cur.fetchone(); return r["id"] if r else None
                snapshot = []
                aid = resolve(t.get("assignee"))
                if aid:
                    cur.execute("SELECT title,priority,status FROM tasks WHERE assignee_id=%s AND status!='done'",(aid,))
                    snapshot = [dict(r) for r in cur.fetchall()]
                due = t.get("due_date") if t.get("due_date") not in ("TBD","",None) else None
                cur.execute("""
                    INSERT INTO tasks (title,project_id,meeting_id,
                        assignee_id,companion_id,guide_id,checker_id,
                        status,priority,assigned_date,due_date,total_days,
                        notes,escalation_details,current_tasks_snapshot)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',%s,NOW(),%s,%s,%s,%s,%s)
                """,(t.get("title"),request.project_id,meeting_id,
                     aid,resolve(t.get("companion")),resolve(t.get("guide")),resolve(t.get("checker")),
                     t.get("priority","Medium"),due,t.get("total_days"),
                     t.get("notes",""),t.get("escalation_details",""),_json.dumps(snapshot)))
            conn.commit(); cur.close(); conn.close()
        except Exception as e:
            print(f"[DB] Warning: {e}")

    sheet_url = tracker_url = None
    try:
        sheet_url = update_sheet(meeting_id,project_name,memo_dict,tasks_list,meetings_list)
    except Exception as e: print(f"[Sheets] {e}")

    if request.project_id:
        try:
            conn = get_conn(); cur = get_cursor(conn)
            cur.execute("""
                SELECT t.id,t.title,t.status,t.priority,t.assigned_date,t.due_date,
                       t.total_days,t.notes,t.meeting_id,t.completed_at,
                       a.name AS assignee_name,c.name AS companion_name,
                       g.name AS guide_name,ch.name AS checker_name
                FROM tasks t
                LEFT JOIN employees a  ON a.id=t.assignee_id
                LEFT JOIN employees c  ON c.id=t.companion_id
                LEFT JOIN employees g  ON g.id=t.guide_id
                LEFT JOIN employees ch ON ch.id=t.checker_id
                WHERE t.project_id=%s
            """,(request.project_id,))
            all_tasks = [dict(r) for r in cur.fetchall()]
            cur.execute("""
                SELECT e.id,e.name,e.role,e.band,e.level,
                       COUNT(t.id) FILTER (WHERE t.status!='done') AS active_task_count
                FROM employees e LEFT JOIN tasks t ON t.assignee_id=e.id
                WHERE e.project_id=%s GROUP BY e.id
            """,(request.project_id,))
            all_emps = [dict(r) for r in cur.fetchall()]
            for e in all_emps: e["workload_pct"] = min(100,e["active_task_count"]*20)
            cur.close(); conn.close()
            tracker_url = update_task_tracker(project_name,all_tasks,all_emps)
        except Exception as e: print(f"[Tracker] {e}")

    return {"meeting_id":meeting_id,"status":"saved",
            "sheet_url":sheet_url,"tracker_url":tracker_url}


@app.post("/api/schedule")
def schedule(request: ScheduleRequest):
    results = {"tasks":[],"meetings":[]}
    for task in request.tasks:
        try:
            eid = create_task(task.model_dump())
            results["tasks"].append({"id":task.id,"status":"scheduled","event_id":eid})
        except Exception as e:
            results["tasks"].append({"id":task.id,"status":"failed","error":str(e)})
    for mtg in request.meetings:
        try:
            eid = create_calendar_event(mtg.model_dump())
            results["meetings"].append({"id":mtg.id,"status":"scheduled","event_id":eid})
        except Exception as e:
            results["meetings"].append({"id":mtg.id,"status":"failed","error":str(e)})
    return results


@app.get("/api/history")
def get_history(): return load_history()


@app.get("/api/history/{meeting_id}")
def get_meeting_briefing(
    meeting_id: str,
    project_id: Optional[int] = Query(None),
    refresh: bool = Query(False),
):
    try:
        past_meeting = load_meeting(meeting_id)
    except FileNotFoundError:
        raise HTTPException(404,"Meeting not found")

    # Return cached briefing unless refresh=true
    if not refresh:
        cached = load_briefing(meeting_id)
        if cached:
            return {
                "meeting_id": meeting_id,
                "meta": {
                    "title":     past_meeting["memo"].get("title"),
                    "date":      past_meeting["memo"].get("date"),
                    "attendees": past_meeting["memo"].get("attendees",[]),
                },
                "briefing": cached,
                "from_cache": True,
            }

    # Generate fresh
    employees = _get_employees(project_id)
    try:
        briefing = run_thread_agent(past_meeting, employees)
    except ValueError as e:
        raise HTTPException(500,str(e))

    # Cache it
    save_briefing(meeting_id, briefing)

    return {
        "meeting_id": meeting_id,
        "meta": {
            "title":     past_meeting["memo"].get("title"),
            "date":      past_meeting["memo"].get("date"),
            "attendees": past_meeting["memo"].get("attendees",[]),
        },
        "briefing": briefing,
        "from_cache": False,
    }




@app.get("/api/transcript/{meeting_id}")
def get_transcript_detail(meeting_id: str):
    """Returns full meeting record for transcript library."""
    try:
        return load_meeting(meeting_id)
    except FileNotFoundError:
        raise HTTPException(404, "Meeting not found")


@app.get("/api/sheet-links")
def get_sheet_links():
    """Returns Google Sheet URLs for each project."""
    import os
    projects = {
        "Enterprise RAG": {
            "log":     f"https://docs.google.com/spreadsheets/d/{os.getenv('SHEET_LOG_RAG')}" if os.getenv('SHEET_LOG_RAG') else None,
            "tracker": f"https://docs.google.com/spreadsheets/d/{os.getenv('SHEET_TRACKER_RAG')}" if os.getenv('SHEET_TRACKER_RAG') else None,
        },
        "Plipkary": {
            "log":     f"https://docs.google.com/spreadsheets/d/{os.getenv('SHEET_LOG_PLIPKARY')}" if os.getenv('SHEET_LOG_PLIPKARY') else None,
            "tracker": f"https://docs.google.com/spreadsheets/d/{os.getenv('SHEET_TRACKER_PLIPKARY')}" if os.getenv('SHEET_TRACKER_PLIPKARY') else None,
        },
    }
    return projects

# ── Frontend ───────────────────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__),"../frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static",StaticFiles(directory=FRONTEND_DIR),name="static")
    @app.get("/")
    def serve_index(): return FileResponse(os.path.join(FRONTEND_DIR,"index.html"))
    @app.get("/{full_path:path}")
    def serve_spa(full_path:str):
        fp = os.path.join(FRONTEND_DIR,full_path)
        return FileResponse(fp if os.path.exists(fp) else os.path.join(FRONTEND_DIR,"index.html"))

# ── Monkey-patch: date serializer injected at bottom ──────────────────────
from datetime import date as _date, datetime as _datetime
import json as _json_mod

class _DateEncoder(_json_mod.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (_date, _datetime)):
            return str(obj)[:10]
        return super().default(obj)

# Patch FastAPI's jsonable_encoder for date objects
from fastapi.encoders import jsonable_encoder as _orig_encoder
import functools

@functools.wraps(_orig_encoder)
def _patched_encoder(obj, **kwargs):
    if isinstance(obj, (_date, _datetime)):
        return str(obj)[:10]
    return _orig_encoder(obj, **kwargs)

#- --------------------------------------------------------------

# import os
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# from pydantic import BaseModel
# from typing import List, Optional

# from database import init_db, get_conn, get_cursor
# from agents.memo_agent import run_memo_agent
# from agents.task_agent import run_task_agent
# from agents.meeting_agent import run_meeting_agent
# from agents.thread_agent import run_thread_agent
# from services.storage_service import save_meeting, load_history, load_meeting
# from services.calendar_service import create_calendar_event, create_task
# from services.sheets_service import update_sheet, update_task_tracker
# from routers.projects_router import router as projects_router

# MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "")
# MANAGER_NAME  = os.getenv("MANAGER_NAME", "hariharan-projectmanager")

# app = FastAPI(title="Meeting Intelligence API")
# app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# app.include_router(projects_router)

# @app.on_event("startup")
# def startup():
#     init_db()

# # ── Models ─────────────────────────────────────────────────────────────────

# class Task(BaseModel):
#     id: str
#     title: str
#     description: Optional[str] = ""
#     assignee: str
#     assignee_email: Optional[str] = ""
#     companion: Optional[str] = ""
#     guide: Optional[str] = ""
#     checker: Optional[str] = "hariharan-projectmanager"
#     due_date: str
#     assigned_date: Optional[str] = ""
#     total_days: Optional[int] = None
#     priority: str
#     notes: Optional[str] = ""
#     escalation_details: Optional[str] = ""
#     skills_required: Optional[List[str]] = []
#     skill_match: Optional[str] = ""

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
#     project: Optional[str] = ""
#     summary_points: Optional[List[str]] = []
#     key_decisions: Optional[List[str]] = []
#     blockers: Optional[List[str]] = []
#     risks: Optional[List[str]] = []
#     dependencies: Optional[List[str]] = []
#     next_steps: Optional[List[str]] = []
#     manager_actions: Optional[List[str]] = []
#     open_questions: Optional[List[str]] = []
#     highlights: Optional[List[str]] = []
#     follow_up_required: Optional[bool] = False

# class FinalizeRequest(BaseModel):
#     memo: Memo
#     tasks: List[Task]
#     meetings: List[Meeting]
#     project_id: Optional[int] = None
#     project_name: Optional[str] = ""

# class ScheduleRequest(BaseModel):
#     meeting_id: str
#     tasks: List[Task]
#     meetings: List[Meeting]

# # ── Endpoints ──────────────────────────────────────────────────────────────

# @app.get("/api/health")
# def health():
#     return {"status": "ok"}


# @app.post("/api/process-transcript")
# async def process_transcript(
#     file: UploadFile = File(...),
#     project_id: Optional[int] = None,
# ):
#     if not file.filename.endswith(".txt"):
#         raise HTTPException(400, "Only .txt files are supported")

#     transcript = (await file.read()).decode("utf-8")
#     if len(transcript.strip()) < 50:
#         raise HTTPException(400, "Transcript is too short")

#     # Fetch project employees for smart assignment
#     employees = []
#     if project_id:
#         conn = get_conn(); cur = get_cursor(conn)
#         cur.execute("""
#             SELECT e.id, e.name, e.email, e.role, e.band, e.level, e.skills,
#                    COUNT(t.id) FILTER (WHERE t.status != 'done') AS active_task_count
#             FROM employees e
#             LEFT JOIN tasks t ON t.assignee_id = e.id AND t.status != 'done'
#             WHERE e.project_id = %s
#             GROUP BY e.id
#         """, (project_id,))
#         rows = cur.fetchall()
#         employees = []
#         for r in rows:
#             e = dict(r)
#             e["workload_pct"] = min(100, e["active_task_count"] * 20)
#             cur.execute("""
#                 SELECT title, priority, status FROM tasks
#                 WHERE assignee_id = %s AND status != 'done'
#             """, (e["id"],))
#             e["current_tasks"] = [dict(t) for t in cur.fetchall()]
#             employees.append(e)
#         cur.close(); conn.close()

#     try:
#         memo     = run_memo_agent(transcript)
#         tasks    = run_task_agent(transcript, employees)
#         meetings = run_meeting_agent(transcript)
#     except ValueError as e:
#         raise HTTPException(500, str(e))

#     return {"memo": memo, "tasks": tasks, "meetings": meetings, "employees": employees}


# @app.post("/api/finalize")
# def finalize(request: FinalizeRequest):
#     memo_dict     = request.memo.model_dump()
#     tasks_list    = [t.model_dump() for t in request.tasks]
#     meetings_list = [m.model_dump() for m in request.meetings]
#     project_name  = request.project_name or memo_dict.get("project", "Unknown")

#     meeting_id = save_meeting(memo=memo_dict, tasks=tasks_list, meetings=meetings_list)

#     # Save tasks to DB
#     if request.project_id:
#         try:
#             conn = get_conn(); cur = get_cursor(conn)
#             for t in tasks_list:
#                 def resolve(name):
#                     if not name: return None
#                     cur.execute("SELECT id FROM employees WHERE name ILIKE %s AND project_id = %s",
#                                 (name, request.project_id))
#                     row = cur.fetchone()
#                     return row["id"] if row else None

#                 import json as _json
#                 snapshot = []
#                 assignee_id = resolve(t.get("assignee"))
#                 if assignee_id:
#                     cur.execute("SELECT title, priority, status FROM tasks WHERE assignee_id=%s AND status!='done'",
#                                 (assignee_id,))
#                     snapshot = [dict(r) for r in cur.fetchall()]

#                 due = t.get("due_date") if t.get("due_date") not in ("TBD","",None) else None
#                 cur.execute("""
#                     INSERT INTO tasks (
#                         title, project_id, meeting_id,
#                         assignee_id, companion_id, guide_id, checker_id,
#                         status, priority, assigned_date, due_date, total_days,
#                         notes, escalation_details, current_tasks_snapshot
#                     ) VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',%s,NOW(),%s,%s,%s,%s,%s)
#                 """, (
#                     t.get("title"), request.project_id, meeting_id,
#                     assignee_id, resolve(t.get("companion")),
#                     resolve(t.get("guide")), resolve(t.get("checker")),
#                     t.get("priority","Medium"), due,
#                     t.get("total_days"), t.get("notes",""),
#                     t.get("escalation_details",""), _json.dumps(snapshot),
#                 ))
#             conn.commit(); cur.close(); conn.close()
#         except Exception as e:
#             print(f"[DB] Task save warning: {e}")

#     # Update meeting log sheet
#     sheet_url = None
#     try:
#         sheet_url = update_sheet(
#             meeting_id=meeting_id,
#             project_name=project_name,
#             memo=memo_dict, tasks=tasks_list, meetings=meetings_list,
#         )
#     except Exception as e:
#         print(f"[Sheets] Warning: {e}")

#     # Update task tracker sheet
#     tracker_url = None
#     if request.project_id:
#         try:
#             conn = get_conn(); cur = get_cursor(conn)
#             cur.execute("""
#                 SELECT t.id, t.title, t.status, t.priority,
#                        t.assigned_date, t.due_date, t.total_days,
#                        t.notes, t.meeting_id, t.completed_at,
#                        a.name AS assignee_name,
#                        c.name AS companion_name,
#                        g.name AS guide_name,
#                        ch.name AS checker_name
#                 FROM tasks t
#                 LEFT JOIN employees a  ON a.id = t.assignee_id
#                 LEFT JOIN employees c  ON c.id = t.companion_id
#                 LEFT JOIN employees g  ON g.id = t.guide_id
#                 LEFT JOIN employees ch ON ch.id = t.checker_id
#                 WHERE t.project_id = %s
#             """, (request.project_id,))
#             all_tasks = [dict(r) for r in cur.fetchall()]

#             cur.execute("""
#                 SELECT e.id, e.name, e.role, e.band, e.level,
#                        COUNT(t.id) FILTER (WHERE t.status != 'done') AS active_task_count
#                 FROM employees e
#                 LEFT JOIN tasks t ON t.assignee_id = e.id
#                 WHERE e.project_id = %s GROUP BY e.id
#             """, (request.project_id,))
#             all_emps = [dict(r) for r in cur.fetchall()]
#             for emp in all_emps:
#                 emp["workload_pct"] = min(100, emp["active_task_count"] * 20)
#             cur.close(); conn.close()

#             tracker_url = update_task_tracker(project_name, all_tasks, all_emps)
#         except Exception as e:
#             print(f"[Tracker] Warning: {e}")

#     return {
#         "meeting_id": meeting_id,
#         "status": "saved",
#         "sheet_url": sheet_url,
#         "tracker_url": tracker_url,
#     }


# @app.post("/api/schedule")
# def schedule(request: ScheduleRequest):
#     results = {"tasks": [], "meetings": []}
#     for task in request.tasks:
#         try:
#             eid = create_task(task.model_dump())
#             results["tasks"].append({"id": task.id, "status": "scheduled", "event_id": eid})
#         except Exception as e:
#             results["tasks"].append({"id": task.id, "status": "failed", "error": str(e)})
#     for mtg in request.meetings:
#         try:
#             eid = create_calendar_event(mtg.model_dump())
#             results["meetings"].append({"id": mtg.id, "status": "scheduled", "event_id": eid})
#         except Exception as e:
#             results["meetings"].append({"id": mtg.id, "status": "failed", "error": str(e)})
#     return results


# @app.get("/api/history")
# def get_history():
#     return load_history()


# @app.get("/api/history/{meeting_id}")
# def get_meeting_briefing(meeting_id: str, project_id: Optional[int] = None):
#     try:
#         past_meeting = load_meeting(meeting_id)
#     except FileNotFoundError:
#         raise HTTPException(404, "Meeting not found")

#     employees = []
#     if project_id:
#         conn = get_conn(); cur = get_cursor(conn)
#         cur.execute("""
#             SELECT e.id, e.name, e.role, e.band, e.level,
#                    COUNT(t.id) FILTER (WHERE t.status != 'done') AS active_task_count
#             FROM employees e
#             LEFT JOIN tasks t ON t.assignee_id = e.id AND t.status != 'done'
#             WHERE e.project_id = %s GROUP BY e.id
#         """, (project_id,))
#         rows = cur.fetchall()
#         for r in rows:
#             e = dict(r)
#             cur.execute("SELECT title, priority, status, due_date FROM tasks WHERE assignee_id=%s AND status!='done'",
#                         (e["id"],))
#             e["current_tasks"] = [dict(t) for t in cur.fetchall()]
#             cur.execute("SELECT title FROM tasks WHERE assignee_id=%s AND status='done'", (e["id"],))
#             e["completed_tasks"] = [dict(t) for t in cur.fetchall()]
#             e["workload_pct"] = min(100, e["active_task_count"] * 20)
#             employees.append(e)
#         cur.close(); conn.close()

#     try:
#         briefing = run_thread_agent(past_meeting, employees)
#     except ValueError as e:
#         raise HTTPException(500, str(e))

#     return {
#         "meeting_id": meeting_id,
#         "meta": {
#             "title":     past_meeting["memo"].get("title"),
#             "date":      past_meeting["memo"].get("date"),
#             "attendees": past_meeting["memo"].get("attendees", []),
#         },
#         "briefing": briefing,
#     }


# # ── Frontend ────────────────────────────────────────────────────────────────
# FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")
# if os.path.exists(FRONTEND_DIR):
#     app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

#     @app.get("/")
#     def serve_index():
#         return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

#     @app.get("/{full_path:path}")
#     def serve_spa(full_path: str):
#         fp = os.path.join(FRONTEND_DIR, full_path)
#         return FileResponse(fp if os.path.exists(fp) else os.path.join(FRONTEND_DIR, "index.html"))

# --------------------------------------------------------------

# import os
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
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

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ── Pydantic models ────────────────────────────────────────────────────────

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


# # ── API Endpoints ──────────────────────────────────────────────────────────

# @app.get("/api/health")
# def health():
#     return {"status": "ok"}


# @app.post("/api/process-transcript")
# async def process_transcript(file: UploadFile = File(...)):
#     if not file.filename.endswith(".txt"):
#         raise HTTPException(status_code=400, detail="Only .txt files are supported")

#     content = await file.read()
#     transcript = content.decode("utf-8")

#     if len(transcript.strip()) < 50:
#         raise HTTPException(status_code=400, detail="Transcript is too short")

#     try:
#         memo     = run_memo_agent(transcript)
#         tasks    = run_task_agent(transcript)
#         meetings = run_meeting_agent(transcript)
#     except ValueError as e:
#         raise HTTPException(status_code=500, detail=str(e))

#     return {"memo": memo, "tasks": tasks, "meetings": meetings}


# @app.post("/api/finalize")
# def finalize(request: FinalizeRequest):
#     memo_dict     = request.memo.model_dump()
#     tasks_list    = [t.model_dump() for t in request.tasks]
#     meetings_list = [m.model_dump() for m in request.meetings]

#     meeting_id = save_meeting(
#         memo=memo_dict,
#         tasks=tasks_list,
#         meetings=meetings_list,
#     )

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

#     return {"meeting_id": meeting_id, "status": "saved", "sheet_url": sheet_url}


# @app.post("/api/schedule")
# def schedule(request: ScheduleRequest):
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
#     return load_history()


# @app.get("/api/history/{meeting_id}")
# def get_meeting_briefing(meeting_id: str):
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
#             "title":     past_meeting["memo"].get("title"),
#             "date":      past_meeting["memo"].get("date"),
#             "attendees": past_meeting["memo"].get("attendees", []),
#         },
#         "briefing": briefing,
#     }


# # ── Serve Frontend (must be LAST) ──────────────────────────────────────────
# FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")

# if os.path.exists(FRONTEND_DIR):
#     app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

#     @app.get("/")
#     def serve_index():
#         return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

#     @app.get("/{full_path:path}")
#     def serve_spa(full_path: str):
#         file_path = os.path.join(FRONTEND_DIR, full_path)
#         if os.path.exists(file_path):
#             return FileResponse(file_path)
#         return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

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