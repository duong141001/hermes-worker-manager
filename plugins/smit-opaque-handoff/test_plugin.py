import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("opaque", Path(__file__).with_name("__init__.py"))
opaque = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(opaque)


def test_transform_discards_real_entity_labels():
    result = json.loads(
        opaque.prepare_smit_handoff(
            action="review",
            entities=[
                {"type": "form", "label": "form đăng ký marketplace"},
                {"type": "actor", "label": "người bán địa phương"},
            ],
            relations=["FLOW_VALIDATION", "LOCALE_RULE"],
        )
    )
    payload = result["goal"] + "\n" + result["context"]
    assert result["ok"] is True
    assert result["mode"] == "transform"
    assert "FORM_01" in payload
    assert "ACTOR_02" in payload
    assert "marketplace" not in payload
    assert "người bán" not in payload


def test_builder_output_passes_guard_in_each_supported_language():
    guard_spec = importlib.util.spec_from_file_location(
        "guard", Path(__file__).parents[1] / "smit-sanitization-guard" / "__init__.py"
    )
    guard = importlib.util.module_from_spec(guard_spec)
    assert guard_spec.loader is not None
    guard_spec.loader.exec_module(guard)
    for language in ("en", "fr", "ru"):
        result = json.loads(opaque.prepare_smit_handoff(
            action="review",
            entities=[{"type": "form", "label": "private label"}],
            relations=["UI ACCESSIBILITY"],
            language=language,
        ))
        assert guard._on_pre_tool_call(
            tool_name="delegate_task",
            args={"goal": result["goal"], "context": result["context"], "role": "leaf"},
        ) is None


def test_strict_blocks_vietnamese_delegation():
    blocked = opaque._strict_block(
        tool_name="delegate_task",
        args={
            "goal": "[SMIT_SANITIZED_V1] Review FORM_A7.",
            "context": "Use only the supplied sanitized context and public information. Đề xuất form đăng ký.",
        },
    )
    assert blocked["action"] == "block"


def test_strict_allows_opaque_russian_delegation():
    allowed = opaque._strict_block(
        tool_name="delegate_task",
        args={
            "goal": "[SMIT_SANITIZED_V1] Проверь FORM_A7.",
            "context": "Use only the supplied sanitized context and public information. Сохрани FORM_A7 без изменений.",
        },
    )
    assert allowed is None


def test_registered_schema_and_handler_support_auto_assignment_options():
    class Context:
        def register_tool(self, **definition):
            self.definition = definition

        def register_hook(self, *_args):
            pass

    ctx = Context()
    opaque.register(ctx)
    properties = ctx.definition["schema"]["parameters"]["properties"]
    assert "auto" in properties["language"]["enum"]
    assert properties["available_languages"]["items"]["enum"] == ["en", "fr", "ru"]
    result = json.loads(ctx.definition["handler"]({
        "action": "review",
        "entities": [{"type": "LOCALE"}],
        "language": "auto",
        "available_languages": ["ru"],
        "previous_language": "ru",
        "seed": 9,
    }))
    assert result["requested_language"] == "auto"
    assert result["language"] == "ru"


if __name__ == "__main__":
    test_transform_discards_real_entity_labels()
    test_builder_output_passes_guard_in_each_supported_language()
    test_strict_blocks_vietnamese_delegation()
    test_strict_allows_opaque_russian_delegation()
    test_registered_schema_and_handler_support_auto_assignment_options()
    print("ASSERTIONS_OK")