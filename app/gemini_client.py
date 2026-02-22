"""
Shared LLM client for NeuraDeck agents.
Fallback order: Groq (primary) → Cerebras → Gemini.
Instantly cascades to the next provider on failure to ensure zero downtime and no thread blocking.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

# Load .env so GROQ_API_KEY, CEREBRAS_API_KEY, GOOGLE_API_KEY are available
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except Exception:
    pass

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"
CEREBRAS_MODEL = "llama-3.3-70b"


def _get_groq_api_key() -> Optional[str]:
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    return key if key else None


def _get_cerebras_api_key() -> Optional[str]:
    key = (os.environ.get("CEREBRAS_API_KEY") or "").strip()
    return key if key else None


def _get_google_api_key() -> Optional[str]:
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    return key if key else None


def _generate_text_groq(
    prompt: str,
    *,
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = 2048,
) -> str:
    """Generate text via Groq."""
    api_key = _get_groq_api_key()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")
        
    from groq import Groq  # type: ignore[reportMissingImports]
    client = Groq(api_key=api_key)
    max_tokens = max_output_tokens if max_output_tokens is not None else 2048
    
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not response or not response.choices:
        return ""
    return (response.choices[0].message.content or "").strip()


def _generate_text_cerebras(
    prompt: str,
    *,
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = 2048,
) -> str:
    """Generate text via Cerebras."""
    api_key = _get_cerebras_api_key()
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY is not set.")
        
    from cerebras.cloud.sdk import Cerebras  # type: ignore[reportMissingImports]
    client = Cerebras(api_key=api_key)
    max_tokens = max_output_tokens if max_output_tokens is not None else 2048
    
    response = client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not response or not response.choices:
        return ""
    return (response.choices[0].message.content or "").strip()


def _configure_gemini_once(api_key: str) -> None:
    if getattr(_configure_gemini_once, "_done", False):
        return
    import google.generativeai as genai  # type: ignore[reportMissingImports]
    genai.configure(api_key=api_key)
    _configure_gemini_once._done = True  # type: ignore[attr-defined]


def _generate_text_gemini(
    prompt: str,
    model_name: str = "gemini-2.0-flash",
    *,
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = 2048,
) -> str:
    """Generate text via Google Gemini, with safety catch."""
    google_key = _get_google_api_key()
    if not google_key:
        raise ValueError("GOOGLE_API_KEY is not set.")
        
    _configure_gemini_once(google_key)
    import google.generativeai as genai  # type: ignore[reportMissingImports]
    model = genai.GenerativeModel(model_name)
    
    kwargs: Any = {}
    try:
        config_kw: Any = {}
        if temperature is not None:
            config_kw["temperature"] = temperature
        if max_output_tokens is not None:
            config_kw["max_output_tokens"] = max_output_tokens
        if config_kw:
            kwargs["generation_config"] = genai.GenerationConfig(**config_kw)
    except (AttributeError, TypeError):
        pass
        
    response = model.generate_content(prompt, **kwargs)
    if not response:
        return ""
        
    # FIX: Safely access response.text so safety filters don't crash the server
    try:
        return response.text.strip()
    except ValueError:
        logger.warning("Gemini safety filter blocked the response.")
        # If blocked, try to return at least the first text part if available
        if response.parts:
             return response.parts[0].text.strip()
        return ""


def generate_text(
    prompt: str,
    model_name: str = "gemini-2.0-flash",
    *,
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = 2048,
) -> str:
    """
    Synchronous generate: Groq → Cerebras → Gemini. 
    INSTANT FALLBACK: If a provider fails or rate-limits, immediately cascades to the next.
    """
    has_groq = _get_groq_api_key() is not None
    has_cerebras = _get_cerebras_api_key() is not None
    has_google = _get_google_api_key() is not None

    if not has_groq and not has_cerebras and not has_google:
        raise ValueError(
            "No LLM configured. Set at least one in .env: "
            "GROQ_API_KEY, CEREBRAS_API_KEY, or GOOGLE_API_KEY."
        )

    errors: list[str] = []

    # 1. Try Groq (Primary)
    if has_groq:
        try:
            return _generate_text_groq(
                prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as e:
            errors.append(f"Groq: {str(e)}")
            logger.warning("Groq failed, falling back to Cerebras. Error: %s", e)

    # 2. Try Cerebras (Secondary)
    if has_cerebras:
        try:
            return _generate_text_cerebras(
                prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as e:
            errors.append(f"Cerebras: {str(e)}")
            logger.warning("Cerebras failed, falling back to Gemini. Error: %s", e)

    # 3. Try Gemini (Tertiary)
    if has_google:
        try:
            return _generate_text_gemini(
                prompt,
                model_name=model_name,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as e:
            errors.append(f"Gemini: {str(e)}")
            logger.warning("Gemini failed. Error: %s", e)

    # If we reach here, all configured providers failed instantly
    raise RuntimeError(
        "All LLM providers failed. Check your API keys and rate limits. "
        "Errors: " + "; ".join(errors)
    )


async def generate_async(
    prompt: str,
    model_name: str = "gemini-2.0-flash",
    *,
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = 2048,
) -> str:
    """Async wrapper: runs generate_text in thread pool (Groq → Cerebras → Gemini)."""
    return await asyncio.to_thread(
        generate_text,
        prompt,
        model_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )