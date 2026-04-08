import os, json
from datetime import datetime, date
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "../token.json")
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Sheet IDs loaded from env — set by setup_sheets.py
SHEET_IDS = {
    "Enterprise RAG": {
        "log":     os.getenv("SHEET_LOG_RAG"),
        "tracker": os.getenv("SHEET_TRACKER_RAG"),
    },
    "Plipkary": {
        "log":     os.getenv("SHEET_LOG_PLIPKARY"),
        "tracker": os.getenv("SHEET_TRACKER_PLIPKARY"),
    },
}

C_HIGH   = {"red":1.00,"green":0.80,"blue":0.80}
C_MEDIUM = {"red":1.00,"green":0.95,"blue":0.80}
C_LOW    = {"red":0.85,"green":0.95,"blue":0.85}
C_DONE   = {"red":0.85,"green":0.85,"blue":0.85}
C_WHITE  = {"red":1.00,"green":1.00,"blue":1.00}
C_LIGHT  = {"red":0.95,"green":0.97,"blue":0.99}

from services.token_loader import load_token

def _creds():
    return Credentials.from_authorized_user_info(load_token(), SCOPES)

def _sheets(): return build("sheets","v4",credentials=_creds())

def _safe_str(val):
    if val is None: return ""
    if isinstance(val, (date, datetime)): return str(val)[:10]
    if isinstance(val, list): return "\n• ".join(str(v) for v in val) if val else ""
    return str(val)

def _priority_color(p):
    return {"High":C_HIGH,"Medium":C_MEDIUM,"Low":C_LOW}.get(p, C_WHITE)

def _get_sheet_id(sheets_svc, spreadsheet_id, tab_name):
    meta = sheets_svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == tab_name:
            return s["properties"]["sheetId"]
    return None


# ── Meeting Log ───────────────────────────────────────────────────────────

def update_sheet(meeting_id, project_name, memo, tasks, meetings):
    """Appends a new meeting row to the static Meeting Log sheet."""
    ids = SHEET_IDS.get(project_name)
    if not ids or not ids.get("log"):
        print(f"[Sheets] No log sheet ID for {project_name}")
        return None

    sid = ids["log"]
    svc = _sheets()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── Overview row ──
    overview_row = [[
        meeting_id, now,
        _safe_str(memo.get("title")),
        _safe_str(memo.get("date")),
        project_name,
        ", ".join(memo.get("attendees",[])),
        "• " + "\n• ".join(memo.get("summary_points",[])) if memo.get("summary_points") else _safe_str(memo.get("summary","")),
        "• " + "\n• ".join(memo.get("key_decisions",[])) if memo.get("key_decisions") else "",
        "• " + "\n• ".join(memo.get("blockers",[])) if memo.get("blockers") else "",
        "• " + "\n• ".join(memo.get("risks",[])) if memo.get("risks") else "",
        "• " + "\n• ".join(memo.get("next_steps",[])) if memo.get("next_steps") else "",
        "• " + "\n• ".join(memo.get("manager_actions",[])) if memo.get("manager_actions") else "",
        "• " + "\n• ".join(memo.get("open_questions",[])) if memo.get("open_questions") else "",
        "• " + "\n• ".join(memo.get("highlights",[])) if memo.get("highlights") else "",
        "Yes" if memo.get("follow_up_required") else "No",
        str(len(tasks)),
        str(len(meetings)),
    ]]

    # ── Task rows ──
    task_rows = []
    for t in tasks:
        task_rows.append([
            meeting_id, _safe_str(memo.get("title")),
            _safe_str(t.get("id")), _safe_str(t.get("title")),
            _safe_str(t.get("description","")),
            _safe_str(t.get("assignee","")), _safe_str(t.get("assignee_email","")),
            _safe_str(t.get("companion","")), _safe_str(t.get("guide","")),
            _safe_str(t.get("checker","Manager")),
            _safe_str(t.get("priority","Medium")),
            _safe_str(t.get("assigned_date",str(datetime.utcnow().date()))),
            _safe_str(t.get("due_date","TBD")),
            _safe_str(t.get("total_days","")),
            _safe_str(t.get("skill_match","")),
            _safe_str(t.get("notes","")),
            _safe_str(t.get("escalation_details","")),
            "pending",
        ])

    # ── Meeting rows ──
    mtg_rows = []
    for m in meetings:
        agenda = m.get("agenda","")
        if isinstance(agenda, list): agenda = "; ".join(agenda)
        mtg_rows.append([
            meeting_id, _safe_str(memo.get("title")),
            _safe_str(m.get("title","")), _safe_str(m.get("purpose","")),
            _safe_str(m.get("suggested_date","TBD")),
            str(m.get("duration_mins",30)),
            ", ".join(m.get("recipients",[])),
            agenda,
        ])

    # Append all
    batch = {"valueInputOption":"RAW","data":[
        {"range":"Overview!A:Q", "values":overview_row},
    ]}
    if task_rows: batch["data"].append({"range":"Tasks!A:R","values":task_rows})
    if mtg_rows:  batch["data"].append({"range":"Meetings!A:H","values":mtg_rows})

    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=sid, body=batch).execute()

    # Color priority column in Tasks (col K = index 10)
    if task_rows:
        tasks_sheet_id = _get_sheet_id(svc, sid, "Tasks")
        result = svc.spreadsheets().values().get(
            spreadsheetId=sid, range="Tasks!A:A").execute()
        start = len(result.get("values",[])) - len(task_rows)
        requests = []
        for i, t in enumerate(tasks):
            requests.append({"repeatCell":{
                "range":{"sheetId":tasks_sheet_id,
                         "startRowIndex":start+i,"endRowIndex":start+i+1,
                         "startColumnIndex":10,"endColumnIndex":11},
                "cell":{"userEnteredFormat":{
                    "backgroundColor":_priority_color(t.get("priority","Medium")),
                    "textFormat":{"bold":True},
                }},
                "fields":"userEnteredFormat(backgroundColor,textFormat)",
            }})
        svc.spreadsheets().batchUpdate(spreadsheetId=sid,
            body={"requests":requests}).execute()

    return f"https://docs.google.com/spreadsheets/d/{sid}"


# ── Task Tracker ──────────────────────────────────────────────────────────

