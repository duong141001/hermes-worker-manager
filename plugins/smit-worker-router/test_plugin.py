import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


_TEST_DIR = Path(__file__).resolve().parent
MODULE_PATH = _TEST_DIR / "router.py"
if not MODULE_PATH.exists():
    MODULE_PATH = _TEST_DIR / "__init__.py"
spec = importlib.util.spec_from_file_location("smit_worker_router", MODULE_PATH)
router = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = router
spec.loader.exec_module(router)


class RouterTests(unittest.TestCase):
    def configured_settings(self, config):
        hermes_cli = types.ModuleType("hermes_cli")
        config_module = types.ModuleType("hermes_cli.config")
        config_module.load_config_readonly = lambda: config
        hermes_cli.config = config_module
        with patch.dict(
            sys.modules,
            {"hermes_cli": hermes_cli, "hermes_cli.config": config_module},
        ):
            return router._configured_settings()

    def test_external_stale_false_forces_effective_handoff_enabled(self):
        config = {
            "plugins": {
                "entries": {
                    "smit-worker-router": {
                        "default_capability": "auto",
                        "provider": "smit-proxy",
                        "model": "gpt-5.6-sol",
                        "reasoning": "high",
                        "handoff_enabled": False,
                        "trust_class": "external_sanitized",
                    }
                }
            }
        }

        self.assertEqual(
            self.configured_settings(config),
            ("auto", "smit-proxy", "gpt-5.6-sol", "high", True, "external_sanitized"),
        )

    def test_ordinary_stale_false_preserves_handoff_disabled(self):
        config = {
            "plugins": {
                "entries": {
                    "smit-worker-router": {
                        "default_capability": "auto",
                        "provider": "cockpit-proxy",
                        "model": "gpt-5.6-sol",
                        "reasoning": "high",
                        "handoff_enabled": False,
                        "trust_class": "private",
                    }
                }
            }
        }

        self.assertEqual(
            self.configured_settings(config),
            ("auto", "cockpit-proxy", "gpt-5.6-sol", "high", False, "private"),
        )

    def test_capability_allowlist_includes_auto(self):
        capabilities = router.available_capabilities()
        self.assertEqual(capabilities["auto"], "Auto")
        self.assertIn("frontend_code", capabilities)
        self.assertIn("architecture_review", capabilities)

    def test_requires_goal(self):
        with patch.object(
            router,
            "_configured_settings",
            return_value=("auto", "cockpit-proxy", "gpt-5.6-sol", "high", False, "private"),
        ):
            result = json.loads(router.run_worker("auto", "", "context"))
        self.assertEqual(result["error"], "goal is required")

    def test_external_dispatch_is_fixed_and_metadata_authoritative(self):
        from tools import delegate_tool

        captured = {}

        def fake_delegate_task(**kwargs):
            captured.update(kwargs)
            return json.dumps({
                "status": "dispatched",
                "capability": "spoofed-capability",
                "profile": "spoofed-profile",
                "provider": "spoofed-provider",
                "model": "spoofed-model",
            })

        parent = object()
        with patch.object(delegate_tool, "delegate_task", side_effect=fake_delegate_task), patch.object(
            router,
            "_configured_settings",
            return_value=("auto", "smit-proxy", "gpt-5.6-sol", "high", True, "external_sanitized"),
        ):
            result = json.loads(router.run_worker(
                "attacker-capability",
                "[SMIT_SANITIZED_V1]",
                "Use only the supplied sanitized context and public information.",
                parent_agent=parent,
                role="attacker-role",
                profile="attacker-profile",
            ))
        self.assertEqual(captured, {
            "goal": "[SMIT_SANITIZED_V1]",
            "context": "Use only the supplied sanitized context and public information.",
            "role": "leaf",
            "profile": "smit-router-selected",
            "parent_agent": parent,
        })
        self.assertEqual(result["capability"], "auto")
        self.assertEqual(result["profile"], "smit-router-selected")
        self.assertEqual(result["provider"], "smit-proxy")
        self.assertEqual(result["model"], "gpt-5.6-sol")

    def test_legacy_run_smit_worker_is_alias(self):
        self.assertIs(router.run_smit_worker, router.run_worker)

    def test_rejects_external_sanitized_when_not_enabled(self):
        with patch.object(
            router,
            "_configured_settings",
            return_value=("auto", "smit-proxy", "gpt-5.6-sol", "high", False, "external_sanitized"),
        ):
            result = json.loads(router.run_worker(
                "auto",
                "[SMIT_SANITIZED_V1] Проверь FORM_A7.",
                "Use only the supplied sanitized context and public information.",
            ))
        self.assertIn("not enabled", result["error"])

    def test_requires_external_sanitized_marker(self):
        with patch.object(
            router,
            "_configured_settings",
            return_value=("auto", "smit-proxy", "gpt-5.6-sol", "high", True, "external_sanitized"),
        ):
            result = json.loads(router.run_worker(
                "auto", "Проверь FORM_A7.", "Use only supplied sanitized context."
            ))
        self.assertIn("[SMIT_SANITIZED_V1]", result["error"])

    def test_requires_external_sanitized_context(self):
        with patch.object(
            router,
            "_configured_settings",
            return_value=("auto", "smit-proxy", "gpt-5.6-sol", "high", True, "external_sanitized"),
        ):
            result = json.loads(router.run_worker(
                "auto", "[SMIT_SANITIZED_V1] Проверь FORM_A7.", ""
            ))
        self.assertIn("context is required", result["error"])

    def test_ordinary_handoff_disabled_uses_router_selected_identity(self):
        from tools import delegate_tool

        captured = {}
        parent = object()

        def fake_delegate_task(**kwargs):
            captured.update(kwargs)
            return json.dumps({"status": "ok"})

        with patch.object(delegate_tool, "delegate_task", side_effect=fake_delegate_task), patch.object(
            router,
            "_configured_settings",
            return_value=("auto", "cockpit-proxy", "gpt-5.6-sol", "high", False, "private"),
        ):
            result = json.loads(router.run_worker(
                "attacker",
                "ordinary safe goal",
                "",
                parent_agent=parent,
                role="attacker",
                profile="attacker",
            ))

        self.assertEqual(
            captured,
            {
                "goal": "ordinary safe goal",
                "context": "",
                "role": "leaf",
                "profile": "smit-router-selected",
                "parent_agent": parent,
            },
        )
        self.assertEqual(result["provider"], "cockpit-proxy")
        self.assertEqual(result["model"], "gpt-5.6-sol")
        self.assertEqual(result["profile"], "smit-router-selected")
        self.assertEqual(result["capability"], "auto")

    def test_ordinary_handoff_enabled_requires_context(self):
        with patch.object(
            router,
            "_configured_settings",
            return_value=("auto", "cockpit-proxy", "gpt-5.6-sol", "high", True, "private"),
        ):
            result = json.loads(router.run_worker("attacker", "ordinary safe goal", ""))

        self.assertIn("context is required", result["error"])

    def test_registers_primary_and_legacy_tools(self):
        class Context:
            def __init__(self):
                self.tools = []

            def register_tool(self, **tool):
                self.tools.append(tool)

        ctx = Context()
        router.register(ctx)
        self.assertEqual([tool["name"] for tool in ctx.tools], ["run_worker", "run_smit_worker"])

    def test_plugin_manifest_lists_both_tools(self):
        manifest = Path(__file__).with_name("plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("  - run_worker\n", manifest)
        self.assertIn("  - run_smit_worker\n", manifest)


if __name__ == "__main__":
    unittest.main()
