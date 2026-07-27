"""Config-driven AI provider abstraction for JSON responses."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Set

from src.config_runtime import get_config_value
from src.observability_metrics import record_provider_call
from src.services.http_client import post_json_with_retry

try:
    from google import genai

    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


_TRUE_VALUES = {"1", "true", "yes", "on"}
_DEFAULT_OPENAI_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_AI_PROVIDER_PROMPT_MAX_CHARS = 20_000
_DEFAULT_AI_PROVIDER_OUTPUT_MAX_BYTES = 131_072
_DEFAULT_AI_ALLOWED_PROVIDERS = frozenset({"gemini", "openai_compatible"})
_LOGGER = logging.getLogger(__name__)

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

_PII_PATTERNS = (
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[redacted-email]"),
    (re.compile(r"\+?\d(?:[\d\s().-]{7,})\d"), "[redacted-phone]"),
)


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

    for key in keys:
        value = get_config_value(key, "")
        if str(value).strip():
            return str(value)
    return None


def _get_bool_config(keys: Sequence[str], default_value: bool = False) -> bool:
    raw = _get_config_value(keys)
    if raw is None:
        return default_value
    return str(raw).strip().lower() in _TRUE_VALUES


def is_external_ai_allowed() -> bool:
    raw = _get_config_value(["ALLOW_EXTERNAL_AI", "OKR_ALLOW_EXTERNAL_AI"])
    if raw is None:
        # Secure-by-default: outbound AI calls remain disabled unless explicitly enabled.
        return False
    return str(raw).strip().lower() in _TRUE_VALUES


def is_ai_governance_strict() -> bool:
    """Return whether strict prompt/output governance is enabled."""
    return _get_bool_config(["AI_GOVERNANCE_STRICT", "OKR_AI_GOVERNANCE_STRICT"], False)


def get_ai_data_classification() -> str:
    """Return normalized AI data-classification value."""
    value = (
        str(
            _get_config_value(["AI_DATA_CLASSIFICATION", "OKR_AI_DATA_CLASSIFICATION"])
            or "internal"
        )
        .strip()
        .lower()
    )
    return value if value in {"public", "internal", "confidential"} else "internal"


def get_ai_max_prompt_chars() -> int:
    raw = _get_config_value(["AI_MAX_PROMPT_CHARS", "OKR_AI_MAX_PROMPT_CHARS"])
    try:
        parsed = int(raw or _DEFAULT_AI_PROVIDER_PROMPT_MAX_CHARS)
    except (TypeError, ValueError):
        parsed = _DEFAULT_AI_PROVIDER_PROMPT_MAX_CHARS
    return parsed if parsed > 0 else _DEFAULT_AI_PROVIDER_PROMPT_MAX_CHARS


def get_ai_max_output_bytes() -> int:
    raw = _get_config_value(
        ["AI_MAX_PROVIDER_OUTPUT_BYTES", "OKR_AI_MAX_PROVIDER_OUTPUT_BYTES"]
    )
    try:
        parsed = int(raw or _DEFAULT_AI_PROVIDER_OUTPUT_MAX_BYTES)
    except (TypeError, ValueError):
        parsed = _DEFAULT_AI_PROVIDER_OUTPUT_MAX_BYTES
    return parsed if parsed > 0 else _DEFAULT_AI_PROVIDER_OUTPUT_MAX_BYTES


def _get_governance_metadata_key() -> bool:
    return _get_bool_config(
        ["AI_INCLUDE_GOVERNANCE_METADATA", "OKR_AI_INCLUDE_GOVERNANCE_METADATA"],
        False,
    )


def get_gemini_api_key() -> Optional[str]:
    value = _get_config_value(["GEMINI_API_KEY", "VITE_GEMINI_API_KEY"])
    return str(value).strip() if value is not None else None


get_ai_api_key = get_gemini_api_key


def get_ai_provider() -> str:
    raw = _get_config_value(["AI_PROVIDER", "OKR_AI_PROVIDER"])
    value = str(raw or "gemini").strip().lower()
    return _PROVIDER_ALIASES.get(value, value or "gemini")


def get_gemini_model() -> str:
    value = _get_config_value(["GEMINI_MODEL", "AI_MODEL"])
    model = str(value or "").strip()
    return model or "gemini-flash-latest"


get_ai_model = get_gemini_model


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


def get_ai_provider_allowlist() -> Set[str]:
    raw = _get_config_value(["AI_PROVIDER_ALLOWLIST", "OKR_AI_PROVIDER_ALLOWLIST"])
    if not raw:
        return set(_DEFAULT_AI_ALLOWED_PROVIDERS)

    providers = set()
    for item in str(raw).split(","):
        normalized = _PROVIDER_ALIASES.get(
            str(item).strip().lower(), str(item).strip().lower()
        )
        if normalized:
            providers.add(normalized)

    return providers or set(_DEFAULT_AI_ALLOWED_PROVIDERS)


def is_ai_provider_allowed(provider: str) -> bool:
    normalized = _PROVIDER_ALIASES.get(
        str(provider).strip().lower(), str(provider).strip().lower()
    )
    return (
        normalized in get_ai_provider_allowlist()
        and normalized in _DEFAULT_AI_ALLOWED_PROVIDERS
    )


def get_openai_request_timeout_seconds() -> float:
    value = _get_config_value(
        ["AI_REQUEST_TIMEOUT_SECONDS", "OPENAI_REQUEST_TIMEOUT_SECONDS"]
    )
    text = str(value or "").strip()
    if not text:
        return _DEFAULT_OPENAI_REQUEST_TIMEOUT_SECONDS
    try:
        parsed = float(text)
    except ValueError:
        return _DEFAULT_OPENAI_REQUEST_TIMEOUT_SECONDS
    return parsed if parsed > 0 else _DEFAULT_OPENAI_REQUEST_TIMEOUT_SECONDS


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest()[:16]


def enforce_ai_prompt_governance(prompt: str) -> tuple[str, Dict[str, Any]]:
    """Redact sensitive data from prompts and enforce governance limits."""
    strict = is_ai_governance_strict()
    raw_prompt = str(prompt or "")
    result = raw_prompt
    redactions: Dict[str, int] = {}

    if strict and raw_prompt:
        sanitized = raw_prompt
        for pattern, replacement in _PII_PATTERNS:
            new_value, count = pattern.subn(replacement, sanitized)
            if count:
                redactions[replacement] = redactions.get(replacement, 0) + count
            sanitized = new_value
        result = sanitized

    max_chars = get_ai_max_prompt_chars()
    truncated = False
    if len(result) > max_chars:
        result = result[:max_chars]
        truncated = True

    if not result.strip():
        result = ""

    return result, {
        "classification": get_ai_data_classification(),
        "strict_governance": strict,
        "prompt_hash": _hash_prompt(raw_prompt),
        "prompt_length": len(raw_prompt),
        "effective_length": len(result),
        "truncated": truncated,
        "redactions": redactions,
    }


def get_ai_provider_runtime_status() -> AIProviderStatus:
    provider = get_ai_provider()
    if not is_external_ai_allowed():
        return AIProviderStatus(
            provider=provider,
            ready=True,
            message="External AI calls are disabled by policy.",
        )

    if not is_ai_provider_allowed(provider):
        return AIProviderStatus(
            provider=provider,
            ready=False,
            message=(f"AI provider '{provider}' is not allowed by governance policy."),
        )

    if provider == "gemini":
        if not _GENAI_AVAILABLE:
            return AIProviderStatus(
                provider=provider,
                ready=False,
                message="AI provider 'gemini' requires google-genai package.",
            )
        if not get_ai_api_key():
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
            f"Unsupported AI_PROVIDER '{provider}'. Use: gemini, openai_compatible."
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
    except ValueError:
        # Fallback: attempt to isolate first JSON object block.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = cleaned[start : end + 1]
            try:
                return json.loads(snippet)
            except ValueError:
                return {"error": f"Failed to parse {provider_name} JSON response."}
        return {"error": f"Failed to parse {provider_name} JSON response."}


def _call_gemini_json(prompt: str) -> Dict[str, Any]:
    if not _GENAI_AVAILABLE:
        return {"error": "AI provider 'gemini' requires google-genai package."}

    api_key = get_ai_api_key()
    if not api_key:
        return {"error": "AI provider 'gemini' requires GEMINI_API_KEY."}

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=get_ai_model(),
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
        return {"error": "AI provider 'openai_compatible' requires AI_BASE_URL."}
    if not model:
        return {"error": "AI provider 'openai_compatible' requires AI_MODEL."}

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
            timeout=(5.0, get_openai_request_timeout_seconds()),
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
    if not is_ai_provider_allowed(provider):
        return {
            "error": (f"AI provider '{provider}' is not allowed by governance policy.")
        }

    governed_prompt, policy = enforce_ai_prompt_governance(prompt)
    if not governed_prompt:
        return {
            "error": (
                "AI prompt was rejected by governance policy."
                if is_ai_governance_strict()
                else "Missing prompt."
            )
        }

    started_ms = time.perf_counter()
    payload: Dict[str, Any] = {"error": "Provider call failed before dispatch."}
    try:
        if provider == "gemini":
            payload = _call_gemini_json(governed_prompt)
        elif provider == "openai_compatible":
            payload = _call_openai_compatible_json(governed_prompt)
        else:
            payload = {
                "error": (
                    f"Unsupported AI_PROVIDER '{provider}'. "
                    "Use: gemini, openai_compatible."
                )
            }
    finally:
        if isinstance(payload, dict):
            try:
                output_size = len(json.dumps(payload, ensure_ascii=False))
            except TypeError:
                output_size = get_ai_max_output_bytes() + 1
            if output_size > get_ai_max_output_bytes():
                payload = {
                    "error": "AI provider output exceeded governance output-size policy."
                }

        duration_ms = (time.perf_counter() - started_ms) * 1000
        error_text = (
            payload.get("error")
            if isinstance(payload, dict)
            else "provider call failed"
        )
        if _get_governance_metadata_key() and isinstance(payload, dict):
            payload = dict(payload)
            payload["ai_governance"] = policy
            payload["ai_provider"] = provider
        record_provider_call(
            provider=provider,
            success=not (isinstance(payload, dict) and "error" in payload),
            latency_ms=duration_ms,
            error_code=str(error_text) if error_text else None,
        )
    return payload


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
        "data_classification": get_ai_data_classification(),
        "strict_governance": is_ai_governance_strict(),
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