def update_task_tracker(project_name, all_tasks, employees):
    """
    Updates the static Task Tracker sheet in place.
    Each employee has a fixed row — we update their columns directly.
    Completed tasks are appended to the Completed Tasks tab.
    """
    ids = SHEET_IDS.get(project_name)
    if not ids or not ids.get("tracker"):
        print(f"[Tracker] No tracker sheet ID for {project_name}")
        return None

    sid = ids["tracker"]
    svc = _sheets()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    # Build per-employee task index
    active_by_emp    = {}
    completed_by_emp = {}
    for t in all_tasks:
        name = t.get("assignee_name","")
        if not name: continue
        if t.get("status") == "done":
            completed_by_emp.setdefault(name,[]).append(t)
        else:
            active_by_emp.setdefault(name,[]).append(t)

    # Read current tracker to find employee row numbers
    result = svc.spreadsheets().values().get(
        spreadsheetId=sid, range="Task Tracker!A:A").execute()
    existing_rows = [r[0] if r else "" for r in result.get("values",[])]

    # Build update data for each employee row
    update_data = []
    requests    = []
    tracker_sid = _get_sheet_id(svc, sid, "Task Tracker")

    for emp in employees:
        name = emp.get("name","")
        try:
            row_idx = existing_rows.index(name)  # 0-based
        except ValueError:
            continue

        active    = active_by_emp.get(name,[])
        completed = completed_by_emp.get(name,[])
        total_active    = len(active)
        total_completed = len(completed)
        workload_pct    = min(100, total_active * 20)

        # Fill up to 3 active task slots
        def task_cols(tasks, slot):
            if slot < len(tasks):
                t = tasks[slot]
                return [
                    _safe_str(t.get("title","")),
                    _safe_str(t.get("priority","")),
                    _safe_str(t.get("due_date","TBD")),
                ]
            return ["","",""]

        row_values = [
            name,
            emp.get("role",""),
            emp.get("band",""),
            emp.get("level",""),
            *task_cols(active,0),
            *task_cols(active,1),
            *task_cols(active,2),
            str(total_active),
            str(total_completed),
            f"{workload_pct}%",
            now,
        ]

        # Row in sheets is 1-based, +1 for header
        sheet_row = row_idx + 1
        update_data.append({
            "range": f"Task Tracker!A{sheet_row}:Q{sheet_row}",
            "values": [row_values],
        })

        # Color workload cell
        workload_color = C_HIGH if workload_pct>=80 else C_MEDIUM if workload_pct>=40 else C_LOW
        requests.append({"repeatCell":{
            "range":{"sheetId":tracker_sid,
                     "startRowIndex":row_idx,"endRowIndex":row_idx+1,
                     "startColumnIndex":15,"endColumnIndex":16},
            "cell":{"userEnteredFormat":{"backgroundColor":workload_color,
                    "textFormat":{"bold":True}}},
            "fields":"userEnteredFormat(backgroundColor,textFormat)",
        }})

    if update_data:
        svc.spreadsheets().values().batchUpdate(
            spreadsheetId=sid,
            body={"valueInputOption":"RAW","data":update_data}
        ).execute()

    # Append newly completed tasks to Completed Tasks tab
    newly_done = [t for t in all_tasks if t.get("status")=="done"]
    if newly_done:
        # Check existing completed to avoid dupes
        existing = svc.spreadsheets().values().get(
            spreadsheetId=sid, range="Completed Tasks!A:A").execute()
        existing_ids = {r[0] for r in existing.get("values",[])[1:] if r}

        new_rows = []
        for t in newly_done:
            tid = str(t.get("id",""))
            if tid not in existing_ids:
                new_rows.append([
                    t.get("assignee_name",""),
                    t.get("role","") if "role" in t else "",
                    _safe_str(t.get("title","")),
                    _safe_str(t.get("completed_at",now)),
                    _safe_str(t.get("meeting_id","")),
                    _safe_str(t.get("notes","")),
                ])
        if new_rows:
            svc.spreadsheets().values().append(
                spreadsheetId=sid, range="Completed Tasks!A:F",
                valueInputOption="RAW", insertDataOption="INSERT_ROWS",
                body={"values":new_rows}
            ).execute()
            # Grey out completed rows
            comp_sid = _get_sheet_id(svc, sid, "Completed Tasks")
            existing_count = len(existing.get("values",[])) 
            for i in range(len(new_rows)):
                requests.append({"repeatCell":{
                    "range":{"sheetId":comp_sid,
                             "startRowIndex":existing_count+i,
                             "endRowIndex":existing_count+i+1,
                             "startColumnIndex":0,"endColumnIndex":6},
                    "cell":{"userEnteredFormat":{"backgroundColor":C_DONE}},
                    "fields":"userEnteredFormat.backgroundColor",
                }})

    if requests:
        svc.spreadsheets().batchUpdate(spreadsheetId=sid,
            body={"requests":requests}).execute()

    return f"https://docs.google.com/spreadsheets/d/{sid}"

# -----------------------------------------------------------------

# import os, json
# from datetime import datetime, date
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build

# TOKEN_FILE = os.path.join(os.path.dirname(__file__), "../token.json")
# SCOPES = [
#     "https://www.googleapis.com/auth/calendar",
#     "https://www.googleapis.com/auth/tasks",
#     "https://www.googleapis.com/auth/spreadsheets",
#     "https://www.googleapis.com/auth/drive.file",
# ]

# # Sheet IDs loaded from env — set by setup_sheets.py
# SHEET_IDS = {
#     "Enterprise RAG": {
#         "log":     os.getenv("SHEET_LOG_RAG"),
#         "tracker": os.getenv("SHEET_TRACKER_RAG"),
#     },
#     "Plipkary": {
#         "log":     os.getenv("SHEET_LOG_PLIPKARY"),
#         "tracker": os.getenv("SHEET_TRACKER_PLIPKARY"),
#     },
# }

# C_HIGH   = {"red":1.00,"green":0.80,"blue":0.80}
# C_MEDIUM = {"red":1.00,"green":0.95,"blue":0.80}
# C_LOW    = {"red":0.85,"green":0.95,"blue":0.85}
# C_DONE   = {"red":0.85,"green":0.85,"blue":0.85}
# C_WHITE  = {"red":1.00,"green":1.00,"blue":1.00}
# C_LIGHT  = {"red":0.95,"green":0.97,"blue":0.99}

