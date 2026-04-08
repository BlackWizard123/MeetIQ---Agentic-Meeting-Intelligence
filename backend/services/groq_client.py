import os
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

GCP_PROJECT = os.getenv("GCP_PROJECT")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# One model per agent — all use Gemini 1.5 Pro (1M context, no size limits)
AGENT_MODELS = {
    "memo":    "gemini-2.5-pro",
    "task":    "gemini-2.5-pro",
    "meeting": "gemini-2.5-flash",  # Flash for simpler extraction — faster + cheaper
    "thread":  "gemini-2.5-pro",
}

_initialized = False

def _init():
    global _initialized
    if not _initialized:
        vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)
        _initialized = True

def _date_header() -> str:
    now = datetime.now()
    return (
        f"[SYSTEM CONTEXT]\n"
        f"Today's date: {now.strftime('%A, %d %B %Y')}\n"
        f"Current year: {now.year}\n"
        f"Current time: {now.strftime('%H:%M')} IST\n"
        f"IMPORTANT: All dates you generate MUST be in {now.year} or later. "
        f"Never generate dates in the past.\n"
        f"[END SYSTEM CONTEXT]\n\n"
    )


def call_agent(agent_name: str, system_prompt: str, user_prompt: str) -> str:
    """
    Call Vertex AI Gemini with the model assigned to the given agent.
    Returns the raw text response.
    """
    _init()

    model_name = AGENT_MODELS.get(agent_name)
    if not model_name:
        raise ValueError(f"Unknown agent: {agent_name}")

    model = GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )

    # Prepend today's date to every prompt so model never guesses the year
    dated_prompt = _date_header() + user_prompt

    response = model.generate_content(
        dated_prompt,
        generation_config=GenerationConfig(
            temperature=0.3,
            max_output_tokens=8192,
        ),
    )

    return response.text

# -----------------------------------------------------

# import os
# from groq import Groq
# from dotenv import load_dotenv

# load_dotenv()

# # One model per agent to distribute load and avoid rate limits
# AGENT_MODELS = {
#     "memo":    "groq/compound-mini",
#     "task":    "groq/compound",
#     "meeting": "groq/compound",
#     "thread":  "groq/compound-mini",
# }

# _client = None

# def _get_client() -> Groq:
#     global _client
#     if _client is None:
#         api_key = os.getenv("GROQ_API_KEY")
#         if not api_key:
#             raise ValueError("GROQ_API_KEY is not set in your .env file")
#         _client = Groq(api_key=api_key)
#     return _client


# def call_agent(agent_name: str, system_prompt: str, user_prompt: str) -> str:
#     """
#     Call the Groq API with the model assigned to the given agent.
#     Returns the raw text response.
#     """
#     model = AGENT_MODELS.get(agent_name)
#     if not model:
#         raise ValueError(f"Unknown agent: {agent_name}")

#     client = _get_client()

#     response = client.chat.completions.create(
#         model=model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user",   "content": user_prompt},
#         ],
#         temperature=0.3,
#         max_tokens=4096,
#     )

#     return response.choices[0].message.content