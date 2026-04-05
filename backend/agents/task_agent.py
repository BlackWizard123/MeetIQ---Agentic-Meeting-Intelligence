import json
import re
import uuid
from services.groq_client import call_agent

SYSTEM_PROMPT = """
You are a task extraction specialist. Your job is to read a meeting transcript
and extract all action items and tasks as a structured JSON array.

Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

Each task must follow this exact structure:
{
  "id": "unique string like t1, t2, t3",
  "title": "Short clear task title",
  "assignee": "Person responsible (full name if mentioned, else 'Unassigned')",
  "due_date": "YYYY-MM-DD if mentioned, else 'TBD'",
  "priority": "High | Medium | Low",
  "notes": "Any extra context about this task"
}

Rules:
- Extract every task, action item, or follow-up mentioned
- Priority: High if blocking something or urgent, Low if nice-to-have, else Medium
- If no due date is mentioned, use 'TBD'
- If a task is assigned to multiple people, create one task per person
- Be specific in the title — avoid vague titles like 'Follow up'
- If no tasks found, return an empty array []
"""


def run_task_agent(transcript: str) -> list:
    """
    Takes a raw transcript string and returns a list of task dicts.
    """
    user_prompt = f"Here is the meeting transcript:\n\n{transcript}"
    raw = call_agent("task", SYSTEM_PROMPT, user_prompt)

    cleaned = re.sub(r"```json|```", "", raw).strip()

    try:
        tasks = json.loads(cleaned)
        # Ensure each task has a unique id even if model reuses them
        seen_ids = set()
        for task in tasks:
            if task.get("id") in seen_ids or not task.get("id"):
                task["id"] = "t_" + str(uuid.uuid4())[:8]
            seen_ids.add(task["id"])
        return tasks
    except json.JSONDecodeError as e:
        raise ValueError(f"Task agent returned invalid JSON: {e}\nRaw output:\n{raw}")