# def _creds():
#     with open(TOKEN_FILE) as f:
#         return Credentials.from_authorized_user_info(json.load(f), SCOPES)

# def _sheets(): return build("sheets","v4",credentials=_creds())

# def _safe_str(val):
#     if val is None: return ""
#     if isinstance(val, (date, datetime)): return str(val)[:10]
#     if isinstance(val, list): return "\n• ".join(str(v) for v in val) if val else ""
#     return str(val)

# def _priority_color(p):
#     return {"High":C_HIGH,"Medium":C_MEDIUM,"Low":C_LOW}.get(p, C_WHITE)

# def _get_sheet_id(sheets_svc, spreadsheet_id, tab_name):
#     meta = sheets_svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
#     for s in meta["sheets"]:
#         if s["properties"]["title"] == tab_name:
#             return s["properties"]["sheetId"]
#     return None


# # ── Meeting Log ───────────────────────────────────────────────────────────

# def update_sheet(meeting_id, project_name, memo, tasks, meetings):
#     """Appends a new meeting row to the static Meeting Log sheet."""
#     ids = SHEET_IDS.get(project_name)
#     if not ids or not ids.get("log"):
#         print(f"[Sheets] No log sheet ID for {project_name}")
#         return None

#     sid = ids["log"]
#     svc = _sheets()
#     now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

#     # ── Overview row ──
#     overview_row = [[
#         meeting_id, now,
#         _safe_str(memo.get("title")),
#         _safe_str(memo.get("date")),
#         project_name,
#         ", ".join(memo.get("attendees",[])),
#         "• " + "\n• ".join(memo.get("summary_points",[])) if memo.get("summary_points") else _safe_str(memo.get("summary","")),
#         "• " + "\n• ".join(memo.get("key_decisions",[])) if memo.get("key_decisions") else "",
#         "• " + "\n• ".join(memo.get("blockers",[])) if memo.get("blockers") else "",
#         "• " + "\n• ".join(memo.get("risks",[])) if memo.get("risks") else "",
#         "• " + "\n• ".join(memo.get("next_steps",[])) if memo.get("next_steps") else "",
#         "• " + "\n• ".join(memo.get("manager_actions",[])) if memo.get("manager_actions") else "",
#         "• " + "\n• ".join(memo.get("open_questions",[])) if memo.get("open_questions") else "",
#         "• " + "\n• ".join(memo.get("highlights",[])) if memo.get("highlights") else "",
#         "Yes" if memo.get("follow_up_required") else "No",
#         str(len(tasks)),
#         str(len(meetings)),
#     ]]

#     # ── Task rows ──
#     task_rows = []
#     for t in tasks:
#         task_rows.append([
#             meeting_id, _safe_str(memo.get("title")),
#             _safe_str(t.get("id")), _safe_str(t.get("title")),
#             _safe_str(t.get("description","")),
#             _safe_str(t.get("assignee","")), _safe_str(t.get("assignee_email","")),
#             _safe_str(t.get("companion","")), _safe_str(t.get("guide","")),
#             _safe_str(t.get("checker","Manager")),
#             _safe_str(t.get("priority","Medium")),
#             _safe_str(t.get("assigned_date",str(datetime.utcnow().date()))),
#             _safe_str(t.get("due_date","TBD")),
#             _safe_str(t.get("total_days","")),
#             _safe_str(t.get("skill_match","")),
#             _safe_str(t.get("notes","")),
#             _safe_str(t.get("escalation_details","")),
#             "pending",
#         ])

#     # ── Meeting rows ──
#     mtg_rows = []
#     for m in meetings:
#         agenda = m.get("agenda","")
#         if isinstance(agenda, list): agenda = "; ".join(agenda)
#         mtg_rows.append([
#             meeting_id, _safe_str(memo.get("title")),
#             _safe_str(m.get("title","")), _safe_str(m.get("purpose","")),
#             _safe_str(m.get("suggested_date","TBD")),
#             str(m.get("duration_mins",30)),
#             ", ".join(m.get("recipients",[])),
#             agenda,
#         ])

#     # Append all
#     batch = {"valueInputOption":"RAW","data":[
#         {"range":"Overview!A:Q", "values":overview_row},
#     ]}
#     if task_rows: batch["data"].append({"range":"Tasks!A:R","values":task_rows})
#     if mtg_rows:  batch["data"].append({"range":"Meetings!A:H","values":mtg_rows})

#     svc.spreadsheets().values().batchUpdate(
#         spreadsheetId=sid, body=batch).execute()

#     # Color priority column in Tasks (col K = index 10)
#     if task_rows:
#         tasks_sheet_id = _get_sheet_id(svc, sid, "Tasks")
#         result = svc.spreadsheets().values().get(
#             spreadsheetId=sid, range="Tasks!A:A").execute()
#         start = len(result.get("values",[])) - len(task_rows)
#         requests = []
#         for i, t in enumerate(tasks):
#             requests.append({"repeatCell":{
#                 "range":{"sheetId":tasks_sheet_id,
#                          "startRowIndex":start+i,"endRowIndex":start+i+1,
#                          "startColumnIndex":10,"endColumnIndex":11},
#                 "cell":{"userEnteredFormat":{
#                     "backgroundColor":_priority_color(t.get("priority","Medium")),
#                     "textFormat":{"bold":True},
#                 }},
#                 "fields":"userEnteredFormat(backgroundColor,textFormat)",
#             }})
#         svc.spreadsheets().batchUpdate(spreadsheetId=sid,
#             body={"requests":requests}).execute()

#     return f"https://docs.google.com/spreadsheets/d/{sid}"


# # ── Task Tracker ──────────────────────────────────────────────────────────

# def update_task_tracker(project_name, all_tasks, employees):
#     """
#     Updates the static Task Tracker sheet in place.
#     Each employee has a fixed row — we update their columns directly.
#     Completed tasks are appended to the Completed Tasks tab.
#     """
#     ids = SHEET_IDS.get(project_name)
#     if not ids or not ids.get("tracker"):
#         print(f"[Tracker] No tracker sheet ID for {project_name}")
#         return None

