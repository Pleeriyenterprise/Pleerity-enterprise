"""
Platform-agnostic LLM chat: OpenAI (via ai_config) and Google Generative AI (Gemini).
- Assistant chat uses OpenAI when AI_ENABLED and ai_config.is_configured() (OPENAI_API_KEY).
- Other features (prompt testing, admin snapshot assistant, etc.) may use Gemini via LLM_API_KEY.
"""
import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Single env var for Gemini/LLM (no Emergent-specific names)
LLM_API_KEY = os.environ.get("LLM_API_KEY")


def _get_api_key() -> Optional[str]:
    return LLM_API_KEY


# ---------------------------------------------------------------------------
# OpenAI (ai_config) – used by Compliance Vault Assistant when AI_PROVIDER=openai
# ---------------------------------------------------------------------------


def _sync_chat_openai(system_prompt: str, user_text: str) -> str:
    """Synchronous OpenAI chat completion using utils.ai_config (model, temperature, max_tokens)."""
    from utils import ai_config
    try:
        from openai import OpenAI
    except ImportError:
        raise ValueError("openai package not installed")
    api_key = ai_config.get_openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=ai_config.AI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=ai_config.AI_TEMPERATURE,
        max_tokens=ai_config.AI_MAX_OUTPUT_TOKENS,
    )
    raw = (response.choices[0].message.content or "").strip()
    if not raw:
        raise ValueError("Empty response from OpenAI")
    return raw


async def chat_openai(system_prompt: str, user_text: str) -> str:
    """Async OpenAI chat using ai_config. For use when ai_config.is_configured() and AI_PROVIDER=openai."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _sync_chat_openai(system_prompt, user_text),
    )


def _sync_chat(system_prompt: str, user_text: str, model: str = "gemini-2.0-flash") -> str:
    """Synchronous chat completion using Google Generative AI."""
    import google.generativeai as genai
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("LLM_API_KEY not found in environment")
    genai.configure(api_key=api_key)
    model_name = model if model and "gemini" in model else "gemini-2.0-flash"
    gemini = genai.GenerativeModel(
        model_name,
        system_instruction=system_prompt,
    )
    response = gemini.generate_content(user_text)
    if not response or not response.text:
        raise ValueError("Empty response from LLM")
    return response.text


def _sync_chat_with_file(
    system_prompt: str,
    user_text: str,
    file_path: str,
    mime_type: str,
    model: str = "gemini-2.0-flash",
) -> str:
    """Synchronous chat with file attachment (e.g. document analysis)."""
    import google.generativeai as genai
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("LLM_API_KEY not found in environment")
    genai.configure(api_key=api_key)
    uploaded = genai.upload_file(path=file_path, mime_type=mime_type)
    model_name = model if model and "gemini" in model else "gemini-2.0-flash"
    gemini = genai.GenerativeModel(
        model_name,
        system_instruction=system_prompt,
    )
    response = gemini.generate_content([uploaded, user_text])
    if not response or not response.text:
        raise ValueError("Empty response from LLM")
    return response.text


async def chat(
    system_prompt: str,
    user_text: str,
    model: str = "gemini-2.0-flash",
) -> str:
    """Async chat completion. Runs sync SDK in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _sync_chat(system_prompt, user_text, model),
    )


async def chat_with_file(
    system_prompt: str,
    user_text: str,
    file_path: str,
    mime_type: str,
    model: str = "gemini-2.0-flash",
) -> str:
    """Async chat with file attachment."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _sync_chat_with_file(system_prompt, user_text, file_path, mime_type, model),
    )
