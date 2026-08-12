from pathlib import Path
import importlib.util


spec = importlib.util.spec_from_file_location(
    "smit_guard", Path(__file__).with_name("__init__.py")
)
guard = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(guard)


def _args(context: str, **extra):
    return {
        "goal": "[SMIT_SANITIZED_V1] Review CAPABILITY_A7 for ORG_T2.",
        "context": context,
        "role": "leaf",
        **extra,
    }


def test_allows_sanitized_leaf_task():
    assert guard._on_pre_tool_call(
        tool_name="delegate_task",
        args=_args("Use only the supplied sanitized context and public information."),
    ) is None


def test_allows_json_string_payload():
    import json

    payload = _args("Use only the supplied sanitized context and public information.")
    assert guard._on_pre_tool_call(tool_name="delegate_task", args=json.dumps(payload)) is None


def test_blocks_missing_marker():
    assert guard._on_pre_tool_call(
        tool_name="delegate_task",
        args=_args("Use only the supplied sanitized context and public information.", goal="Review ORG_T2."),
    )["action"] == "block"


def test_blocks_secret():
    assert guard._on_pre_tool_call(
        tool_name="delegate_task",
        args=_args("Use only the supplied sanitized context and public information. token=smit_abcdefghijklmnop"),
    )["action"] == "block"


def test_allows_opaque_russian_handoff():
    payload = {
        "goal": "[SMIT_SANITIZED_V1] Проанализируй FLOW_C9 для FORM_A7.",
        "context": "Use only the supplied sanitized context and public information. "
        "Верни краткий результат на русском языке. Сохрани FORM_A7, FLOW_C9 и LOCALE_D4 без изменений.",
        "role": "leaf",
    }
    assert guard._on_pre_tool_call(tool_name="delegate_task", args=payload) is None


def test_allows_generic_foreign_technical_terms():
    payload = _args(
        "Use only the supplied sanitized context and public information. "
        "Review FORM_A7 UI UX accessibility marketplace."
    )
    assert guard._on_pre_tool_call(tool_name="delegate_task", args=payload) is None


def test_blocks_vietnamese_business_context():
    blocked = guard._on_pre_tool_call(
        tool_name="delegate_task",
        args=_args("Use only the supplied sanitized context and public information. Đề xuất UI cho form đăng ký marketplace."),
    )
    assert blocked["action"] == "block"
    assert "vietnamese_business_prose" in blocked["message"]