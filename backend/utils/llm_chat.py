"""
Platform-agnostic LLM chat using Google Generative AI (Gemini).
Uses LLM_API_KEY from environment (Gemini API key from Google AI Studio).
Replaces previous emergentintegrations dependency.
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
