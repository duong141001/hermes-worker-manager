import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("plugin_api.py")
spec = importlib.util.spec_from_file_location("smit_worker_router_api", MODULE_PATH)
api = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = api
spec.loader.exec_module(api)


class PluginApiTests(unittest.TestCase):
    def base_config(self):
        return {
            "providers": {"smit-proxy": {"models": {"gpt-5.6-sol": {}, "kimi-k3": {}}}},
            "plugins": {},
            "delegation": {"profiles": {}},
        }

    def provider_rows(self):
        return [
            {"slug": "smit-proxy", "name": "SMIT", "models": ["gpt-5.6-sol"],
             "capabilities": {"gpt-5.6-sol": {"reasoning": True, "thinking": True, "fast": True}},
             "source": "external-sanitized", "secret": "must-not-leak"},
            {"slug": "other", "name": "Other", "models": ["other-model"],
             "capabilities": {"other-model": {"reasoning": False, "thinking": False, "fast": False}},
             "source": "built-in"},
        ]

    def test_provider_discovery_uses_picker_context_without_refresh_and_allowlists_rows(self):
        context = unittest.mock.Mock(**{
            "current_provider": "smit-proxy", "current_model": "gpt-5.6-sol",
            "current_base_url": "https://example.invalid", "user_providers": {},
            "custom_providers": [], "excluded_providers": [],
        })
        with patch("hermes_cli.inventory.load_picker_context", return_value=context) as load, patch(
            "hermes_cli.model_switch.list_authenticated_providers", return_value=self.provider_rows()
        ) as discover, patch.object(api, "_config", return_value=self.base_config()):
            result = api.get_settings()
        load.assert_called_once_with()
        self.assertFalse(discover.call_args.kwargs["refresh"])
        self.assertEqual(set(result["providers"][0]), {"slug", "name", "models", "capabilities"})
        self.assertEqual(set(result["providers"][0]["capabilities"]["gpt-5.6-sol"]), {"reasoning", "thinking", "fast"})

    def test_refresh_workers_refreshes_discovery_and_returns_all_surfaces(self):
        with patch.object(api, "_provider_rows", return_value=self.provider_rows()) as rows, patch.object(
            api, "get_settings", return_value={"provider": "smit-proxy"}
        ), patch.object(api, "get_activity", return_value={"active": 0, "workers": []}), patch.object(
            api, "get_history", return_value={"workers": []}
        ):
            result = api.refresh_workers()
        rows.assert_called_once_with(refresh=True)
        self.assertEqual(set(result), {"settings", "activity", "history"})

    def test_settings_preserve_profile_and_provider_controls_handoff(self):
        config = self.base_config()
        config["delegation"]["profiles"][api._DYNAMIC_PROFILE] = {"temperature": 0.2, "tools": ["x"]}
        with patch.object(api, "_config", return_value=config), patch.object(
            api, "_provider_rows", return_value=self.provider_rows()
        ), patch("hermes_cli.config.save_config"):
            result = api.save_settings(api.SettingsBody(
                capability="auto", language="fr", provider="smit-proxy", model="gpt-5.6-sol",
                reasoning="high", fast=True, handoff_enabled=False,
            ))
        profile = config["delegation"]["profiles"][api._DYNAMIC_PROFILE]
        self.assertEqual((profile["provider"], profile["model"]), ("smit-proxy", "gpt-5.6-sol"))
        self.assertEqual((profile["temperature"], profile["tools"]), (0.2, ["x"]))
        self.assertTrue(result["handoff_enabled"])
        self.assertTrue(result["handoff_locked"])
        self.assertEqual(result["language"], "fr")

    def test_other_provider_allows_handoff_false(self):
        config = self.base_config()
        with patch.object(api, "_config", return_value=config), patch.object(
            api, "_provider_rows", return_value=self.provider_rows()
        ), patch("hermes_cli.config.save_config"):
            result = api.save_settings(api.SettingsBody(
                capability="auto", language="en", provider="other", model="other-model",
                reasoning="none", fast=False, handoff_enabled=False,
            ))
        self.assertFalse(result["handoff_enabled"])
        self.assertFalse(result["handoff_locked"])

    def test_selected_probe_resolves_selected_provider_and_model(self):
        config = self.base_config()
        original = {
            "provider": "smit-proxy", "model": "gpt-5.6-sol",
            "reasoning_effort": "high", "nested": {"preserved": True},
        }
        config["delegation"]["profiles"][api._DYNAMIC_PROFILE] = original
        resolved = {
            "provider": "other", "model": "other-model",
            "base_url": "https://must-not-leak.invalid", "api_key": "must-not-leak",
            "headers": {"Authorization": "must-not-leak"},
        }
        with patch.object(api, "_config", return_value=config), patch(
            "tools.delegate_tool._resolve_delegation_credentials", return_value=resolved
        ) as resolver:
            result = api._probe("other", "other-model")
        expected = dict(original, provider="other", model="other-model")
        resolver.assert_called_once_with(expected, None)
        self.assertIsNot(resolver.call_args.args[0], original)
        self.assertEqual(config["delegation"]["profiles"][api._DYNAMIC_PROFILE], original)
        self.assertEqual(result, {"provider": "other", "model": "other-model", "ok": True})

    def test_selected_probe_response_is_allowlisted_and_error_is_bounded(self):
        config = self.base_config()
        config["delegation"]["profiles"][api._DYNAMIC_PROFILE] = {"base_url": "secret"}
        with patch.object(api, "_config", return_value=config), patch(
            "tools.delegate_tool._resolve_delegation_credentials",
            side_effect=ValueError("secret endpoint and credential details"),
        ):
            result = api._probe("other", "other-model")
        self.assertEqual(set(result), {"provider", "model", "ok", "error"})
        self.assertEqual(result["error"], "ValueError")
        self.assertNotIn("secret", str(result))

    def test_selected_probe_requires_matching_model_and_resolved_route(self):
        config = self.base_config()
        config["delegation"]["profiles"][api._DYNAMIC_PROFILE] = {}
        unsafe = {
            "provider": "other", "model": "wrong-model", "base_url": "secret",
            "api_key": "secret", "headers": {"secret": "secret"},
        }
        with patch.object(api, "_config", return_value=config), patch(
            "tools.delegate_tool._resolve_delegation_credentials", return_value=unsafe
        ):
            mismatch = api._probe("other", "other-model")
        self.assertEqual(mismatch, {"provider": "other", "model": "other-model", "ok": False})

        unsafe.update(model="other-model", provider=None, base_url=None, command=None)
        with patch.object(api, "_config", return_value=config), patch(
            "tools.delegate_tool._resolve_delegation_credentials", return_value=unsafe
        ):
            no_route = api._probe("other", "other-model")
        self.assertEqual(no_route, {"provider": "other", "model": "other-model", "ok": False})

    def test_history_clear_deletes_only_manifests_under_live_root(self):
        manifest_a = unittest.mock.Mock()
        manifest_b = unittest.mock.Mock()
        root = unittest.mock.Mock()
        root.rglob.return_value = [manifest_a, manifest_b]
        with patch.object(api, "_delegation_live_root", return_value=root):
            result = api.clear_history()
        root.rglob.assert_called_once_with("manifest.json")
        manifest_a.unlink.assert_called_once_with()
        manifest_b.unlink.assert_called_once_with()
        self.assertEqual(result, {"ok": True, "removed": 2, "workers": []})

    def test_settings_persist_thinking_off_and_fast_request_profile(self):
        config = self.base_config()
        with patch.object(api, "_config", return_value=config), patch.object(
            api, "_provider_rows", return_value=self.provider_rows()
        ), patch("hermes_cli.config.save_config") as save:
            result = api.save_settings(api.SettingsBody(
                capability="auto", language="ru", provider="smit-proxy", model="gpt-5.6-sol",
                reasoning="none", fast=True,
            ))
        profile = config["delegation"]["profiles"][api._DYNAMIC_PROFILE]
        self.assertEqual(profile["reasoning_effort"], "none")
        self.assertTrue(profile["fast"])
        self.assertEqual(result["reasoning"], "none")
        self.assertTrue(result["fast"])
        save.assert_called_once_with(config)

    def test_settings_persist_auto_random_language(self):
        config = self.base_config()
        with patch.object(api, "_config", return_value=config), patch.object(
            api, "_model_options", return_value={
                "gpt-5.6-sol": {"reasoning": True, "fast": True},
                "kimi-k3": {"reasoning": True, "fast": False},
            }
        ), patch("hermes_cli.config.save_config") as save:
            result = api.save_settings(api.SettingsBody(
                capability="auto", language="auto", provider="smit-proxy", model="gpt-5.6-sol",
                reasoning="high", fast=False,
            ))
        entry = config["plugins"]["entries"]["smit-worker-router"]
        self.assertEqual(entry["default_language"], "auto")
        self.assertEqual(result["language"], "auto")
        save.assert_called_once_with(config)

    def test_settings_reject_fast_for_unsupported_model(self):
        config = self.base_config()
        with patch.object(api, "_config", return_value=config), patch.object(
            api, "_model_options", return_value={"kimi-k3": {"reasoning": True, "fast": False}}
        ):
            with self.assertRaises(api.HTTPException) as raised:
                api.save_settings(api.SettingsBody(
                    capability="auto", language="ru", provider="smit-proxy", model="kimi-k3",
                    reasoning="high", fast=True,
                ))
        self.assertEqual(raised.exception.status_code, 400)

    def test_settings_return_model_capabilities_and_real_options(self):
        config = self.base_config()
        entry = config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("smit-worker-router", {})
        entry.update(default_capability="auto", default_model="gpt-5.6-sol", default_reasoning="high", default_fast=True)
        with patch.object(api, "_config", return_value=config), patch.object(
            api, "_model_options", return_value={
                "gpt-5.6-sol": {"reasoning": True, "fast": True},
                "kimi-k3": {"reasoning": True, "fast": False},
            }
        ):
            result = api.get_settings()
        self.assertEqual(result["reasoning_options"], ["minimal", "low", "medium", "high", "xhigh", "max", "ultra"])
        self.assertTrue(result["model_options"]["gpt-5.6-sol"]["fast"])
        self.assertFalse(result["model_options"]["kimi-k3"]["fast"])
        self.assertTrue(result["fast"])
        self.assertEqual(result["languages"], ["auto", "en", "fr", "ru"])

    def test_activity_returns_only_active_smit_workers_with_safe_task_label(self):
        active = [
            {
                "subagent_id": "child-live", "status": "running", "model": "gpt-5.6-sol",
                "profile": "smit-gpt-5-6-sol", "tool_count": 2, "last_tool": "read_file",
                "started_at": 123, "reasoning_effort": "high", "fast": True,
                "metadata": {"locale": "fr"},
                "goal": "[SMIT_SANITIZED_V1] Проверить FORM_A7 и вернуть критерии.",
            },
            {
                "subagent_id": "internal", "status": "running", "model": "private-model",
                "profile": "", "goal": "private task must not appear",
            },
        ]
        with patch.object(api, "_active_workers", return_value=active):
            result = api.get_activity()
        self.assertEqual(result["active"], 1)
        self.assertEqual(len(result["workers"]), 1)
        row = result["workers"][0]
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["task_label"], "Проверить FORM_A7 и вернуть критерии.")
        self.assertEqual(row["reasoning_effort"], "high")
        self.assertTrue(row["fast"])
        self.assertEqual(row["locale"], "fr")
        self.assertNotIn("goal", row)

    def test_activity_includes_bounded_usage_and_duration_from_registry(self):
        active = [{
            "subagent_id": "live", "profile": "smit-worker", "started_at": 1,
            "input_tokens": "12", "output_tokens": 7, "total_tokens": -9,
            "api_calls": 10 ** 30, "duration_seconds": 3.8,
        }]
        with patch.object(api, "_active_workers", return_value=active):
            row = api.get_activity()["workers"][0]
        self.assertEqual(row["input_tokens"], 12)
        self.assertEqual(row["output_tokens"], 7)
        self.assertEqual(row["total_tokens"], 0)
        self.assertEqual(row["api_calls"], api._MAX_SAFE_INTEGER)
        self.assertEqual(row["duration_seconds"], 3)

    def test_history_flattens_real_nested_manifest_and_uses_live_root(self):
        manifest = {
            "delegation_id": "delegation-real",
            "started": 1,
            "completed": 2,
            "task_count": 2,
            "tasks": [
                {
                    "profile": "smit-worker", "status": "completed",
                    "model": "gpt-5.6-sol", "provider": "smit-proxy",
                    "reasoning_effort": "high", "fast": True,
                    "locale": "ru", "goal": "[SMIT_SANITIZED_V1] safe task",
                    "duration_seconds": 60, "api_calls": 2,
                    "tokens": {"input": 11, "output": 7, "total": 18},
                    "log": "secret.log", "path": "/secret",
                    "context": "secret", "transcript": "secret",
                    "tool_output": "secret",
                },
                {"profile": "internal", "tokens": {"total": 999}},
            ],
        }
        fake_root = unittest.mock.MagicMock()
        fake_root.rglob.return_value = ["only/manifest.json"]
        with patch("tools.delegation_live_log.live_transcript_root", return_value=fake_root) as live_root, patch.object(
            api, "_read_manifest", return_value=manifest
        ):
            result = api.get_history()
        live_root.assert_called_once_with()
        self.assertEqual(len(result["workers"]), 1)
        row = result["workers"][0]
        self.assertEqual(row["id"], "delegation-real:0")
        self.assertEqual(row["delegation_id"], "delegation-real")
        self.assertEqual(row["started_at"], manifest["started"])
        self.assertEqual(row["completed_at"], manifest["completed"])
        self.assertEqual((row["input_tokens"], row["output_tokens"], row["total_tokens"]), (11, 7, 18))
        self.assertEqual(row["task_label"], "safe task")
        self.assertTrue(set(row).isdisjoint({"log", "path", "context", "transcript", "tool_output"}))

    def test_history_is_sanitized_filtered_sorted_and_limited(self):
        manifests = []
        for index in range(55):
            manifests.append({
                "delegation_id": f"delegation-{index}", "started": index,
                "completed": index + 100, "task_count": 1, "tasks": [{
                    "status": "completed", "model": "gpt-5.6-sol", "profile": "smit-worker",
                    "provider": "smit-proxy", "reasoning_effort": "high", "fast": bool(index % 2),
                    "locale": "ru", "task_label": f"task {index}", "duration_seconds": index,
                    "api_calls": 1, "tokens": {"input": 2, "output": 3, "total": 5},
                    "cost_usd": 0.01, "prompt": "secret", "context": "secret",
                    "transcript": "secret", "tool_output": "secret", "path": "/secret",
                }],
            })
        manifests.extend([{"profile": "internal", "completed_at": 9999}, None, "bad"])
        fake_root = unittest.mock.MagicMock()
        fake_root.rglob.return_value = [f"p-{i}" for i in range(len(manifests))]
        with patch.object(api, "_delegation_live_root", return_value=fake_root), patch.object(
            api, "_read_manifest", side_effect=manifests
        ):
            result = api.get_history()
        fake_root.rglob.assert_called_once_with("manifest.json")
        self.assertEqual(len(result["workers"]), 50)
        self.assertEqual(result["workers"][0]["id"], "delegation-54:0")
        self.assertEqual(result["workers"][-1]["id"], "delegation-5:0")
        allowed = {
            "id", "delegation_id", "status", "model", "profile", "provider",
            "reasoning_effort", "fast", "locale", "task_label", "started_at",
            "completed_at", "duration_seconds", "api_calls", "input_tokens",
            "output_tokens", "total_tokens", "cost_usd",
        }
        self.assertTrue(all(set(row) == allowed for row in result["workers"]))

    def test_history_defensively_skips_bad_manifest_reads(self):
        fake_root = unittest.mock.MagicMock()
        fake_root.rglob.return_value = ["bad", "good"]
        good = {"delegation_id": "ok", "started": 1, "completed": 2, "task_count": 1, "tasks": [{"profile": "smit-worker"}]}
        with patch.object(api, "_delegation_live_root", return_value=fake_root), patch.object(
            api, "_read_manifest", side_effect=[ValueError("bad json"), good]
        ):
            result = api.get_history()
        self.assertEqual([row["id"] for row in result["workers"]], ["ok:0"])

    def test_activity_is_empty_when_no_worker_is_called(self):
        with patch.object(api, "_active_workers", return_value=[]):
            self.assertEqual(api.get_activity(), {"active": 0, "workers": []})

    def test_selected_probe_calls_only_selected_model(self):
        called = []
        config = self.base_config()
        with patch.object(api, "_config", return_value=config), patch.object(
            api, "_probe", side_effect=lambda provider, model: called.append((provider, model)) or {"model": model, "ok": True}
        ):
            result = api.test_selected_model(api.ProbeBody(provider="smit-proxy", model="gpt-5.6-sol"))
        self.assertEqual(called, [("smit-proxy", "gpt-5.6-sol")])
        self.assertTrue(result["ok"])

    def test_selected_probe_rejects_unregistered_model(self):
        with patch.object(api, "_config", return_value=self.base_config()):
            with self.assertRaises(api.HTTPException) as raised:
                api.test_selected_model(api.ProbeBody(model="unknown"))
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
