import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# One model per agent to distribute load and avoid rate limits
AGENT_MODELS = {
    "memo":    "groq/compound-mini",
    "task":    "groq/compound",
    "meeting": "groq/compound",
    "thread":  "groq/compound-mini",
}

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in your .env file")
        _client = Groq(api_key=api_key)
    return _client


def call_agent(agent_name: str, system_prompt: str, user_prompt: str) -> str:
    """
    Call the Groq API with the model assigned to the given agent.
    Returns the raw text response.
    """
    model = AGENT_MODELS.get(agent_name)
    if not model:
        raise ValueError(f"Unknown agent: {agent_name}")

    client = _get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=4096,
    )

    return response.choices[0].message.content