#     sid = ids["tracker"]
#     svc = _sheets()
#     now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

#     # Build per-employee task index
#     active_by_emp    = {}
#     completed_by_emp = {}
#     for t in all_tasks:
#         name = t.get("assignee_name","")
#         if not name: continue
#         if t.get("status") == "done":
#             completed_by_emp.setdefault(name,[]).append(t)
#         else:
#             active_by_emp.setdefault(name,[]).append(t)

#     # Read current tracker to find employee row numbers
#     result = svc.spreadsheets().values().get(
#         spreadsheetId=sid, range="Task Tracker!A:A").execute()
#     existing_rows = [r[0] if r else "" for r in result.get("values",[])]

#     # Build update data for each employee row
#     update_data = []
#     requests    = []
#     tracker_sid = _get_sheet_id(svc, sid, "Task Tracker")

#     for emp in employees:
#         name = emp.get("name","")
#         try:
#             row_idx = existing_rows.index(name)  # 0-based
#         except ValueError:
#             continue

#         active    = active_by_emp.get(name,[])
#         completed = completed_by_emp.get(name,[])
#         total_active    = len(active)
#         total_completed = len(completed)
#         workload_pct    = min(100, total_active * 20)

#         # Fill up to 3 active task slots
#         def task_cols(tasks, slot):
#             if slot < len(tasks):
#                 t = tasks[slot]
#                 return [
#                     _safe_str(t.get("title","")),
#                     _safe_str(t.get("priority","")),
#                     _safe_str(t.get("due_date","TBD")),
#                 ]
#             return ["","",""]

#         row_values = [
#             name,
#             emp.get("role",""),
#             emp.get("band",""),
#             emp.get("level",""),
#             *task_cols(active,0),
#             *task_cols(active,1),
#             *task_cols(active,2),
#             str(total_active),
#             str(total_completed),
#             f"{workload_pct}%",
#             now,
#         ]

#         # Row in sheets is 1-based, +1 for header
#         sheet_row = row_idx + 1
#         update_data.append({
#             "range": f"Task Tracker!A{sheet_row}:Q{sheet_row}",
#             "values": [row_values],
#         })

#         # Color workload cell
#         workload_color = C_HIGH if workload_pct>=80 else C_MEDIUM if workload_pct>=40 else C_LOW
#         requests.append({"repeatCell":{
#             "range":{"sheetId":tracker_sid,
#                      "startRowIndex":row_idx,"endRowIndex":row_idx+1,
#                      "startColumnIndex":15,"endColumnIndex":16},
#             "cell":{"userEnteredFormat":{"backgroundColor":workload_color,
#                     "textFormat":{"bold":True}}},
#             "fields":"userEnteredFormat(backgroundColor,textFormat)",
#         }})

#     if update_data:
#         svc.spreadsheets().values().batchUpdate(
#             spreadsheetId=sid,
#             body={"valueInputOption":"RAW","data":update_data}
#         ).execute()

#     # Append newly completed tasks to Completed Tasks tab
#     newly_done = [t for t in all_tasks if t.get("status")=="done"]
#     if newly_done:
#         # Check existing completed to avoid dupes
#         existing = svc.spreadsheets().values().get(
#             spreadsheetId=sid, range="Completed Tasks!A:A").execute()
#         existing_ids = {r[0] for r in existing.get("values",[])[1:] if r}

#         new_rows = []
#         for t in newly_done:
#             tid = str(t.get("id",""))
#             if tid not in existing_ids:
#                 new_rows.append([
#                     t.get("assignee_name",""),
#                     t.get("role","") if "role" in t else "",
#                     _safe_str(t.get("title","")),
#                     _safe_str(t.get("completed_at",now)),
#                     _safe_str(t.get("meeting_id","")),
#                     _safe_str(t.get("notes","")),
#                 ])
#         if new_rows:
#             svc.spreadsheets().values().append(
#                 spreadsheetId=sid, range="Completed Tasks!A:F",
#                 valueInputOption="RAW", insertDataOption="INSERT_ROWS",
#                 body={"values":new_rows}
#             ).execute()
#             # Grey out completed rows
#             comp_sid = _get_sheet_id(svc, sid, "Completed Tasks")
#             existing_count = len(existing.get("values",[])) 
#             for i in range(len(new_rows)):
#                 requests.append({"repeatCell":{
#                     "range":{"sheetId":comp_sid,
#                              "startRowIndex":existing_count+i,
#                              "endRowIndex":existing_count+i+1,
#                              "startColumnIndex":0,"endColumnIndex":6},
#                     "cell":{"userEnteredFormat":{"backgroundColor":C_DONE}},
#                     "fields":"userEnteredFormat.backgroundColor",
#                 }})

#     if requests:
#         svc.spreadsheets().batchUpdate(spreadsheetId=sid,
#             body={"requests":requests}).execute()

#     return f"https://docs.google.com/spreadsheets/d/{sid}"

# ----------------------------------------------------------------------
# import os
# import json
# from datetime import datetime
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build

# TOKEN_FILE = os.path.join(os.path.dirname(__file__), "../token.json")

# SCOPES = [
#     "https://www.googleapis.com/auth/calendar",
#     "https://www.googleapis.com/auth/tasks",
#     "https://www.googleapis.com/auth/spreadsheets",
#     "https://www.googleapis.com/auth/drive.file",
# ]

# # Color palette (Google Sheets RGB objects)
# COLOR_HEADER     = {"red": 0.13, "green": 0.16, "blue": 0.20}   # dark slate
# COLOR_ACCENT     = {"red": 0.00, "green": 0.89, "blue": 0.63}   # green accent
# COLOR_HIGH       = {"red": 1.00, "green": 0.30, "blue": 0.42}   # red
# COLOR_MEDIUM     = {"red": 1.00, "green": 0.82, "blue": 0.40}   # yellow
# COLOR_LOW        = {"red": 0.60, "green": 0.93, "blue": 0.76}   # light green
# COLOR_DONE       = {"red": 0.80, "green": 0.80, "blue": 0.80}   # grey
# COLOR_WHITE      = {"red": 1.00, "green": 1.00, "blue": 1.00}
# COLOR_LIGHT_BG   = {"red": 0.95, "green": 0.96, "blue": 0.98}


