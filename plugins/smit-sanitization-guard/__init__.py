"""Fail-closed validation for every task delegated to smit-proxy.

This plugin deliberately validates a Cockpit-produced sanitized task instead
of attempting to transform private prose locally.  Semantic sanitization stays
with the trusted Cockpit parent; this deterministic gate blocks common leaks
and any delegation that lacks the required handoff marker and boundary.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, Optional


_MARKER = "[SMIT_SANITIZED_V1]"
_BOUNDARY = "Use only the supplied sanitized context and public information."
_PLACEHOLDER = re.compile(r"\b(?:ORG|PERSON|PROJECT|CAPABILITY|ACTOR|DATASET|REGION|SERVICE|TENANT|RECORD|CLIENT|FORM|FLOW|LOCALE|SURFACE|ARTIFACT|POLICY|STATE|RULE|EVENT)_[A-Z0-9]{2,}\b")
_PATTERNS = {
    "secret": re.compile(r"(?i)(?:api[_ -]?key|authorization\s*:\s*bearer|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|smit)_[A-Za-z0-9_-]{12,})"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "private_url": re.compile(r"(?i)https?://(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})"),
    "private_ip": re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})\b"),
    "local_path": re.compile(r"(?i)(?:[A-Z]:\\|/(?:home|users|mnt|private|var)/|\.env\b|state\.db\b|request_dump_[^\s]+)"),
    # Detect Vietnamese business prose by words, not accents: French also
    # legitimately uses characters such as â/é/è in opaque handoffs.
    "vietnamese_business_prose": re.compile(
        r"(?i)(?:đề\s*xuất|đăng\s*ký|người\s*dùng|khách\s*hàng|cửa\s*hàng|"
        r"thị\s*trường|sản\s*phẩm|giao\s*diện|dữ\s*liệu|nội\s*bộ)"
    ),
}


def _task_text(task: Dict[str, Any]) -> str:
    return "\n".join(str(task.get(key) or "") for key in ("goal", "context"))


def _tasks(args: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (TypeError, ValueError):
            return []
    if not isinstance(args, dict):
        return []
    raw = args.get("tasks")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    if isinstance(raw, list):
        return (task for task in raw if isinstance(task, dict))
    nested = args.get("arguments")
    if isinstance(nested, str):
        try:
            nested = json.loads(nested)
        except (TypeError, ValueError):
            nested = None
    if isinstance(nested, dict):
        return _tasks(nested)
    return ({"goal": args.get("goal"), "context": args.get("context"), "role": args.get("role")},)


def _reject(reason: str) -> Dict[str, str]:
    return {
        "action": "block",
        "message": "SMIT sanitization guard blocked delegation: " + reason,
    }


def _on_pre_tool_call(*, tool_name: str = "", args: Any = None, **_: Any) -> Optional[Dict[str, str]]:
    if tool_name != "delegate_task":
        return None
    parsed_args = args
    if isinstance(parsed_args, str):
        try:
            parsed_args = json.loads(parsed_args)
        except (TypeError, ValueError):
            return _reject("task payload is not valid JSON")
    tasks = list(_tasks(parsed_args))
    if not tasks:
        # Some provider paths expose pre_tool_call before JSON arguments are
        # parsed. Defer those calls to the mandatory core validator inside
        # delegate_task instead of producing a false block here.
        return None
    for index, task in enumerate(tasks, start=1):
        text = _task_text(task)
        if _MARKER not in text:
            return _reject(f"task {index} is missing {_MARKER}")
        if _BOUNDARY not in text:
            return _reject(f"task {index} is missing the required child boundary")
        if not _PLACEHOLDER.search(text):
            return _reject(f"task {index} contains no typed one-time placeholder")
        scan_text = text.replace(_MARKER, "")
        for label, pattern in _PATTERNS.items():
            if pattern.search(scan_text):
                return _reject(f"task {index} contains blocked {label} data")
        if str(task.get("role") or parsed_args.get("role") or "leaf").lower() != "leaf":
            return _reject(f"task {index} must use role=leaf")
    return None


def register(ctx: Any) -> None:
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)