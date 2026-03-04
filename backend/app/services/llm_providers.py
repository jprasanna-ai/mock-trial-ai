"""
Multi-provider LLM abstraction.

Routes requests to the correct provider (OpenAI, Anthropic, Google, xAI)
based on the model name. All providers expose the same chat-completion
interface so agents and the LLM service remain provider-agnostic.
"""

import os
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# ─── Model → Provider mapping ────────────────────────────────────────────────

PROVIDER_MODELS: Dict[str, List[str]] = {
    "openai": [
        "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo",
    ],
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "google": [
        "gemini-2.5-pro", "gemini-2.5-flash",
        "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash",
    ],
    "xai": [
        "grok-3", "grok-3-mini",
    ],
}

# Flatten for quick lookup
_MODEL_TO_PROVIDER: Dict[str, str] = {}
for provider, models in PROVIDER_MODELS.items():
    for m in models:
        _MODEL_TO_PROVIDER[m] = provider


def get_provider_for_model(model: str) -> str:
    return _MODEL_TO_PROVIDER.get(model, "openai")


# ─── Available models list (for frontend) ────────────────────────────────────

AVAILABLE_MODELS = [
    # OpenAI
    {"id": "gpt-4.1", "label": "GPT-4.1", "provider": "openai", "description": "Best OpenAI model for trial simulation"},
    {"id": "gpt-4.1-mini", "label": "GPT-4.1 Mini", "provider": "openai", "description": "Fast, lower cost OpenAI"},
    {"id": "gpt-4.1-nano", "label": "GPT-4.1 Nano", "provider": "openai", "description": "Fastest, cheapest OpenAI"},
    {"id": "gpt-4o", "label": "GPT-4o", "provider": "openai", "description": "Multimodal OpenAI"},
    {"id": "gpt-4o-mini", "label": "GPT-4o Mini", "provider": "openai", "description": "Affordable multimodal"},
    # Anthropic
    {"id": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4", "provider": "anthropic", "description": "Latest Anthropic model"},
    {"id": "claude-3-5-sonnet-20241022", "label": "Claude 3.5 Sonnet", "provider": "anthropic", "description": "Strong reasoning, balanced"},
    {"id": "claude-3-5-haiku-20241022", "label": "Claude 3.5 Haiku", "provider": "anthropic", "description": "Fast and affordable Anthropic"},
    # Google
    {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "provider": "google", "description": "Most capable Google model"},
    {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "provider": "google", "description": "Fast Google model"},
    {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash", "provider": "google", "description": "Affordable Google model"},
    # xAI
    {"id": "grok-3", "label": "Grok 3", "provider": "xai", "description": "xAI flagship model"},
    {"id": "grok-3-mini", "label": "Grok 3 Mini", "provider": "xai", "description": "Fast xAI model"},
]


# ─── Provider clients (lazy singletons) ──────────────────────────────────────

_clients: Dict[str, Any] = {}


def _get_openai_client():
    if "openai" not in _clients:
        from ..utils.openai_client import get_openai_client
        _clients["openai"] = get_openai_client()
    return _clients["openai"]


def _get_anthropic_client():
    if "anthropic" not in _clients:
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY not set")
                return None
            _clients["anthropic"] = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            logger.warning("anthropic package not installed")
            return None
    return _clients.get("anthropic")


def _get_google_client():
    if "google" not in _clients:
        try:
            from google import genai
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GOOGLE_API_KEY / GEMINI_API_KEY not set")
                return None
            _clients["google"] = genai.Client(api_key=api_key)
        except ImportError:
            logger.warning("google-genai package not installed")
            return None
    return _clients.get("google")


def _get_xai_client():
    """xAI Grok uses OpenAI-compatible API."""
    if "xai" not in _clients:
        try:
            from openai import OpenAI
            api_key = os.environ.get("XAI_API_KEY")
            if not api_key:
                logger.warning("XAI_API_KEY not set")
                return None
            _clients["xai"] = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        except Exception:
            logger.warning("Failed to create xAI client")
            return None
    return _clients.get("xai")


# ─── Unified chat completion ─────────────────────────────────────────────────

def chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gpt-4.1",
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """Route a chat completion request to the correct provider."""
    provider = get_provider_for_model(model)

    if provider == "openai":
        client = _get_openai_client()
        return client.chat_completion(
            messages=messages, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )

    if provider == "anthropic":
        client = _get_anthropic_client()
        if not client:
            logger.warning(f"Anthropic unavailable, falling back to OpenAI for {model}")
            return _get_openai_client().chat_completion(
                messages=messages, model="gpt-4.1",
                temperature=temperature, max_tokens=max_tokens,
            )
        system_msg = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg += m["content"] + "\n"
            else:
                user_msgs.append({"role": m["role"], "content": m["content"]})
        if not user_msgs:
            user_msgs = [{"role": "user", "content": "Please respond."}]
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg.strip() if system_msg else "You are a helpful assistant.",
            messages=user_msgs,
        )
        return response.content[0].text.strip()

    if provider == "google":
        client = _get_google_client()
        if not client:
            logger.warning(f"Google unavailable, falling back to OpenAI for {model}")
            return _get_openai_client().chat_completion(
                messages=messages, model="gpt-4.1",
                temperature=temperature, max_tokens=max_tokens,
            )
        system_msg = ""
        contents = []
        for m in messages:
            if m["role"] == "system":
                system_msg += m["content"] + "\n"
            else:
                role = "model" if m["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Please respond."}]}]
        from google.genai import types
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_msg.strip() if system_msg else None,
        )
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        return response.text.strip()

    if provider == "xai":
        client = _get_xai_client()
        if not client:
            logger.warning(f"xAI unavailable, falling back to OpenAI for {model}")
            return _get_openai_client().chat_completion(
                messages=messages, model="gpt-4.1",
                temperature=temperature, max_tokens=max_tokens,
            )
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    # Fallback
    return _get_openai_client().chat_completion(
        messages=messages, model=model,
        temperature=temperature, max_tokens=max_tokens,
    )


async def chat_completion_async(
    messages: List[Dict[str, str]],
    model: str = "gpt-4.1",
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """Async version — runs sync providers in a thread when needed."""
    import asyncio
    provider = get_provider_for_model(model)

    if provider == "openai":
        client = _get_openai_client()
        return await client.chat_completion_async(
            messages=messages, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )

    # For non-OpenAI providers, run sync in thread pool
    return await asyncio.to_thread(
        chat_completion,
        messages=messages, model=model,
        temperature=temperature, max_tokens=max_tokens,
    )