# def _get_creds():
#     with open(TOKEN_FILE) as f:
#         data = json.load(f)
#     return Credentials.from_authorized_user_info(data, SCOPES)

# def _sheets(): return build("sheets", "v4", credentials=_get_creds())
# def _drive():  return build("drive",  "v3", credentials=_get_creds())


# # ── Helpers ───────────────────────────────────────────────────────────────

# def _find_or_create_spreadsheet(sheets_svc, drive_svc, title: str) -> str:
#     q = f"name='{title}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
#     files = drive_svc.files().list(q=q, fields="files(id)").execute().get("files", [])
#     if files:
#         return files[0]["id"]
#     body = {"properties": {"title": title}, "sheets": [
#         {"properties": {"title": "Overview"}},
#         {"properties": {"title": "Tasks"}},
#         {"properties": {"title": "Meetings"}},
#         {"properties": {"title": "Task Tracker"}},
#     ]}
#     created = sheets_svc.spreadsheets().create(body=body).execute()
#     sid = created["spreadsheetId"]
#     _write_master_headers(sheets_svc, sid)
#     return sid


# def _get_sheet_map(sheets_svc, spreadsheet_id: str) -> dict:
#     meta = sheets_svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
#     return {s["properties"]["title"]: s["properties"]["sheetId"]
#             for s in meta.get("sheets", [])}


# def _ensure_tab(sheets_svc, spreadsheet_id: str, title: str, sheet_map: dict) -> int:
#     """Create a tab if it doesn't exist. Returns sheetId."""
#     if title in sheet_map:
#         return sheet_map[title]
#     resp = sheets_svc.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={
#         "requests": [{"addSheet": {"properties": {"title": title}}}]
#     }).execute()
#     return resp["replies"][0]["addSheet"]["properties"]["sheetId"]


# def _header_format(sheet_id: int, num_cols: int, color=None) -> list:
#     bg = color or COLOR_HEADER
#     return [
#         {"repeatCell": {
#             "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
#                       "startColumnIndex": 0, "endColumnIndex": num_cols},
#             "cell": {"userEnteredFormat": {
#                 "backgroundColor": bg,
#                 "textFormat": {"bold": True, "foregroundColor": COLOR_WHITE, "fontSize": 10},
#                 "horizontalAlignment": "CENTER",
#                 "verticalAlignment": "MIDDLE",
#             }},
#             "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
#         }},
#         {"updateSheetProperties": {
#             "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
#             "fields": "gridProperties.frozenRowCount",
#         }},
#     ]


# def _auto_resize(sheet_id: int, num_cols: int) -> dict:
#     return {"autoResizeDimensions": {"dimensions": {
#         "sheetId": sheet_id, "dimension": "COLUMNS",
#         "startIndex": 0, "endIndex": num_cols,
#     }}}


# def _priority_color(priority: str) -> dict:
#     return {
#         "High":   COLOR_HIGH,
#         "Medium": COLOR_MEDIUM,
#         "Low":    COLOR_LOW,
#     }.get(priority, COLOR_WHITE)


# # ── Master spreadsheet (per-project meeting log) ──────────────────────────

# def _write_master_headers(sheets_svc, sid: str):
#     sheet_map = _get_sheet_map(sheets_svc, sid)
#     data = [
#         # Overview tab
#         {"range": "Overview!A1", "values": [[
#             "Meeting ID", "Date Processed", "Meeting Title", "Meeting Date",
#             "Project", "Attendees", "Summary Points", "Key Decisions",
#             "Blockers", "Next Steps", "Action Item Count", "Follow-up Meetings",
#         ]]},
#         # Tasks tab
#         {"range": "Tasks!A1", "values": [[
#             "Meeting ID", "Meeting Title", "Task ID", "Task Title",
#             "Assignee", "Assignee Email", "Companion", "Guide",
#             "Status Checker", "Priority", "Assigned Date", "Due Date",
#             "Total Days", "Notes", "Escalation Details",
#         ]]},
#         # Meetings tab
#         {"range": "Meetings!A1", "values": [[
#             "Meeting ID", "Source Meeting", "Suggested Meeting Title",
#             "Purpose", "Suggested Date", "Duration (mins)",
#             "Recipients", "Agenda Points",
#         ]]},
#     ]
#     sheets_svc.spreadsheets().values().batchUpdate(
#         spreadsheetId=sid,
#         body={"valueInputOption": "RAW", "data": data}
#     ).execute()

#     # Format headers
#     requests = []
#     for tab, n in [("Overview", 12), ("Tasks", 15), ("Meetings", 8)]:
#         requests += _header_format(sheet_map[tab], n)
#     sheets_svc.spreadsheets().batchUpdate(spreadsheetId=sid,
#         body={"requests": requests}).execute()


# def _append_overview(sheets_svc, sid: str, meeting_id: str,
#                      project_name: str, memo: dict, tasks: list, meetings: list):
#     summary_points = memo.get("summary", "")
#     if isinstance(summary_points, list):
#         summary_points = "\n• " + "\n• ".join(summary_points)

#     row = [[
#         meeting_id,
#         datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
#         memo.get("title", ""),
#         memo.get("date", ""),
#         project_name,
#         ", ".join(memo.get("attendees", [])),
#         summary_points,
#         "\n• " + "\n• ".join(memo.get("decisions", [])) if memo.get("decisions") else "",
#         "\n• " + "\n• ".join(memo.get("blockers", [])) if memo.get("blockers") else "",
#         "\n• " + "\n• ".join(memo.get("next_steps", [])) if memo.get("next_steps") else "",
#         str(len(tasks)),
#         str(len(meetings)),
#     ]]
#     sheets_svc.spreadsheets().values().append(
#         spreadsheetId=sid, range="Overview!A:L",
#         valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": row}
#     ).execute()


# def _append_tasks(sheets_svc, sid: str, sheet_map: dict,
#                   meeting_id: str, memo: dict, tasks: list):
#     if not tasks:
#         return
#     rows = []
#     for t in tasks:
#         rows.append([
#             meeting_id, memo.get("title", ""),
#             t.get("id", ""), t.get("title", ""),
#             t.get("assignee", ""), t.get("assignee_email", ""),
#             t.get("companion", ""), t.get("guide", ""),
#             t.get("checker", "Manager"),
#             t.get("priority", "Medium"),
#             t.get("assigned_date", str(datetime.utcnow().date())),
#             t.get("due_date", "TBD"),
#             str(t.get("total_days", "")),
#             t.get("notes", ""),
#             t.get("escalation_details", ""),
#         ])
#     sheets_svc.spreadsheets().values().append(
#         spreadsheetId=sid, range="Tasks!A:O",
#         valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": rows}
#     ).execute()

