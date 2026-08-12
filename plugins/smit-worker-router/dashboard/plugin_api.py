"""Desktop API for the local SMIT worker-router plugin."""

from __future__ import annotations

import json
import math
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_CAPABILITIES = {
    "auto": "Auto",
    "frontend_code": "Frontend code",
    "backend_code": "Backend code",
    "research": "Research",
    "architecture_review": "Architecture review",
    "fast_general": "Fast general work",
}
_LANGUAGES = {"auto", "en", "fr", "ru"}
_REASONING = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
_REASONING_LEVELS = ["minimal", "low", "medium", "high", "xhigh", "max", "ultra"]
_DEFAULT_MODEL = "gpt-5.6-sol"
_DEFAULT_REASONING = "high"
_DYNAMIC_PROFILE = "smit-router-selected"
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_HISTORY_LIMIT = 50
_HISTORY_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


class SettingsBody(BaseModel):
    capability: Literal["auto", "frontend_code", "backend_code", "research", "architecture_review", "fast_general"]
    language: Literal["auto", "en", "fr", "ru"]
    provider: str = "smit-proxy"
    model: str = _DEFAULT_MODEL
    reasoning: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"] = _DEFAULT_REASONING
    fast: bool = False
    handoff_enabled: bool = True


class ProbeBody(BaseModel):
    provider: str = "smit-proxy"
    model: str


def _provider_rows(refresh: bool = False) -> list[dict]:
    """Return authenticated provider discovery rows, stripped to the public schema."""
    from hermes_cli.inventory import load_picker_context
    from hermes_cli.model_switch import list_authenticated_providers

    context = load_picker_context()
    rows = list_authenticated_providers(
        current_provider=context.current_provider,
        current_model=context.current_model,
        current_base_url=context.current_base_url,
        user_providers=context.user_providers,
        custom_providers=context.custom_providers,
        excluded_providers=context.excluded_providers,
        refresh=refresh,
        for_picker=True,
    )
    public = []
    for row in rows:
        slug = str(row.get("slug") or "")
        models = list(row.get("models") or [])
        existing = row.get("capabilities") if isinstance(row.get("capabilities"), dict) else {}
        capabilities = {
            model: _model_capabilities(slug, model, existing.get(model))
            for model in models
        }
        public.append({
            "slug": slug,
            "name": str(row.get("name") or row.get("slug") or ""),
            "models": models,
            "capabilities": capabilities,
            # Retained internally solely to enforce the handoff policy; never returned.
            "_external": row.get("source") == "external-sanitized",
        })
    return public


def _model_capabilities(provider: str, model: str, existing: object = None) -> dict[str, bool]:
    """Return the exact public capability shape for one provider/model pair."""
    from hermes_cli.models import model_supports_fast_mode

    reasoning = True
    thinking = True
    try:
        from agent.models_dev import get_model_capabilities

        metadata = get_model_capabilities(provider, model)
        if metadata is not None:
            reasoning = bool(metadata.supports_reasoning)
            thinking = bool(getattr(metadata, "supports_thinking", reasoning))
    except Exception:
        pass
    try:
        fast = bool(model_supports_fast_mode(model))
    except Exception:
        fast = False

    saved = existing if isinstance(existing, dict) else {}
    return {
        "reasoning": bool(saved.get("reasoning", reasoning)),
        "thinking": bool(saved.get("thinking", thinking)),
        "fast": bool(saved.get("fast", fast)),
    }


def _public_provider_rows(rows: list[dict]) -> list[dict]:
    return [{key: row[key] for key in ("slug", "name", "models", "capabilities")} for row in rows]


def _handoff_locked(config: dict, provider: dict) -> bool:
    profile = (((config.get("delegation") or {}).get("profiles") or {}).get(_DYNAMIC_PROFILE) or {})
    return (
        provider.get("slug") in {"external-sanitized", "smit-proxy"}
        or provider.get("_external") is True
        or profile.get("trust_class") == "external_sanitized"
    )


def _config() -> dict:
    from hermes_cli.config import load_config

    return load_config()


def _hermes_home() -> Path:
    from hermes_constants import get_hermes_home

    return Path(get_hermes_home())


def _models(config: dict) -> list[str]:
    smit = ((config.get("providers") or {}).get("smit-proxy") or {})
    models = smit.get("models") if isinstance(smit, dict) else {}
    return sorted(models) if isinstance(models, dict) else []


def _model_options(config: dict) -> dict[str, dict[str, bool]]:
    from hermes_cli.models import model_supports_fast_mode

    try:
        from agent.models_dev import get_model_capabilities
    except Exception:
        get_model_capabilities = None

    options: dict[str, dict[str, bool]] = {}
    for model in _models(config):
        reasoning = True
        if get_model_capabilities is not None:
            try:
                metadata = get_model_capabilities("smit-proxy", model)
                if metadata is not None:
                    reasoning = bool(metadata.supports_reasoning)
            except Exception:
                reasoning = True
        options[model] = {
            "reasoning": reasoning,
            "fast": bool(model_supports_fast_mode(model)),
        }
    return options


def _save_settings(body: SettingsBody) -> dict:
    from hermes_cli.config import save_config

    config = _config()
    provider_rows = _provider_rows(refresh=False)
    provider = next((row for row in provider_rows if row["slug"] == body.provider), None)
    if provider is None:
        raise HTTPException(status_code=400, detail="Selected provider is not authenticated.")
    models = provider["models"]
    safe_defaults = {"reasoning": True, "thinking": True, "fast": False}
    model_options = {
        model: provider["capabilities"].get(model, safe_defaults)
        for model in models
    }
    if body.model not in models:
        raise HTTPException(status_code=400, detail="Selected model is not registered for the provider.")
    if body.reasoning not in _REASONING:
        raise HTTPException(status_code=400, detail="Selected reasoning effort is not supported.")
    selected_options = model_options.get(body.model, {"reasoning": True, "fast": False})
    if not selected_options["reasoning"] and body.reasoning != "none":
        raise HTTPException(status_code=400, detail="Selected model does not support reasoning.")
    if body.fast and not selected_options["fast"]:
        raise HTTPException(status_code=400, detail="Selected model does not support fast mode.")
    plugins = config.setdefault("plugins", {})
    entries = plugins.setdefault("entries", {})
    entry = entries.setdefault("smit-worker-router", {})
    entry["default_capability"] = body.capability
    entry.pop("default_worker", None)
    entry["default_language"] = body.language
    entry["default_provider"] = body.provider
    entry["default_model"] = body.model
    entry["default_reasoning"] = body.reasoning
    entry["default_fast"] = body.fast
    handoff_locked = _handoff_locked(config, provider)
    handoff_enabled = True if handoff_locked else body.handoff_enabled
    entry["handoff_enabled"] = handoff_enabled
    delegation = config.setdefault("delegation", {})
    profiles = delegation.setdefault("profiles", {})
    profile = profiles.setdefault(_DYNAMIC_PROFILE, {})
    profile.update({
        "provider": body.provider,
        "model": body.model,
        "reasoning_effort": body.reasoning,
        "fast": body.fast,
    })
    save_config(config)
    return {
        "ok": True,
        "capability": body.capability,
        "language": body.language,
        "provider": body.provider,
        "model": body.model,
        "reasoning": body.reasoning,
        "fast": body.fast,
        "handoff_enabled": handoff_enabled,
        "handoff_locked": handoff_locked,
        "models": models,
        "model_options": model_options,
    }


def _settings(config: dict, provider_rows: list[dict]) -> dict:
    """Build the public settings payload from an existing discovery result."""
    entry = (((config.get("plugins") or {}).get("entries") or {}).get("smit-worker-router") or {})
    model = entry.get("default_model") or _DEFAULT_MODEL
    provider_slug = entry.get("default_provider") or "smit-proxy"
    reasoning = entry.get("default_reasoning") or (
        ((config.get("delegation") or {}).get("profiles") or {}).get(_DYNAMIC_PROFILE) or {}
    ).get("reasoning_effort") or _DEFAULT_REASONING
    if reasoning not in _REASONING:
        reasoning = _DEFAULT_REASONING
    provider = next((row for row in provider_rows if row["slug"] == provider_slug), None)
    model_options = provider["capabilities"] if provider is not None else _model_options(config)
    selected_options = model_options.get(model, {"reasoning": True, "fast": False})
    fast = bool(entry.get("default_fast", False)) and selected_options["fast"]
    if not selected_options["reasoning"]:
        reasoning = "none"
    handoff_locked = _handoff_locked(config, provider or {"slug": provider_slug})
    return {
        "capabilities": _CAPABILITIES,
        "languages": sorted(_LANGUAGES),
        "reasoning_options": list(_REASONING_LEVELS),
        "models": _models(config),
        "model_options": model_options,
        "capability": entry.get("default_capability") or entry.get("default_worker") or "auto",
        "language": entry.get("default_language", "auto"),
        "provider": provider_slug,
        "providers": _public_provider_rows(provider_rows),
        "model": model,
        "reasoning_effort": reasoning,
        "fast": fast,
        "handoff_enabled": True if handoff_locked else bool(entry.get("handoff_enabled", True)),
        "handoff_locked": handoff_locked,
        "role": "leaf",
    }


