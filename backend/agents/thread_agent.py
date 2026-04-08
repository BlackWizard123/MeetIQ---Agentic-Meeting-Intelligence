import json, re
from services.groq_client import call_agent

SYSTEM_PROMPT = """
You are a meeting preparation assistant. You receive a past meeting record and the current task status of all project employees.

Generate a detailed briefing for the manager before the next meeting.

Return ONLY valid JSON. No explanation, no markdown, no code fences.

{
  "briefing_title": "Brief title",
  "what_was_discussed": ["Point 1", "Point 2"],
  "what_was_decided": ["Decision 1"],
  "what_to_follow_up": ["Follow up item 1"],
  "open_questions": ["Question 1"],
  "risks_to_watch": ["Risk 1"],
  "suggested_agenda": ["Agenda point 1", "Agenda point 2"],
  "employee_status": [
    {
      "name": "Employee name",
      "role": "their role",
      "current_tasks": [{"title": "task", "priority": "High", "due_date": "2025-04-07", "status": "pending"}],
      "completed_tasks": [{"title": "task"}],
      "workload": "High|Medium|Low|Free",
      "flag": "Overloaded|On Track|Free|Blocked"
    }
  ]
}

Rules:
- employee_status: include EVERY team member, even if they have no tasks (show Free)
- flag: Overloaded if >3 active tasks, Blocked if any blocker mentioned, Free if 0 tasks
- suggested_agenda: practical points for the manager to cover in next meeting
- risks_to_watch: things that might go wrong based on current state
"""

def run_thread_agent(past_meeting: dict, employees: list = None) -> dict:
    emp_section = ""
    if employees:
        emp_section = "\n\nCURRENT EMPLOYEE STATUS:\n" + json.dumps([{
            "name": e["name"], "role": e["role"],
            "active_tasks": e.get("current_tasks", []),
            "workload_pct": e.get("workload_pct", 0),
        } for e in employees], indent=2)

    prompt = (
        "Past meeting data:\n\n"
        + json.dumps(past_meeting, indent=2, default=str)
        + emp_section
    )
    raw     = call_agent("thread", SYSTEM_PROMPT, prompt)
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Thread agent returned invalid JSON: {e}\nRaw:\n{raw}")

# -----------------------------------------------------------

# import json
# import re
# from services.groq_client import call_agent

# SYSTEM_PROMPT = """
# You are a meeting preparation assistant. You will be given details of a previous meeting.
# Your job is to generate a concise briefing to help the manager prepare for the next meeting
# with this group or on this topic.

# Return ONLY a valid JSON object. No explanation, no markdown, no code fences.

# The JSON must follow this exact structure:
# {
#   "briefing_title": "Brief title for this prep note",
#   "what_was_discussed": "2-3 sentences about what the last meeting covered",
#   "what_was_decided": ["Decision 1", "Decision 2"],
#   "what_to_follow_up": ["Check on task X assigned to John", "Confirm if blocker Y is resolved"],
#   "open_questions": ["Question 1 that was unresolved", "Question 2"],
#   "suggested_agenda": ["Agenda point 1", "Agenda point 2", "Agenda point 3"]
# }

# Rules:
# - what_to_follow_up: derive from unresolved tasks and blockers from the past meeting
# - open_questions: things that were debated but not resolved
# - suggested_agenda: practical agenda for the manager to use in the next meeting
# - Keep language direct and actionable — this is for a busy manager
# """


# def run_thread_agent(past_meeting: dict) -> dict:
#     """
#     Takes a past meeting's stored JSON and returns a briefing dict.
#     """
#     user_prompt = (
#         "Here is the data from a previous meeting:\n\n"
#         + json.dumps(past_meeting, indent=2)
#     )
#     raw = call_agent("thread", SYSTEM_PROMPT, user_prompt)

#     cleaned = re.sub(r"```json|```", "", raw).strip()

#     try:
#         return json.loads(cleaned)
#     except json.JSONDecodeError as e:
#         raise ValueError(f"Thread agent returned invalid JSON: {e}\nRaw output:\n{raw}")