#     # Color-code priority column (col J = index 9)
#     task_sheet_id = sheet_map.get("Tasks")
#     if not task_sheet_id:
#         return
#     # Get current row count to know where new rows start
#     result = sheets_svc.spreadsheets().values().get(
#         spreadsheetId=sid, range="Tasks!A:A").execute()
#     start_row = len(result.get("values", [])) - len(rows)

#     requests = []
#     for i, t in enumerate(tasks):
#         color = _priority_color(t.get("priority", "Medium"))
#         requests.append({"repeatCell": {
#             "range": {"sheetId": task_sheet_id,
#                       "startRowIndex": start_row + i,
#                       "endRowIndex":   start_row + i + 1,
#                       "startColumnIndex": 9, "endColumnIndex": 10},
#             "cell": {"userEnteredFormat": {"backgroundColor": color,
#                      "textFormat": {"bold": True}}},
#             "fields": "userEnteredFormat(backgroundColor,textFormat)",
#         }})
#         # Alternate row background
#         bg = COLOR_LIGHT_BG if i % 2 == 0 else COLOR_WHITE
#         requests.append({"repeatCell": {
#             "range": {"sheetId": task_sheet_id,
#                       "startRowIndex": start_row + i,
#                       "endRowIndex":   start_row + i + 1,
#                       "startColumnIndex": 0, "endColumnIndex": 9},
#             "cell": {"userEnteredFormat": {"backgroundColor": bg}},
#             "fields": "userEnteredFormat.backgroundColor",
#         }})
#     if requests:
#         sheets_svc.spreadsheets().batchUpdate(
#             spreadsheetId=sid, body={"requests": requests}).execute()


# def _append_meetings(sheets_svc, sid: str, meeting_id: str, memo: dict, meetings: list):
#     if not meetings:
#         return
#     rows = []
#     for m in meetings:
#         agenda = m.get("agenda", "")
#         if isinstance(agenda, list):
#             agenda = "; ".join(agenda)
#         rows.append([
#             meeting_id, memo.get("title", ""),
#             m.get("title", ""), m.get("purpose", ""),
#             m.get("suggested_date", "TBD"),
#             str(m.get("duration_mins", 30)),
#             ", ".join(m.get("recipients", [])),
#             agenda,
#         ])
#     sheets_svc.spreadsheets().values().append(
#         spreadsheetId=sid, range="Meetings!A:H",
#         valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": rows}
#     ).execute()


# # ── Task Tracker sheet (one per project, always updated) ──────────────────

# def _get_or_create_tracker(sheets_svc, drive_svc, project_name: str) -> str:
#     title = f"Task Tracker — {project_name}"
#     q = f"name='{title}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
#     files = drive_svc.files().list(q=q, fields="files(id)").execute().get("files", [])
#     if files:
#         return files[0]["id"]
#     body = {"properties": {"title": title}, "sheets": [
#         {"properties": {"title": "Active Tasks"}},
#         {"properties": {"title": "Completed Tasks"}},
#         {"properties": {"title": "Team Overview"}},
#     ]}
#     created = sheets_svc.spreadsheets().create(body=body).execute()
#     sid = created["spreadsheetId"]
#     _write_tracker_headers(sheets_svc, sid)
#     return sid


# def _write_tracker_headers(sheets_svc, sid: str):
#     sheet_map = _get_sheet_map(sheets_svc, sid)
#     TASK_COLS = [
#         "Task ID", "Task Title", "Assignee", "Companion", "Guide",
#         "Status Checker", "Priority", "Assigned Date", "Due Date",
#         "Total Days", "Status", "Notes", "Meeting ID",
#     ]
#     TEAM_COLS = [
#         "Employee", "Role", "Band", "Level",
#         "Active Tasks", "Completed Tasks", "Workload %",
#     ]
#     data = [
#         {"range": "Active Tasks!A1",    "values": [TASK_COLS]},
#         {"range": "Completed Tasks!A1", "values": [TASK_COLS]},
#         {"range": "Team Overview!A1",   "values": [TEAM_COLS]},
#     ]
#     sheets_svc.spreadsheets().values().batchUpdate(
#         spreadsheetId=sid,
#         body={"valueInputOption": "RAW", "data": data}
#     ).execute()

#     requests = []
#     for tab, n in [("Active Tasks", 13), ("Completed Tasks", 13), ("Team Overview", 7)]:
#         requests += _header_format(sheet_map[tab], n, COLOR_HEADER)
#     sheets_svc.spreadsheets().batchUpdate(spreadsheetId=sid,
#         body={"requests": requests}).execute()


# def update_task_tracker(project_name: str, all_tasks: list, employees: list) -> str:
#     """
#     Fully rewrites the Task Tracker sheet for a project.
#     all_tasks: list of task dicts from DB (with assignee_name etc.)
#     employees: list of employee dicts from DB
#     """
#     sheets_svc = _sheets()
#     drive_svc  = _drive()
#     sid = _get_or_create_tracker(sheets_svc, drive_svc, project_name)
#     sheet_map = _get_sheet_map(sheets_svc, sid)

#     active    = [t for t in all_tasks if t.get("status") != "done"]
#     completed = [t for t in all_tasks if t.get("status") == "done"]

#     def task_row(t):
#         return [
#             str(t.get("id", "")),
#             t.get("title", ""),
#             t.get("assignee_name", ""),
#             t.get("companion_name", "") or "",
#             t.get("guide_name", "") or "",
#             t.get("checker_name", "") or "Manager",
#             t.get("priority", ""),
#             str(t.get("assigned_date", "")) if t.get("assigned_date") else "",
#             str(t.get("due_date", "")) if t.get("due_date") else "TBD",
#             str(t.get("total_days", "")) if t.get("total_days") else "",
#             t.get("status", "pending"),
#             t.get("notes", "") or "",
#             t.get("meeting_id", "") or "",
#         ]

