import json, re
from services.groq_client import call_agent

SYSTEM_PROMPT = """
You are a professional meeting analyst. Read the transcript and extract a detailed structured memo.

IMPORTANT: The manager is identified as "hariharan-projectmanager" or "Hariharan" in the transcript.
- If the manager says "I will schedule a meeting" or "let's meet tomorrow" — add it to manager_actions.
- If any employee mentions scheduling, the manager must always be included as an attendee.

Return ONLY valid JSON. No explanation, no markdown, no code fences.

{
  "title": "Meeting title inferred from context",
  "date": "YYYY-MM-DD or Unknown",
  "attendees": ["Name1", "Name2"],
  "project": "Project name if mentioned else Unknown",
  "summary_points": ["Point 1", "Point 2", "Point 3"],
  "key_decisions": ["Decision 1"],
  "blockers": ["Blocker 1"],
  "risks": ["Risk 1"],
  "dependencies": ["Dependency 1"],
  "next_steps": ["Step 1"],
  "manager_actions": ["Things manager said they will do"],
  "open_questions": ["Unresolved question 1"],
  "highlights": ["Notable moment or achievement 1"],
  "follow_up_required": true
}

Rules:
- summary_points: 4-6 crisp bullet points covering what happened
- highlights: positive achievements, milestones reached
- risks: potential future problems mentioned
- dependencies: things blocked waiting on someone else
- manager_actions: ONLY things Hariharan/manager committed to
- If a field has no content return []
"""

def run_memo_agent(transcript: str) -> dict:
    # Chunk large transcripts
    MAX_CHARS = 12000
    if len(transcript) > MAX_CHARS:
        chunks    = [transcript[i:i+MAX_CHARS] for i in range(0, len(transcript), MAX_CHARS)]
        all_memos = []
        for chunk in chunks:
            raw     = call_agent("memo", SYSTEM_PROMPT, f"Transcript chunk:\n\n{chunk}")
            cleaned = re.sub(r"```json|```", "", raw).strip()
            try:
                all_memos.append(json.loads(cleaned))
            except:
                pass
        return _merge_memos(all_memos)

    raw     = call_agent("memo", SYSTEM_PROMPT, f"Here is the meeting transcript:\n\n{transcript}")
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Memo agent returned invalid JSON: {e}\nRaw:\n{raw}")

def _merge_memos(memos: list) -> dict:
    if not memos: return {}
    base = memos[0]
    list_fields = ["summary_points","key_decisions","blockers","risks",
                   "dependencies","next_steps","manager_actions",
                   "open_questions","highlights","attendees"]
    for m in memos[1:]:
        for f in list_fields:
            base[f] = list(set(base.get(f,[]) + m.get(f,[])))
    return base

# ----------------------------------------------------

# import json
# import re
# from services.groq_client import call_agent

# SYSTEM_PROMPT = """
# You are a professional meeting analyst. Your job is to read a meeting transcript
# and extract a structured memo in JSON format.

# Return ONLY a valid JSON object. No explanation, no markdown, no code fences.

# The JSON must follow this exact structure:
# {
#   "title": "Meeting title inferred from context",
#   "date": "YYYY-MM-DD or 'Unknown' if not mentioned",
#   "attendees": ["Name1", "Name2"],
#   "summary": "2-4 sentence summary of what the meeting was about",
#   "decisions": ["Decision 1", "Decision 2"],
#   "blockers": ["Blocker 1", "Blocker 2"],
#   "next_steps": ["Next step 1", "Next step 2"]
# }

# Rules:
# - attendees: extract every name mentioned as a participant
# - decisions: only firm decisions made, not discussions
# - blockers: issues that are stopping progress
# - next_steps: action items mentioned (who will do what)
# - If a field has no content, return an empty array []
# """


# def run_memo_agent(transcript: str) -> dict:
#     """
#     Takes a raw transcript string and returns a structured memo dict.
#     """
#     user_prompt = f"Here is the meeting transcript:\n\n{transcript}"
#     raw = call_agent("memo", SYSTEM_PROMPT, user_prompt)

#     # Strip any accidental markdown fences if model adds them
#     cleaned = re.sub(r"```json|```", "", raw).strip()

#     try:
#         return json.loads(cleaned)
#     except json.JSONDecodeError as e:
#         raise ValueError(f"Memo agent returned invalid JSON: {e}\nRaw output:\n{raw}")