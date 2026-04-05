import json
import re
from services.groq_client import call_agent

SYSTEM_PROMPT = """
You are a professional meeting analyst. Your job is to read a meeting transcript
and extract a structured memo in JSON format.

Return ONLY a valid JSON object. No explanation, no markdown, no code fences.

The JSON must follow this exact structure:
{
  "title": "Meeting title inferred from context",
  "date": "YYYY-MM-DD or 'Unknown' if not mentioned",
  "attendees": ["Name1", "Name2"],
  "summary": "2-4 sentence summary of what the meeting was about",
  "decisions": ["Decision 1", "Decision 2"],
  "blockers": ["Blocker 1", "Blocker 2"],
  "next_steps": ["Next step 1", "Next step 2"]
}

Rules:
- attendees: extract every name mentioned as a participant
- decisions: only firm decisions made, not discussions
- blockers: issues that are stopping progress
- next_steps: action items mentioned (who will do what)
- If a field has no content, return an empty array []
"""


def run_memo_agent(transcript: str) -> dict:
    """
    Takes a raw transcript string and returns a structured memo dict.
    """
    user_prompt = f"Here is the meeting transcript:\n\n{transcript}"
    raw = call_agent("memo", SYSTEM_PROMPT, user_prompt)

    # Strip any accidental markdown fences if model adds them
    cleaned = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Memo agent returned invalid JSON: {e}\nRaw output:\n{raw}")