#     # Clear existing data (keep headers)
#     for tab in ["Active Tasks", "Completed Tasks", "Team Overview"]:
#         sheets_svc.spreadsheets().values().clear(
#             spreadsheetId=sid, range=f"{tab}!A2:Z"
#         ).execute()

#     # Write active tasks
#     if active:
#         sheets_svc.spreadsheets().values().update(
#             spreadsheetId=sid, range="Active Tasks!A2",
#             valueInputOption="RAW", body={"values": [task_row(t) for t in active]}
#         ).execute()

#     # Write completed tasks
#     if completed:
#         sheets_svc.spreadsheets().values().update(
#             spreadsheetId=sid, range="Completed Tasks!A2",
#             valueInputOption="RAW", body={"values": [task_row(t) for t in completed]}
#         ).execute()

#     # Write team overview
#     if employees:
#         active_by_emp    = {}
#         completed_by_emp = {}
#         for t in all_tasks:
#             name = t.get("assignee_name", "")
#             if t.get("status") == "done":
#                 completed_by_emp[name] = completed_by_emp.get(name, 0) + 1
#             else:
#                 active_by_emp[name] = active_by_emp.get(name, 0) + 1

#         team_rows = []
#         for e in employees:
#             name = e.get("name", "")
#             act  = active_by_emp.get(name, 0)
#             comp = completed_by_emp.get(name, 0)
#             team_rows.append([
#                 name,
#                 e.get("role", ""),
#                 e.get("band", ""),
#                 e.get("level", ""),
#                 str(act),
#                 str(comp),
#                 f"{min(100, act * 20)}%",
#             ])
#         sheets_svc.spreadsheets().values().update(
#             spreadsheetId=sid, range="Team Overview!A2",
#             valueInputOption="RAW", body={"values": team_rows}
#         ).execute()

#     # Color-code priority on Active Tasks
#     requests = []
#     active_sid = sheet_map.get("Active Tasks")
#     if active_sid and active:
#         for i, t in enumerate(active):
#             color = _priority_color(t.get("priority", "Medium"))
#             requests.append({"repeatCell": {
#                 "range": {"sheetId": active_sid,
#                           "startRowIndex": i + 1, "endRowIndex": i + 2,
#                           "startColumnIndex": 6, "endColumnIndex": 7},
#                 "cell": {"userEnteredFormat": {"backgroundColor": color,
#                          "textFormat": {"bold": True}}},
#                 "fields": "userEnteredFormat(backgroundColor,textFormat)",
#             }})

#     # Color completed tasks grey
#     comp_sid = sheet_map.get("Completed Tasks")
#     if comp_sid and completed:
#         requests.append({"repeatCell": {
#             "range": {"sheetId": comp_sid,
#                       "startRowIndex": 1, "endRowIndex": len(completed) + 1,
#                       "startColumnIndex": 0, "endColumnIndex": 13},
#             "cell": {"userEnteredFormat": {"backgroundColor": COLOR_DONE}},
#             "fields": "userEnteredFormat.backgroundColor",
#         }})

#     # Auto-resize all tabs
#     for tab_name, n in [("Active Tasks", 13), ("Completed Tasks", 13), ("Team Overview", 7)]:
#         requests.append(_auto_resize(sheet_map[tab_name], n))

#     if requests:
#         sheets_svc.spreadsheets().batchUpdate(
#             spreadsheetId=sid, body={"requests": requests}).execute()

#     return f"https://docs.google.com/spreadsheets/d/{sid}"


# # ── Main entry point ──────────────────────────────────────────────────────

# def update_sheet(meeting_id: str, project_name: str,
#                  memo: dict, tasks: list, meetings: list) -> str:
#     """
#     Updates the project's meeting log spreadsheet.
#     Returns the spreadsheet URL.
#     """
#     sheets_svc = _sheets()
#     drive_svc  = _drive()

#     title = f"Meeting Log — {project_name}"
#     sid   = _find_or_create_spreadsheet(sheets_svc, drive_svc, title)
#     sheet_map = _get_sheet_map(sheets_svc, sid)

#     _append_overview(sheets_svc, sid, meeting_id, project_name, memo, tasks, meetings)
#     _append_tasks(sheets_svc, sid, sheet_map, meeting_id, memo, tasks)
#     _append_meetings(sheets_svc, sid, meeting_id, memo, meetings)

#     # Auto-resize all tabs
#     requests = []
#     for tab, n in [("Overview", 12), ("Tasks", 15), ("Meetings", 8)]:
#         if tab in sheet_map:
#             requests.append(_auto_resize(sheet_map[tab], n))
#     if requests:
#         sheets_svc.spreadsheets().batchUpdate(
#             spreadsheetId=sid, body={"requests": requests}).execute()

#     return f"https://docs.google.com/spreadsheets/d/{sid}"

# --------------------------------------------------------

# import os
# import json
# from datetime import datetime
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build

# TOKEN_FILE = os.path.join(os.path.dirname(__file__), "../token.json")

# SCOPES = [
#     "https://www.googleapis.com/auth/calendar",
#     "https://www.googleapis.com/auth/tasks",
#     "https://www.googleapis.com/auth/spreadsheets",
#     "https://www.googleapis.com/auth/drive.file",
# ]

# # Name of the master spreadsheet (one sheet for all meetings)
# SPREADSHEET_NAME = "Meeting Intelligence Log"


# def _get_credentials() -> Credentials:
#     if not os.path.exists(TOKEN_FILE):
#         raise FileNotFoundError("token.json not found. Run generate_token.py first.")
#     with open(TOKEN_FILE, "r") as f:
#         token_data = json.load(f)
#     return Credentials.from_authorized_user_info(token_data, SCOPES)


# def _get_sheets_service():
#     return build("sheets", "v4", credentials=_get_credentials())


# def _get_drive_service():
#     return build("drive", "v3", credentials=_get_credentials())


# def _get_or_create_spreadsheet(sheets_svc, drive_svc) -> str:
#     """
#     Looks for an existing spreadsheet named SPREADSHEET_NAME in Drive.
#     Creates one if not found. Returns the spreadsheet ID.
#     """
#     # Search Drive for existing sheet
#     query = f"name='{SPREADSHEET_NAME}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
#     results = drive_svc.files().list(q=query, fields="files(id, name)").execute()
#     files = results.get("files", [])

