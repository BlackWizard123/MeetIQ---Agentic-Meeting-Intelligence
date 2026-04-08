import json, re, uuid
from services.groq_client import call_agent

SYSTEM_PROMPT = """
You are a task extraction and smart assignment specialist.

You will receive a transcript AND a list of project employees with their skills, level, band, and current workload.

Your job:
1. Extract every action item from the transcript
2. Suggest the best assignee based on skills mentioned in the task
3. Suggest a GUIDE if the assignee's skills don't fully match the task (pick someone senior with matching skills)
4. Suggest a COMPANION if the task is complex and needs peer support (same or similar level)
5. Leave companion empty if the task is simple

Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

Each task:
{
  "id": "t1",
  "title": "Clear specific task title",
  "description": "What exactly needs to be done",
  "assignee": "Name from employee list or Unassigned",
  "assignee_email": "their email or empty",
  "companion": "Name or empty",
  "guide": "Name of senior guide or empty",
  "checker": "hariharan-projectmanager",
  "due_date": "YYYY-MM-DD or TBD",
  "assigned_date": "today's date YYYY-MM-DD",
  "total_days": 3,
  "priority": "High|Medium|Low",
  "notes": "Context from meeting",
  "escalation_details": "What happens if not done on time",
  "skills_required": ["skill1", "skill2"],
  "skill_match": "Full|Partial|None"
}

Assignment rules:
- Match task skills to employee skills
- If assignee level is Associate (L1/L2) and task needs skills they lack — assign a Senior/Lead as guide
- companion: assign someone at same level working on related tasks
- checker: default to hariharan-projectmanager unless transcript says otherwise
- If no one clearly matches, use Unassigned
- Return [] if no tasks found
"""

def run_task_agent(transcript: str, employees: list = None) -> list:
    MAX_CHARS = 12000
    emp_context = ""
    if employees:
        emp_context = "\n\nPROJECT EMPLOYEES:\n" + json.dumps([{
            "name": e["name"], "email": e.get("email",""),
            "role": e["role"], "band": e["band"], "level": e["level"],
            "skills": e.get("skills",[]),
            "active_tasks": e.get("active_task_count", 0),
            "workload_pct": e.get("workload_pct", 0),
        } for e in employees], indent=2)

    chunks = [transcript[i:i+MAX_CHARS] for i in range(0, len(transcript), MAX_CHARS)]
    all_tasks = []
    seen_ids  = set()

    for chunk in chunks:
        prompt  = f"Transcript:\n\n{chunk}{emp_context}"
        raw     = call_agent("task", SYSTEM_PROMPT, prompt)
        cleaned = re.sub(r"```json|```", "", raw).strip()
        try:
            tasks = json.loads(cleaned)
            for t in tasks:
                if t.get("id") in seen_ids or not t.get("id"):
                    t["id"] = "t_" + str(uuid.uuid4())[:8]
                seen_ids.add(t["id"])
                all_tasks.append(t)
        except:
            pass

    return all_tasks

# -------------------------------------------------------------

# import json
# import re
# import uuid
# from services.groq_client import call_agent

# SYSTEM_PROMPT = """
# You are a task extraction specialist. Your job is to read a meeting transcript
# and extract all action items and tasks as a structured JSON array.

# Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

# Each task must follow this exact structure:
# {
#   "id": "unique string like t1, t2, t3",
#   "title": "Short clear task title",
#   "assignee": "Person responsible (full name if mentioned, else 'Unassigned')",
#   "due_date": "YYYY-MM-DD if mentioned, else 'TBD'",
#   "priority": "High | Medium | Low",
#   "notes": "Any extra context about this task"
# }

# Rules:
# - Extract every task, action item, or follow-up mentioned
# - Priority: High if blocking something or urgent, Low if nice-to-have, else Medium
# - If no due date is mentioned, use 'TBD'
# - If a task is assigned to multiple people, create one task per person
# - Be specific in the title — avoid vague titles like 'Follow up'
# - If no tasks found, return an empty array []
# """


# def run_task_agent(transcript: str) -> list:
#     """
#     Takes a raw transcript string and returns a list of task dicts.
#     """
#     user_prompt = f"Here is the meeting transcript:\n\n{transcript}"
#     raw = call_agent("task", SYSTEM_PROMPT, user_prompt)

#     cleaned = re.sub(r"```json|```", "", raw).strip()

#     try:
#         tasks = json.loads(cleaned)
#         # Ensure each task has a unique id even if model reuses them
#         seen_ids = set()
#         for task in tasks:
#             if task.get("id") in seen_ids or not task.get("id"):
#                 task["id"] = "t_" + str(uuid.uuid4())[:8]
#             seen_ids.add(task["id"])
#         return tasks
#     except json.JSONDecodeError as e:
#         raise ValueError(f"Task agent returned invalid JSON: {e}\nRaw output:\n{raw}")