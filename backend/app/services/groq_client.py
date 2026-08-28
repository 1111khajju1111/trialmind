from groq import Groq
from app.config import settings

# Exposed directly (not just via ask_llm) because agent_orchestrator.py
# needs the tools/tool_choice parameters that ask_llm's simple wrapper doesn't expose.
client = Groq(api_key=settings.groq_api_key)


def ask_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
    """Single shared entry point for all LLM calls across modules.
    Keeping this centralized makes it easy to swap models, add logging,
    or add retry logic in one place."""
    response = client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""