#     if files:
#         return files[0]["id"]

#     # Create new spreadsheet with 3 tabs
#     spreadsheet_body = {
#         "properties": {"title": SPREADSHEET_NAME},
#         "sheets": [
#             {"properties": {"title": "Memos"}},
#             {"properties": {"title": "Tasks"}},
#             {"properties": {"title": "Meetings"}},
#         ],
#     }
#     created = sheets_svc.spreadsheets().create(body=spreadsheet_body).execute()
#     spreadsheet_id = created["spreadsheetId"]

#     # Write headers to each tab
#     _write_headers(sheets_svc, spreadsheet_id)

#     return spreadsheet_id


# def _write_headers(sheets_svc, spreadsheet_id: str):
#     """Write column headers to each tab."""
#     memo_headers = [[
#         "Meeting ID", "Date Processed", "Meeting Title", "Meeting Date",
#         "Attendees", "Summary", "Decisions", "Blockers", "Next Steps"
#     ]]
#     task_headers = [[
#         "Meeting ID", "Meeting Title", "Task ID", "Task Title",
#         "Assignee", "Due Date", "Priority", "Notes"
#     ]]
#     meeting_headers = [[
#         "Meeting ID", "Source Meeting Title", "Suggested Meeting Title",
#         "Purpose", "Suggested Date", "Duration (mins)", "Recipients", "Agenda"
#     ]]

#     body = {"valueInputOption": "RAW", "data": [
#         {"range": "Memos!A1",    "values": memo_headers},
#         {"range": "Tasks!A1",    "values": task_headers},
#         {"range": "Meetings!A1", "values": meeting_headers},
#     ]}
#     sheets_svc.spreadsheets().values().batchUpdate(
#         spreadsheetId=spreadsheet_id, body=body
#     ).execute()

#     # Bold + freeze header rows
#     requests = []
#     sheet_ids = _get_sheet_ids(sheets_svc, spreadsheet_id)

#     for sheet_name, sheet_id in sheet_ids.items():
#         requests.append({
#             "repeatCell": {
#                 "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
#                 "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
#                 "fields": "userEnteredFormat.textFormat.bold",
#             }
#         })
#         requests.append({
#             "updateSheetProperties": {
#                 "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
#                 "fields": "gridProperties.frozenRowCount",
#             }
#         })

#     sheets_svc.spreadsheets().batchUpdate(
#         spreadsheetId=spreadsheet_id,
#         body={"requests": requests}
#     ).execute()


# def _get_sheet_ids(sheets_svc, spreadsheet_id: str) -> dict:
#     """Returns a dict of {sheet_name: sheet_id}."""
#     meta = sheets_svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
#     return {
#         s["properties"]["title"]: s["properties"]["sheetId"]
#         for s in meta.get("sheets", [])
#     }


# def update_sheet(meeting_id: str, memo: dict, tasks: list, meetings: list) -> str:
#     """
#     Appends this meeting's data to the master Google Sheet.
#     Returns the spreadsheet URL.
#     """
#     sheets_svc = _get_sheets_service()
#     drive_svc = _get_drive_service()

#     spreadsheet_id = _get_or_create_spreadsheet(sheets_svc, drive_svc)
#     processed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

#     # ── Memo row ──────────────────────────────────────────────────────────────
#     memo_row = [[
#         meeting_id,
#         processed_at,
#         memo.get("title", ""),
#         memo.get("date", ""),
#         ", ".join(memo.get("attendees", [])),
#         memo.get("summary", ""),
#         " | ".join(memo.get("decisions", [])),
#         " | ".join(memo.get("blockers", [])),
#         " | ".join(memo.get("next_steps", [])),
#     ]]

#     # ── Task rows ─────────────────────────────────────────────────────────────
#     task_rows = []
#     for task in tasks:
#         task_rows.append([
#             meeting_id,
#             memo.get("title", ""),
#             task.get("id", ""),
#             task.get("title", ""),
#             task.get("assignee", ""),
#             task.get("due_date", ""),
#             task.get("priority", ""),
#             task.get("notes", ""),
#         ])
#     if not task_rows:
#         task_rows = [[meeting_id, memo.get("title", ""), "", "No tasks", "", "", "", ""]]

#     # ── Meeting rows ──────────────────────────────────────────────────────────
#     meeting_rows = []
#     for mtg in meetings:
#         meeting_rows.append([
#             meeting_id,
#             memo.get("title", ""),
#             mtg.get("title", ""),
#             mtg.get("purpose", ""),
#             mtg.get("suggested_date", ""),
#             str(mtg.get("duration_mins", 30)),
#             ", ".join(mtg.get("recipients", [])),
#             mtg.get("agenda", ""),
#         ])
#     if not meeting_rows:
#         meeting_rows = [[meeting_id, memo.get("title", ""), "No follow-up meetings", "", "", "", "", ""]]

#     # ── Append all rows ───────────────────────────────────────────────────────
#     append_data = [
#         {"range": "Memos!A:I",    "values": memo_row},
#         {"range": "Tasks!A:H",    "values": task_rows},
#         {"range": "Meetings!A:H", "values": meeting_rows},
#     ]

#     sheets_svc.spreadsheets().values().batchUpdate(
#         spreadsheetId=spreadsheet_id,
#         body={"valueInputOption": "RAW", "data": append_data}
#     ).execute()

#     # Auto-resize columns for readability
#     _auto_resize(sheets_svc, spreadsheet_id)

#     return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


# def _auto_resize(sheets_svc, spreadsheet_id: str):
#     """Auto-resize all columns in all sheets."""
#     sheet_ids = _get_sheet_ids(sheets_svc, spreadsheet_id)
#     requests = [
#         {
#             "autoResizeDimensions": {
#                 "dimensions": {
#                     "sheetId": sid,
#                     "dimension": "COLUMNS",
#                     "startIndex": 0,
#                     "endIndex": 10,
#                 }
#             }
#         }
#         for sid in sheet_ids.values()
#     ]
#     sheets_svc.spreadsheets().batchUpdate(
#         spreadsheetId=spreadsheet_id,
#         body={"requests": requests}
#     ).execute()