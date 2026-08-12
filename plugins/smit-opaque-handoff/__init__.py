"""Zero-token local builder for opaque SMIT child handoffs."""

from __future__ import annotations

import json
import re
from typing import Any


_MARKER = "[SMIT_SANITIZED_V1]"
_BOUNDARY = "Use only the supplied sanitized context and public information."
_ENTITY_TYPES = {
    "ACTOR", "ARTIFACT", "CAPABILITY", "EVENT", "FLOW", "FORM", "LOCALE",
    "ORG", "POLICY", "RULE", "STATE", "SURFACE", "TENANT",
}
_ALLOWED_ACTIONS = {
    "analyze": {"en": "Analyze", "fr": "Analyse", "ru": "Проанализируй"},
    "review": {"en": "Review", "fr": "Examine", "ru": "Проверь"},
    "compare": {"en": "Compare", "fr": "Compare", "ru": "Сравни"},
    "list_risks": {"en": "List risks for", "fr": "Identifie les risques pour", "ru": "Выяви риски для"},
}
_LANGUAGE_TEXT = {
    "en": ("This is an abstract task. Do not use tools.", "Relations", "Keep", "unchanged.", "Return a brief result in English."),
    "fr": ("Ceci est une tâche abstraite. N'utilise pas d'outils.", "Relations", "Conserve", "sans modification.", "Retourne un résultat bref en français."),
    "ru": ("Это абстрактная задача. Не используй инструменты.", "Отношения", "Сохрани", "без изменений.", "Верни краткий результат на русском языке."),
}
_AUTO_LANGUAGE = "auto"
_LANGUAGES = tuple(_LANGUAGE_TEXT)
_PLACEHOLDER = re.compile(r"^[A-Z]+_[A-Z0-9]{2,}$")
_VIETNAMESE = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]", re.I)


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def _placeholder(entity_type: str, index: int) -> str:
    return f"{entity_type}_{index:02X}"


def _default_language() -> str:
    try:
        from hermes_cli.config import load_config_readonly

        entries = (load_config_readonly().get("plugins") or {}).get("entries") or {}
        configured = (entries.get("smit-worker-router") or {}).get("default_language")
        return configured if configured in {*_LANGUAGES, _AUTO_LANGUAGE} else "ru"
    except Exception:
        return "ru"


def _next_random(seed: int) -> int:
    value = (seed or 1) & 0xFFFFFFFF
    value ^= (value << 13) & 0xFFFFFFFF
    value ^= value >> 17
    value ^= (value << 5) & 0xFFFFFFFF
    return value & 0xFFFFFFFF


