"""Role-labelled router for pre-approved Worker Manager workers."""

from __future__ import annotations

import json
from typing import Any


_CAPABILITIES = {
    "auto": "Auto",
    "frontend_code": "Frontend code",
    "backend_code": "Backend code",
    "research": "Research",
    "architecture_review": "Architecture review",
    "fast_general": "Fast general work",
}
_DEFAULT_CAPABILITY = "auto"
_DEFAULT_MODEL = "gpt-5.6-sol"
_DEFAULT_REASONING = "high"
_DYNAMIC_PROFILE = "smit-router-selected"


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def _configured_settings() -> tuple[str, str, str, str, bool, str]:
    """Return the effective, locally controlled worker routing settings."""
    try:
        from hermes_cli.config import load_config_readonly

        config = load_config_readonly()
        entries = (config.get("plugins") or {}).get("entries") or {}
        entry = entries.get("smit-worker-router") or {}
        profiles = (config.get("delegation") or {}).get("profiles") or {}
        profile = profiles.get(_DYNAMIC_PROFILE) or {}

        capability = entry.get("default_capability") or entry.get("default_worker")
        provider = entry.get("provider") or entry.get("default_provider") or profile.get("provider")
        model = entry.get("model") or entry.get("default_model") or profile.get("model")
        reasoning = (
            entry.get("reasoning")
            or entry.get("default_reasoning")
            or profile.get("reasoning")
            or profile.get("reasoning_effort")
        )
        handoff_enabled = entry.get("handoff_enabled", profile.get("handoff_enabled", False))
        trust_class = entry.get("trust_class") or profile.get("trust_class")
        external = provider == "smit-proxy" or trust_class == "external_sanitized"

        return (
            capability if capability in _CAPABILITIES else _DEFAULT_CAPABILITY,
            provider if isinstance(provider, str) else "",
            model if isinstance(model, str) and model else _DEFAULT_MODEL,
            reasoning if reasoning in {"low", "medium", "high"} else _DEFAULT_REASONING,
            external or handoff_enabled is True,
            trust_class if isinstance(trust_class, str) else "",
        )
    except Exception:
        return _DEFAULT_CAPABILITY, "", _DEFAULT_MODEL, _DEFAULT_REASONING, False, ""


def available_capabilities() -> dict[str, str]:
    return dict(_CAPABILITIES)


def run_worker(
    capability: str = "",
    goal: str = "",
    context: str = "",
    **kwargs: Any,
) -> str:
    """Dispatch a task through the fixed Worker Manager profile."""
    configured_capability, provider, model, _, handoff_enabled, trust_class = _configured_settings()
    selected = configured_capability
    if selected not in _CAPABILITIES:
        return _error("capability must be one of: " + ", ".join(sorted(_CAPABILITIES)))
    if not isinstance(goal, str) or not goal.strip():
        return _error("goal is required")
    external = provider == "smit-proxy" or trust_class == "external_sanitized"
    has_context = isinstance(context, str) and bool(context.strip())
    if external:
        if not handoff_enabled:
            return _error("external sanitized handoff is not enabled")
        if not goal.startswith("[SMIT_SANITIZED_V1]"):
            return _error("goal must begin with the external-sanitized marker [SMIT_SANITIZED_V1]")
        if not has_context:
            return _error("context is required for external sanitized handoff")
    elif handoff_enabled and not has_context:
        return _error("context is required when handoff is enabled")

    from tools.delegate_tool import delegate_task

    result = delegate_task(
        goal=goal,
        context=context,
        role="leaf",
        profile=_DYNAMIC_PROFILE,
        parent_agent=kwargs.get("parent_agent"),
    )
    try:
        payload = json.loads(result)
    except (TypeError, ValueError):
        return result
    if isinstance(payload, dict):
        payload["capability"] = selected
        payload["profile"] = _DYNAMIC_PROFILE
        payload["provider"] = provider
        payload["model"] = model
        return json.dumps(payload, ensure_ascii=False)
    return result


run_smit_worker = run_worker


def register(ctx: Any) -> None:
    for name in ("run_worker", "run_smit_worker"):
        ctx.register_tool(
            name=name,
            toolset="delegation",
            schema={
            "name": name,
            "description": "Dispatch a subagent through Worker Manager. External sanitized routes require enabled handoff, the exact [SMIT_SANITIZED_V1] goal prefix, and nonempty sanitized context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "enum": sorted(_CAPABILITIES),
                        "description": "Optional task role label. auto delegates classification to the private parent. Omit to use the locally configured default capability.",
                    },
                    "goal": {"type": "string", "description": "Goal for the Worker Manager subagent. External sanitized routes must use the required marker prefix."},
                    "context": {"type": "string", "description": "Optional context for ordinary routes; required for enabled handoffs and external sanitized routes."},
                },
                "required": ["goal"],
            },
        },
            handler=lambda args, **kwargs: run_worker(
            capability=args.get("capability", ""),
            goal=args.get("goal", ""),
            context=args.get("context", ""),
            **kwargs,
            ),
        )
