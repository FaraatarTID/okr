"""Config-driven AI provider abstraction for JSON responses."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import streamlit as st

from src.services.http_client import post_json_with_retry

try:
    from google import genai

    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


_TRUE_VALUES = {"1", "true", "yes", "on"}

_PROVIDER_ALIASES = {
    "gemini": "gemini",
    "google": "gemini",
    "google-gemini": "gemini",
    "openai": "openai_compatible",
    "openai_compatible": "openai_compatible",
    "openai-compatible": "openai_compatible",
    "local": "openai_compatible",
    "ollama": "openai_compatible",
    "lmstudio": "openai_compatible",
    "lm-studio": "openai_compatible",
    "vllm": "openai_compatible",
}


@dataclass(frozen=True)
class AIProviderStatus:
    provider: str
    ready: bool
    message: str


def _get_config_value(keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value is not None:
            return value

    try:
        app_cfg = st.secrets.get("app", {})
        for key in keys:
            if key in st.secrets:
                value = st.secrets.get(key)
                if value is not None:
                    return str(value)
            if hasattr(app_cfg, "get"):
                value = app_cfg.get(key)
                if value is not None:
                    return str(value)
    except Exception:
        pass
    return None


def is_external_ai_allowed() -> bool:
    raw = _get_config_value(["ALLOW_EXTERNAL_AI", "OKR_ALLOW_EXTERNAL_AI"])
    if raw is None:
        # Secure-by-default: outbound AI calls remain disabled unless explicitly enabled.
        return False
    return str(raw).strip().lower() in _TRUE_VALUES


def get_gemini_api_key() -> Optional[str]:
    value = _get_config_value(["GEMINI_API_KEY", "VITE_GEMINI_API_KEY"])
    return str(value).strip() if value is not None else None


def get_ai_provider() -> str:
    raw = _get_config_value(["AI_PROVIDER", "OKR_AI_PROVIDER"])
    value = str(raw or "gemini").strip().lower()
    return _PROVIDER_ALIASES.get(value, value or "gemini")


def get_gemini_model() -> str:
    value = _get_config_value(["GEMINI_MODEL", "AI_MODEL"])
    model = str(value or "").strip()
    return model or "gemini-flash-latest"


def get_openai_base_url() -> Optional[str]:
    value = _get_config_value(["AI_BASE_URL", "OPENAI_BASE_URL", "OLLAMA_BASE_URL"])
    value = str(value or "").strip()
    return value or None


def get_openai_model() -> Optional[str]:
    value = _get_config_value(["AI_MODEL", "OPENAI_MODEL", "OLLAMA_MODEL"])
    value = str(value or "").strip()
    return value or None


def get_openai_api_key() -> Optional[str]:
    value = _get_config_value(["AI_API_KEY", "OPENAI_API_KEY"])
    value = str(value or "").strip()
    return value or None


def get_ai_provider_runtime_status() -> AIProviderStatus:
    provider = get_ai_provider()
    if not is_external_ai_allowed():
        return AIProviderStatus(
            provider=provider,
            ready=True,
            message="External AI calls are disabled by policy.",
        )

    if provider == "gemini":
        if not _GENAI_AVAILABLE:
            return AIProviderStatus(
                provider=provider,
                ready=False,
                message="AI provider 'gemini' requires google-genai package.",
            )
        if not get_gemini_api_key():
            return AIProviderStatus(
                provider=provider,
                ready=False,
                message="AI provider 'gemini' requires GEMINI_API_KEY.",
            )
        return AIProviderStatus(
            provider=provider,
            ready=True,
            message=f"AI provider '{provider}' is configured.",
        )

    if provider == "openai_compatible":
        base_url = get_openai_base_url()
        model = get_openai_model()
        missing = []
        if not base_url:
            missing.append("AI_BASE_URL")
        if not model:
            missing.append("AI_MODEL")
        if missing:
            return AIProviderStatus(
                provider=provider,
                ready=False,
                message=(
                    "AI provider 'openai_compatible' missing required config: "
                    + ", ".join(missing)
                    + "."
                ),
            )
        return AIProviderStatus(
            provider=provider,
            ready=True,
            message=f"AI provider '{provider}' is configured.",
        )

    return AIProviderStatus(
        provider=provider,
        ready=False,
        message=(
            f"Unsupported AI_PROVIDER '{provider}'. "
            "Use: gemini, openai_compatible."
        ),
    )


def _clean_ai_text(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _parse_json_payload(text: str, provider_name: str) -> Dict[str, Any]:
    cleaned = _clean_ai_text(text)
    if not cleaned:
        return {"error": f"{provider_name} returned an empty response."}

    try:
        return json.loads(cleaned)
    except Exception:
        # Fallback: attempt to isolate first JSON object block.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = cleaned[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                pass
        return {"error": f"Failed to parse {provider_name} JSON response."}


def _call_gemini_json(prompt: str) -> Dict[str, Any]:
    if not _GENAI_AVAILABLE:
        return {"error": "AI provider 'gemini' requires google-genai package."}

    api_key = get_gemini_api_key()
    if not api_key:
        return {"error": "AI provider 'gemini' requires GEMINI_API_KEY."}

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        text = getattr(response, "text", None)
        if not text:
            return {"error": "Gemini returned an empty response."}
        return _parse_json_payload(text, "Gemini")
    except Exception as exc:
        return {"error": f"Gemini request failed: {exc}"}


def _openai_chat_completions_url(base_url: str) -> str:
    cleaned = str(base_url or "").strip().rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
    return f"{cleaned}/v1/chat/completions"


def _normalize_openai_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item.get("text")))
                elif item.get("content"):
                    parts.append(str(item.get("content")))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content or "")


def _call_openai_compatible_json(prompt: str) -> Dict[str, Any]:
    base_url = get_openai_base_url()
    model = get_openai_model()
    if not base_url:
        return {
            "error": "AI provider 'openai_compatible' requires AI_BASE_URL."
        }
    if not model:
        return {
            "error": "AI provider 'openai_compatible' requires AI_MODEL."
        }

    url = _openai_chat_completions_url(base_url)
    headers = {"Content-Type": "application/json"}
    api_key = get_openai_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return valid JSON only. Do not use markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        response = post_json_with_retry(
            url,
            headers=headers,
            json_payload=payload,
            retries=1,
        )
    except Exception as exc:
        return {"error": f"AI provider request failed: {exc}"}

    if response.status_code >= 400:
        text = str(response.text or "").strip()
        snippet = text[:180] + ("..." if len(text) > 180 else "")
        return {
            "error": (
                "AI provider 'openai_compatible' returned HTTP "
                f"{response.status_code}: {snippet}"
            )
        }

    try:
        body = response.json()
    except Exception as exc:
        return {"error": f"AI provider response is not valid JSON: {exc}"}

    choices = body.get("choices") if isinstance(body, dict) else None
    if not choices or not isinstance(choices, list):
        return {"error": "AI provider response missing choices[] payload."}

    message = choices[0].get("message", {})
    content = _normalize_openai_content(message.get("content"))
    if not content:
        return {"error": "AI provider returned empty message content."}

    return _parse_json_payload(content, "openai_compatible")


def generate_json(prompt: str) -> Dict[str, Any]:
    """Generate structured JSON using configured AI provider."""
    if not is_external_ai_allowed():
        return {
            "error": (
                "External AI calls are disabled by policy "
                "(set ALLOW_EXTERNAL_AI=true to enable)."
            )
        }

    provider = get_ai_provider()
    if provider == "gemini":
        return _call_gemini_json(prompt)
    if provider == "openai_compatible":
        return _call_openai_compatible_json(prompt)

    return {
        "error": (
            f"Unsupported AI_PROVIDER '{provider}'. "
            "Use: gemini, openai_compatible."
        )
    }


def run_ai_health_check(*, live_probe: bool = True) -> Dict[str, Any]:
    """
    Evaluate AI configuration and optionally execute a live provider probe.

    Returns a structured dictionary with:
      - status: one of disabled|not_configured|configured|ok|probe_failed
      - provider
      - external_ai_allowed
      - configured
      - config_message
      - live_probe_enabled
      - probe_ok
      - probe_message
      - probe_payload (when probe runs)
    """
    status = get_ai_provider_runtime_status()
    report: Dict[str, Any] = {
        "status": "configured",
        "provider": status.provider,
        "external_ai_allowed": is_external_ai_allowed(),
        "configured": bool(status.ready),
        "config_message": status.message,
        "live_probe_enabled": bool(live_probe),
        "probe_ok": None,
        "probe_message": None,
    }

    if not report["external_ai_allowed"]:
        report["status"] = "disabled"
        report["probe_message"] = "Skipped: external AI is disabled by policy."
        return report

    if not report["configured"]:
        report["status"] = "not_configured"
        report["probe_ok"] = False
        report["probe_message"] = "Provider configuration is incomplete."
        return report

    if not live_probe:
        report["status"] = "configured"
        report["probe_message"] = "Live probe skipped by option."
        return report

    probe_prompt = (
        "Return strict JSON only with shape "
        '{"health":"ok","purpose":"provider_health_check"}.'
    )
    probe_payload = generate_json(probe_prompt)
    report["probe_payload"] = probe_payload

    if isinstance(probe_payload, dict) and "error" not in probe_payload:
        report["status"] = "ok"
        report["probe_ok"] = True
        report["probe_message"] = "Live AI probe succeeded."
        return report

    report["status"] = "probe_failed"
    report["probe_ok"] = False
    error_text = (
        str(probe_payload.get("error"))
        if isinstance(probe_payload, dict)
        else "Unknown probe error."
    )
    report["probe_message"] = f"Live AI probe failed: {error_text}"
    return report
