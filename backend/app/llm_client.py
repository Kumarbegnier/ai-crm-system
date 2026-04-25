"""
Structured async Ollama client with JSON-mode support and retry logic.
"""
import json
import logging
import asyncio
from typing import Any, AsyncIterator

import ollama

from .config import AGENT_MODEL, AGENT_TIMEOUT

logger = logging.getLogger(__name__)

_client: ollama.AsyncClient | None = None


def get_client() -> ollama.AsyncClient:
    global _client
    if _client is None:
        _client = ollama.AsyncClient()
    return _client


async def chat_stream(
    messages: list[dict[str, str]],
    model: str = AGENT_MODEL,
    timeout: int = AGENT_TIMEOUT,
) -> AsyncIterator[str]:
    """Yield raw content chunks from Ollama streaming chat."""
    try:
        async with asyncio.timeout(timeout):
            stream = await get_client().chat(model=model, messages=messages, stream=True)
            async for resp in stream:
                content = resp["message"].get("content", "")
                if content:
                    yield content
    except asyncio.TimeoutError:
        logger.error("LLM chat_stream timed out")
        raise


async def chat_json(
    messages: list[dict[str, str]],
    model: str = AGENT_MODEL,
    timeout: int = AGENT_TIMEOUT,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Request a JSON object from the LLM with retry logic."""
    system_msg = {
        "role": "system",
        "content": (
            "You are a JSON-only API. Respond with a single valid JSON object "
            "and no markdown formatting, no explanation, no code fences."
        ),
    }
    # Prepend system instruction if not already present
    if not messages or messages[0].get("role") != "system":
        msgs = [system_msg, *messages]
    else:
        msgs = [*messages]

    for attempt in range(max_retries + 1):
        try:
            async with asyncio.timeout(timeout):
                resp = await get_client().chat(model=model, messages=msgs, stream=False)
            text = resp["message"].get("content", "")
            # Strip fences
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[-1]
                if text.lower().startswith("json"):
                    text = text[4:]
                text = text.strip()
            if text.endswith("```"):
                text = text[:-3].strip()
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, KeyError, asyncio.TimeoutError) as e:
            logger.warning(f"chat_json attempt {attempt + 1} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue
    logger.error("chat_json exhausted all retries, returning empty dict")
    return {}