def _available_languages(available_languages: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Normalize a caller-provided LOCALE pool without inventing locales."""
    if available_languages is None:
        return _LANGUAGES
    if not isinstance(available_languages, (list, tuple)):
        raise ValueError("available_languages must be a non-empty list of: en, fr, ru")
    normalized = tuple(dict.fromkeys(available_languages))
    if not normalized or any(language not in _LANGUAGES for language in normalized):
        raise ValueError("available_languages must be a non-empty list of: en, fr, ru")
    return normalized


def choose_auto_language(
    previous_language: str = "",
    *,
    seed: int = 1,
    available_languages: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Choose an allowed language while avoiding the previous sequential one."""
    locales = _available_languages(available_languages)
    candidates = [language for language in locales if language != previous_language]
    if not candidates:
        candidates = list(locales)
    return candidates[_next_random(seed) % len(candidates)]


def assign_auto_languages(
    count: int,
    *,
    seed: int = 1,
    available_languages: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Return a deterministic shuffled balanced language bag for parallel workers."""
    if count < 1:
        return []
    locales = _available_languages(available_languages)
    full, remainder = divmod(count, len(locales))
    bag = list(locales) * full
    extras = list(locales)
    state = seed or 1
    for index in range(len(extras) - 1, 0, -1):
        state = _next_random(state)
        swap = state % (index + 1)
        extras[index], extras[swap] = extras[swap], extras[index]
    bag.extend(extras[:remainder])
    for index in range(len(bag) - 1, 0, -1):
        state = _next_random(state)
        swap = state % (index + 1)
        bag[index], bag[swap] = bag[swap], bag[index]
    return bag


def prepare_smit_handoff(
    action: str,
    entities: list[dict[str, Any]],
    relations: list[str] | None = None,
    language: str = "",
    previous_language: str = "",
    seed: int = 1,
    available_languages: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Render a public-safe Russian SMIT task from structured local facts.

    Real entity labels never leave this tool result. The model receives only
    generated placeholders and abstract relation tokens, then passes the result
    as goal/context to delegate_task.
    """
    if action not in _ALLOWED_ACTIONS:
        return _error("action must be one of: analyze, review, compare, list_risks")
    requested_language = language or _default_language()
    if requested_language not in {*_LANGUAGES, _AUTO_LANGUAGE}:
        return _error("language must be one of: auto, en, fr, ru")
    try:
        language = (
            choose_auto_language(
                previous_language,
                seed=seed,
                available_languages=available_languages,
            )
            if requested_language == _AUTO_LANGUAGE
            else requested_language
        )
    except ValueError as exc:
        return _error(str(exc))
    if not isinstance(entities, list) or not entities or len(entities) > 8:
        return _error("entities must contain 1 to 8 structured entries")
    placeholders: list[str] = []
    for index, entity in enumerate(entities, start=1):
        if not isinstance(entity, dict):
            return _error("every entity must be an object")
        entity_type = str(entity.get("type") or "").upper()
        if entity_type not in _ENTITY_TYPES:
            return _error("entity.type is not allowed")
        placeholders.append(_placeholder(entity_type, index))

    clean_relations: list[str] = []
    for relation in relations or []:
        if not isinstance(relation, str) or not re.fullmatch(r"[A-Z][A-Z0-9_ -]{0,48}", relation):
            return _error("relations must be short abstract uppercase labels")
        clean_relations.append(relation)

    subject = ", ".join(placeholders)
    relation_text = "; ".join(clean_relations) if clean_relations else "NONE"
    task_text, relation_label, preserve_text, unchanged_text, result_text = _LANGUAGE_TEXT[language]
    goal = f"{_MARKER} {_ALLOWED_ACTIONS[action][language]} {subject}."
    context = (
        f"{_BOUNDARY} {task_text} {relation_label}: {relation_text}. "
        f"{preserve_text} {subject} {unchanged_text} {result_text}"
    )
    return json.dumps(
        {
            "ok": True,
            "mode": "transform",
            "requested_language": requested_language,
            "language": language,
            "goal": goal,
            "context": context,
            "role": "leaf",
            "placeholders": placeholders,
        },
        ensure_ascii=False,
    )


def _strict_block(tool_name: str = "", args: Any = None, **_: Any):
    if tool_name != "delegate_task" or not isinstance(args, dict):
        return None
    tasks = args.get("tasks") if isinstance(args.get("tasks"), list) else [args]
    for task in tasks:
        if not isinstance(task, dict):
            continue
        text = "\n".join(str(task.get(key) or "") for key in ("goal", "context"))
        if _MARKER in text and _VIETNAMESE.search(text):
            return {
                "action": "block",
                "message": "SMIT opaque handoff blocked Vietnamese text; use prepare_smit_handoff transform mode or an already-opaque Russian task.",
            }
    return None


def register(ctx) -> None:
    ctx.register_tool(
        name="prepare_smit_handoff",
        toolset="delegation",
        schema={
            "name": "prepare_smit_handoff",
            "description": "Local zero-token builder for a Russian opaque SMIT child task. Pass only structured entity types and abstract uppercase relation labels. Real labels are intentionally discarded and never appear in the returned payload.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": sorted(_ALLOWED_ACTIONS)},
                    "entities": {
                        "type": "array",
                        "items": {"type": "object", "properties": {"type": {"type": "string"}}, "required": ["type"]},
                    },
                    "relations": {"type": "array", "items": {"type": "string"}},
                    "language": {"type": "string", "enum": sorted((*_LANGUAGE_TEXT, _AUTO_LANGUAGE))},
                    "previous_language": {"type": "string", "enum": sorted(_LANGUAGE_TEXT)},
                    "seed": {"type": "integer"},
                    "available_languages": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": sorted(_LANGUAGE_TEXT)},
                    },
                },
                "required": ["action", "entities"],
            },
        },
        handler=lambda args, **_kwargs: prepare_smit_handoff(
            action=args.get("action", ""),
            entities=args.get("entities", []),
            relations=args.get("relations"),
            language=args.get("language", ""),
            previous_language=args.get("previous_language", ""),
            seed=args.get("seed", 1),
            available_languages=args.get("available_languages"),
        ),
    )
    ctx.register_hook("pre_tool_call", _strict_block)
