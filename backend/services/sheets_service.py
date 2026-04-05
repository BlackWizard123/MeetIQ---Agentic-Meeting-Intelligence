import os
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "../token.json")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Name of the master spreadsheet (one sheet for all meetings)
SPREADSHEET_NAME = "Meeting Intelligence Log"


def _get_credentials() -> Credentials:
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("token.json not found. Run generate_token.py first.")
    with open(TOKEN_FILE, "r") as f:
        token_data = json.load(f)
    return Credentials.from_authorized_user_info(token_data, SCOPES)


def _get_sheets_service():
    return build("sheets", "v4", credentials=_get_credentials())


def _get_drive_service():
    return build("drive", "v3", credentials=_get_credentials())


def _get_or_create_spreadsheet(sheets_svc, drive_svc) -> str:
    """
    Looks for an existing spreadsheet named SPREADSHEET_NAME in Drive.
    Creates one if not found. Returns the spreadsheet ID.
    """
    # Search Drive for existing sheet
    query = f"name='{SPREADSHEET_NAME}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = drive_svc.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # Create new spreadsheet with 3 tabs
    spreadsheet_body = {
        "properties": {"title": SPREADSHEET_NAME},
        "sheets": [
            {"properties": {"title": "Memos"}},
            {"properties": {"title": "Tasks"}},
            {"properties": {"title": "Meetings"}},
        ],
    }
    created = sheets_svc.spreadsheets().create(body=spreadsheet_body).execute()
    spreadsheet_id = created["spreadsheetId"]

    # Write headers to each tab
    _write_headers(sheets_svc, spreadsheet_id)

    return spreadsheet_id


def _write_headers(sheets_svc, spreadsheet_id: str):
    """Write column headers to each tab."""
    memo_headers = [[
        "Meeting ID", "Date Processed", "Meeting Title", "Meeting Date",
        "Attendees", "Summary", "Decisions", "Blockers", "Next Steps"
    ]]
    task_headers = [[
        "Meeting ID", "Meeting Title", "Task ID", "Task Title",
        "Assignee", "Due Date", "Priority", "Notes"
    ]]
    meeting_headers = [[
        "Meeting ID", "Source Meeting Title", "Suggested Meeting Title",
        "Purpose", "Suggested Date", "Duration (mins)", "Recipients", "Agenda"
    ]]

    body = {"valueInputOption": "RAW", "data": [
        {"range": "Memos!A1",    "values": memo_headers},
        {"range": "Tasks!A1",    "values": task_headers},
        {"range": "Meetings!A1", "values": meeting_headers},
    ]}
    sheets_svc.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body
    ).execute()

    # Bold + freeze header rows
    requests = []
    sheet_ids = _get_sheet_ids(sheets_svc, spreadsheet_id)

    for sheet_name, sheet_id in sheet_ids.items():
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        })
        requests.append({
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        })

    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()


def _get_sheet_ids(sheets_svc, spreadsheet_id: str) -> dict:
    """Returns a dict of {sheet_name: sheet_id}."""
    meta = sheets_svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {
        s["properties"]["title"]: s["properties"]["sheetId"]
        for s in meta.get("sheets", [])
    }


def update_sheet(meeting_id: str, memo: dict, tasks: list, meetings: list) -> str:
    """
    Appends this meeting's data to the master Google Sheet.
    Returns the spreadsheet URL.
    """
    sheets_svc = _get_sheets_service()
    drive_svc = _get_drive_service()

    spreadsheet_id = _get_or_create_spreadsheet(sheets_svc, drive_svc)
    processed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── Memo row ──────────────────────────────────────────────────────────────
    memo_row = [[
        meeting_id,
        processed_at,
        memo.get("title", ""),
        memo.get("date", ""),
        ", ".join(memo.get("attendees", [])),
        memo.get("summary", ""),
        " | ".join(memo.get("decisions", [])),
        " | ".join(memo.get("blockers", [])),
        " | ".join(memo.get("next_steps", [])),
    ]]

    # ── Task rows ─────────────────────────────────────────────────────────────
    task_rows = []
    for task in tasks:
        task_rows.append([
            meeting_id,
            memo.get("title", ""),
            task.get("id", ""),
            task.get("title", ""),
            task.get("assignee", ""),
            task.get("due_date", ""),
            task.get("priority", ""),
            task.get("notes", ""),
        ])
    if not task_rows:
        task_rows = [[meeting_id, memo.get("title", ""), "", "No tasks", "", "", "", ""]]

    # ── Meeting rows ──────────────────────────────────────────────────────────
    meeting_rows = []
    for mtg in meetings:
        meeting_rows.append([
            meeting_id,
            memo.get("title", ""),
            mtg.get("title", ""),
            mtg.get("purpose", ""),
            mtg.get("suggested_date", ""),
            str(mtg.get("duration_mins", 30)),
            ", ".join(mtg.get("recipients", [])),
            mtg.get("agenda", ""),
        ])
    if not meeting_rows:
        meeting_rows = [[meeting_id, memo.get("title", ""), "No follow-up meetings", "", "", "", "", ""]]

    # ── Append all rows ───────────────────────────────────────────────────────
    append_data = [
        {"range": "Memos!A:I",    "values": memo_row},
        {"range": "Tasks!A:H",    "values": task_rows},
        {"range": "Meetings!A:H", "values": meeting_rows},
    ]

    sheets_svc.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": append_data}
    ).execute()

    # Auto-resize columns for readability
    _auto_resize(sheets_svc, spreadsheet_id)

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


def _auto_resize(sheets_svc, spreadsheet_id: str):
    """Auto-resize all columns in all sheets."""
    sheet_ids = _get_sheet_ids(sheets_svc, spreadsheet_id)
    requests = [
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sid,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 10,
                }
            }
        }
        for sid in sheet_ids.values()
    ]
    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()