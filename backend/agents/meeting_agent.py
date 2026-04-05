import json
import re
import uuid
from services.groq_client import call_agent

SYSTEM_PROMPT = """
You are a meeting scheduler assistant. Your job is to read a meeting transcript
and suggest follow-up meetings that should be scheduled based on the discussion.

Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

Each suggested meeting must follow this exact structure:
{
  "id": "unique string like m1, m2",
  "title": "Clear meeting title",
  "purpose": "One sentence explaining why this meeting is needed",
  "suggested_date": "YYYY-MM-DD if a date was mentioned, else 'TBD'",
  "duration_mins": 30,
  "recipients": ["Name1", "Name2"],
  "agenda": "Brief bullet-point agenda as a single string with items separated by semicolons"
}

Rules:
- Only suggest meetings that are clearly needed based on the transcript
- recipients: only people who need to be in this specific meeting
- duration_mins: 15 for quick syncs, 30 for reviews, 60 for planning sessions
- Do NOT suggest a meeting just to repeat the same people from today
- If no follow-up meetings are needed, return an empty array []
- Maximum 4 suggested meetings
"""


def run_meeting_agent(transcript: str) -> list:
    """
    Takes a raw transcript string and returns a list of suggested meeting dicts.
    """
    user_prompt = f"Here is the meeting transcript:\n\n{transcript}"
    raw = call_agent("meeting", SYSTEM_PROMPT, user_prompt)

    cleaned = re.sub(r"```json|```", "", raw).strip()

    try:
        meetings = json.loads(cleaned)
        seen_ids = set()
        for meeting in meetings:
            if meeting.get("id") in seen_ids or not meeting.get("id"):
                meeting["id"] = "m_" + str(uuid.uuid4())[:8]
            seen_ids.add(meeting["id"])
        return meetings
    except json.JSONDecodeError as e:
        raise ValueError(f"Meeting agent returned invalid JSON: {e}\nRaw output:\n{raw}")