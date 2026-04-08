"""
Run ONCE to create all static sheets for all projects.
Prints Sheet IDs to paste into .env

Usage: python setup_sheets.py
"""
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE = "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

PROJECTS = [
    {"key": "RAG",      "name": "Enterprise RAG"},
    {"key": "PLIPKARY", "name": "Plipkary"},
]

EMPLOYEES = {
    "Enterprise RAG": ["Arjun","Sneha","Karthik","Divya","Rahul","Meena"],
    "Plipkary":       ["Vikram","Priya","Arun","Nithya","Suresh","Lakshmi"],
}

# Colors
C_DARK    = {"red":0.13,"green":0.16,"blue":0.20}
C_GREEN   = {"red":0.00,"green":0.74,"blue":0.53}
C_WHITE   = {"red":1.00,"green":1.00,"blue":1.00}
C_LIGHT   = {"red":0.95,"green":0.97,"blue":0.99}
C_YELLOW  = {"red":1.00,"green":0.95,"blue":0.80}
C_RED     = {"red":1.00,"green":0.90,"blue":0.90}

def get_services():
    with open(TOKEN_FILE) as f:
        data = json.load(f)
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    return build("sheets","v4",credentials=creds), build("drive","v3",credentials=creds)

def header_req(sheet_id, num_cols, bg=None):
    return [
        {"repeatCell":{
            "range":{"sheetId":sheet_id,"startRowIndex":0,"endRowIndex":1,
                     "startColumnIndex":0,"endColumnIndex":num_cols},
            "cell":{"userEnteredFormat":{
                "backgroundColor": bg or C_DARK,
                "textFormat":{"bold":True,"foregroundColor":C_WHITE,"fontSize":10},
                "horizontalAlignment":"CENTER","verticalAlignment":"MIDDLE",
                "wrapStrategy":"WRAP",
            }},
            "fields":"userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }},
        {"updateSheetProperties":{
            "properties":{"sheetId":sheet_id,"gridProperties":{"frozenRowCount":1}},
            "fields":"gridProperties.frozenRowCount",
        }},
        {"updateDimensionProperties":{
            "range":{"sheetId":sheet_id,"dimension":"ROWS","startIndex":0,"endIndex":1},
            "properties":{"pixelSize":36},
            "fields":"pixelSize",
        }},
    ]

def auto_resize(sheet_id, num_cols):
    return {"autoResizeDimensions":{"dimensions":{
        "sheetId":sheet_id,"dimension":"COLUMNS",
        "startIndex":0,"endIndex":num_cols,
    }}}

def create_meeting_log(sheets, project_name):
    """Creates Meeting Log sheet with Overview, Tasks, Meetings tabs."""
    body = {
        "properties":{"title":f"Meeting Log — {project_name}"},
        "sheets":[
            {"properties":{"title":"Overview","sheetId":1000}},
            {"properties":{"title":"Tasks","sheetId":1001}},
            {"properties":{"title":"Meetings","sheetId":1002}},
        ]
    }
    ss = sheets.spreadsheets().create(body=body).execute()
    sid = ss["spreadsheetId"]
    sheet_map = {s["properties"]["title"]:s["properties"]["sheetId"]
                 for s in ss["sheets"]}

    # Write headers
    OVERVIEW_HEADERS = [[
        "Meeting ID","Date Processed","Meeting Title","Meeting Date",
        "Project","Attendees","Summary Points","Key Decisions",
        "Blockers","Risks","Next Steps","Manager Actions",
        "Open Questions","Highlights","Follow-up Required","Task Count","Meeting Count"
    ]]
    TASK_HEADERS = [[
        "Meeting ID","Meeting Title","Task ID","Task Title","Description",
        "Assignee","Assignee Email","Companion","Guide","Status Checker",
        "Priority","Assigned Date","Due Date","Total Days",
        "Skill Match","Notes","Escalation Details","Status"
    ]]
    MTG_HEADERS = [[
        "Meeting ID","Source Meeting","Suggested Title","Purpose",
        "Suggested Date","Duration (mins)","Recipients","Agenda"
    ]]

    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=sid,
        body={"valueInputOption":"RAW","data":[
            {"range":"Overview!A1","values":OVERVIEW_HEADERS},
            {"range":"Tasks!A1",   "values":TASK_HEADERS},
            {"range":"Meetings!A1","values":MTG_HEADERS},
        ]}
    ).execute()

    # Format headers + freeze + auto-resize
    requests = []
    for tab, n in [("Overview",17),("Tasks",18),("Meetings",8)]:
        requests += header_req(sheet_map[tab], n)
    for tab, n in [("Overview",17),("Tasks",18),("Meetings",8)]:
        requests.append(auto_resize(sheet_map[tab], n))

    sheets.spreadsheets().batchUpdate(spreadsheetId=sid,
        body={"requests":requests}).execute()

    print(f"  ✅ Meeting Log created: {sid}")
    return sid


def create_task_tracker(sheets, project_name, employees):
    """Creates Task Tracker sheet — one row per employee, updates in place."""
    body = {
        "properties":{"title":f"Task Tracker — {project_name}"},
        "sheets":[
            {"properties":{"title":"Task Tracker","sheetId":2000}},
            {"properties":{"title":"Completed Tasks","sheetId":2001}},
        ]
    }
    ss = sheets.spreadsheets().create(body=body).execute()
    sid = ss["spreadsheetId"]
    sheet_map = {s["properties"]["title"]:s["properties"]["sheetId"]
                 for s in ss["sheets"]}

    TRACKER_HEADERS = [[
        "Employee","Role","Band","Level",
        "Active Task 1","Priority 1","Due Date 1",
        "Active Task 2","Priority 2","Due Date 2",
        "Active Task 3","Priority 3","Due Date 3",
        "Total Active","Total Completed","Workload %","Last Updated"
    ]]
    COMPLETED_HEADERS = [[
        "Employee","Role","Task Title","Completed Date","Meeting ID","Notes"
    ]]

    # Seed employee rows
    emp_rows = [[e,"","","","","","","","","","","","",0,0,"0%",""] for e in employees]

    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=sid,
        body={"valueInputOption":"RAW","data":[
            {"range":"Task Tracker!A1",    "values":TRACKER_HEADERS},
            {"range":"Task Tracker!A2",    "values":emp_rows},
            {"range":"Completed Tasks!A1", "values":COMPLETED_HEADERS},
        ]}
    ).execute()

    # Format headers
    requests = []
    requests += header_req(sheet_map["Task Tracker"],   17, C_GREEN)
    requests += header_req(sheet_map["Completed Tasks"], 6, C_GREEN)
    requests.append(auto_resize(sheet_map["Task Tracker"],   17))
    requests.append(auto_resize(sheet_map["Completed Tasks"], 6))

    # Alternate row colors for employee rows
    for i, _ in enumerate(employees):
        bg = C_LIGHT if i % 2 == 0 else C_WHITE
        requests.append({"repeatCell":{
            "range":{"sheetId":sheet_map["Task Tracker"],
                     "startRowIndex":i+1,"endRowIndex":i+2,
                     "startColumnIndex":0,"endColumnIndex":17},
            "cell":{"userEnteredFormat":{"backgroundColor":bg}},
            "fields":"userEnteredFormat.backgroundColor",
        }})

    sheets.spreadsheets().batchUpdate(spreadsheetId=sid,
        body={"requests":requests}).execute()

    print(f"  ✅ Task Tracker created: {sid}")
    return sid


def main():
    print("Setting up static sheets for all projects...\n")
    sheets, drive = get_services()

    env_lines = ["\n# ── Google Sheet IDs (generated by setup_sheets.py) ──"]

    for p in PROJECTS:
        print(f"📁 {p['name']}")
        log_id     = create_meeting_log(sheets, p["name"])
        tracker_id = create_task_tracker(sheets, p["name"], EMPLOYEES[p["name"]])

        env_lines.append(f"SHEET_LOG_{p['key']}={log_id}")
        env_lines.append(f"SHEET_TRACKER_{p['key']}={tracker_id}")
        print()

    print("\n" + "="*60)
    print("Add these to your backend/.env file:")
    print("="*60)
    for line in env_lines:
        print(line)
    print("="*60)
    print("\n✅ Setup complete! Sheets are ready.")

if __name__ == "__main__":
    main()