@router.get("/settings")
def get_settings():
    config = _config()
    provider_rows = _provider_rows(refresh=False)
    return _settings(config, provider_rows)


@router.post("/settings")
def save_settings(body: SettingsBody):
    return _save_settings(body)


@router.post("/refresh-workers")
def refresh_workers():
    """Refresh provider discovery and return the current router surface."""
    provider_rows = _provider_rows(refresh=True)
    settings = _settings(_config(), provider_rows)
    return {
        "settings": settings,
        "activity": get_activity(),
        "history": get_history(),
    }


def _probe(provider: str, model: str) -> dict:
    """Validate the selected route through the child runtime's resolver.

    The credential bundle is deliberately reduced to an allowlisted boolean;
    endpoint and authentication material must never cross the desktop API.
    """
    try:
        from tools.delegate_tool import _resolve_delegation_credentials

        config = _config()
        selected = (((config.get("delegation") or {}).get("profiles") or {}).get(_DYNAMIC_PROFILE) or {})
        profile = deepcopy(selected)
        profile["provider"] = provider
        profile["model"] = model
        resolved = _resolve_delegation_credentials(profile, None)
        route_exists = bool(
            resolved.get("provider") or resolved.get("base_url") or resolved.get("command")
        )
        ok = resolved.get("model") == model and route_exists
        return {"provider": provider, "model": model, "ok": ok}
    except Exception as exc:
        error_class = type(exc).__name__[:64]
        return {"provider": provider, "model": model, "ok": False, "error": error_class}


@router.post("/test-selected")
def test_selected_model(body: ProbeBody):
    provider = next((row for row in _provider_rows(refresh=False) if row["slug"] == body.provider), None)
    if provider is None or body.model not in provider["models"]:
        raise HTTPException(status_code=400, detail="Selected provider/model is not registered.")
    result = _probe(body.provider, body.model)
    return {"ok": result["ok"], "result": result}


def _active_workers() -> list[dict]:
    from tools.delegate_tool import list_active_subagents

    return list_active_subagents()


def _safe_task_label(goal: object) -> str:
    text = " ".join(str(goal or "").split())
    text = text.replace("[SMIT_SANITIZED_V1]", "").strip()
    return text[:157] + "..." if len(text) > 160 else text


def _bounded_integer(value: object) -> int:
    """Coerce registry counters without allowing booleans, negatives or huge values."""
    if isinstance(value, bool):
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    if not math.isfinite(number) or number <= 0:
        return 0
    return min(int(number), _MAX_SAFE_INTEGER)


def _assigned_locale(item: dict) -> str:
    """Read the concrete locale assigned by the router, never the `auto` preference."""
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    locale = metadata.get("locale") or metadata.get("LOCALE") or item.get("locale") or item.get("LOCALE")
    locale = str(locale or "").strip()
    return "" if locale == "auto" else locale


def _running_rows() -> list[dict]:
    rows = []
    for item in _active_workers():
        profile = str(item.get("profile") or "")
        if not profile.startswith("smit-"):
            continue
        rows.append({
            "id": str(item.get("subagent_id") or ""),
            "status": "running",
            "model": str(item.get("model") or ""),
            "profile": profile,
            "reasoning_effort": str(item.get("reasoning_effort") or ""),
            "fast": bool(item.get("fast", False)),
            "locale": _assigned_locale(item),
            "depth": int(item.get("depth") or 0),
            "tool_count": int(item.get("tool_count") or 0),
            "current_tool": str(item.get("last_tool") or item.get("current_tool") or ""),
            "task_label": _safe_task_label(item.get("goal")),
            "started_at": item.get("started_at"),
            "input_tokens": _bounded_integer(item.get("input_tokens")),
            "output_tokens": _bounded_integer(item.get("output_tokens")),
            "total_tokens": _bounded_integer(item.get("total_tokens")),
            "api_calls": _bounded_integer(item.get("api_calls")),
            "duration_seconds": _bounded_integer(item.get("duration_seconds")),
        })
    return rows


@router.get("/activity")
def get_activity():
    """Return only active SMIT workers with a bounded sanitized task label."""
    try:
        running = _running_rows()
        return {"active": len(running), "workers": running}
    except Exception:
        return {"active": 0, "workers": []}


def _delegation_live_root() -> Path:
    """The authoritative tree from which public delegation history may be read."""
    from tools.delegation_live_log import live_transcript_root

    return live_transcript_root()


def _read_manifest(path: Path) -> object:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


_HISTORY_TEXT_FIELDS = (
    "id", "delegation_id", "status", "model", "profile", "provider",
    "reasoning_effort", "locale",
)
_HISTORY_COUNTER_FIELDS = (
    "duration_seconds", "api_calls", "input_tokens", "output_tokens", "total_tokens",
)


def _timestamp_number(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else 0.0
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError):
            return 0.0
    return 0.0


def _recent_enough(value: object) -> bool:
    stamp = _timestamp_number(value)
    # Tiny synthetic counters are not epoch timestamps; retain them defensively.
    return stamp < 1_000_000_000 or stamp >= time.time() - _HISTORY_MAX_AGE_SECONDS


def _history_row(item: object) -> dict | None:
    if not isinstance(item, dict) or not str(item.get("profile") or "").startswith("smit-"):
        return None
    completed_at = item.get("completed_at")
    if not _recent_enough(completed_at):
        return None
    row = {field: str(item.get(field) or "") for field in _HISTORY_TEXT_FIELDS}
    row.update({
        "fast": bool(item.get("fast", False)),
        "task_label": _safe_task_label(item.get("task_label", item.get("goal"))),
        "started_at": item.get("started_at"),
        "completed_at": completed_at,
        "cost_usd": item.get("cost_usd", 0),
    })
    row.update({field: _bounded_integer(item.get(field)) for field in _HISTORY_COUNTER_FIELDS})
    return row


def _manifest_rows(manifest: object) -> list[dict]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("tasks"), list):
        return []
    delegation_id = str(manifest.get("delegation_id") or "")
    if not delegation_id:
        return []
    rows = []
    for index, task in enumerate(manifest["tasks"]):
        if not isinstance(task, dict):
            continue
        item = dict(task)
        tokens = task.get("tokens") if isinstance(task.get("tokens"), dict) else {}
        item.update({
            "id": f"{delegation_id}:{index}",
            "delegation_id": delegation_id,
            "started_at": task.get("started_at", manifest.get("started")),
            "completed_at": task.get("completed_at", manifest.get("completed")),
            "input_tokens": tokens.get("input", task.get("input_tokens")),
            "output_tokens": tokens.get("output", task.get("output_tokens")),
            "total_tokens": tokens.get("total", task.get("total_tokens")),
        })
        row = _history_row(item)
        if row is not None:
            rows.append(row)
    return rows


@router.get("/history")
def get_history():
    rows = []
    try:
        paths = _delegation_live_root().rglob("manifest.json")
    except Exception:
        paths = []
    for path in paths:
        try:
            rows.extend(_manifest_rows(_read_manifest(path)))
        except Exception:
            continue
    rows.sort(key=lambda row: _timestamp_number(row["completed_at"]), reverse=True)
    return {"workers": rows[:_HISTORY_LIMIT]}


@router.post("/clear-history")
def clear_history():
    """Remove only delegation manifest files, leaving their trees intact."""
    removed = 0
    try:
        paths = _delegation_live_root().rglob("manifest.json")
    except Exception:
        paths = []
    for path in paths:
        try:
            path.unlink()
            removed += 1
        except Exception:
            continue
    return {"ok": True, "removed": removed, "workers": []}
