# Hermes Worker Manager

A provider-aware subagent manager for [Hermes Agent](https://github.com/NousResearch/hermes-agent) and Hermes Desktop.

Worker Manager adds a compact native model picker, provider/model discovery, safe handoff controls, selected-profile validation, live worker activity, token usage, and persisted worker history. The settings surface and monitor are separate Hermes Desktop panes.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- Uses Hermes' authenticated provider profiles and per-model capability metadata.
- Reuses the native Hermes `ModelCatalogMenu` used by the chat composer.
- Keeps the settings pane compact: capability, provider, refresh icon, model picker, handoff, and profile test.
- Shows activity, token/API usage, duration, and history in a separate **Worker Monitor** pane.
- Preserves compatibility IDs: `smit-worker-router`, `smit-router-selected`, `run_worker`, and `run_smit_worker`.
- Supports ordinary providers and fail-closed `external_sanitized` routes.
- Includes an optional local opaque-handoff builder with deterministic EN/FR/RU assignment and a fail-closed sanitization guard.
- Never returns provider credentials, endpoint URLs, prompts, contexts, transcripts, logs, or local paths from its public API.

## Requirements

- A current Hermes Agent installation with the native Desktop Plugin SDK.
- Python 3.11+ and Node.js 20+ for running the included tests.
- At least one authenticated Hermes provider profile.
- Git for cloning this repository.

## Quick install

Clone the repository, then run the installer for your platform.

### Windows PowerShell

```powershell
git clone https://github.com/duong141001/hermes-worker-manager.git
cd hermes-worker-manager
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

### Linux, macOS, or WSL

```bash
git clone https://github.com/duong141001/hermes-worker-manager.git
cd hermes-worker-manager
bash scripts/install.sh
```

The installer:

1. Resolves `HERMES_HOME` (default: `~/.hermes`).
2. Backs up any existing copies under `$HERMES_HOME/backups/`.
3. Installs three agent plugins and one Desktop plugin.
4. Enables the agent plugins without granting built-in tool override.
5. Prints the restart commands; it does not terminate a running Hermes session.

After installation:

```bash
hermes gateway restart
```

Then restart Hermes Desktop, or use the command palette action **Reload desktop plugins**. New Desktop plugin files are normally discovered automatically within a few seconds.

For a detailed Vietnamese guide, see [INSTALL.vi.md](INSTALL.vi.md).

## Manual install

Hermes supports Git subdirectory installs for native agent plugins:

```bash
hermes plugins install duong141001/hermes-worker-manager/plugins/smit-worker-router --enable
hermes plugins install duong141001/hermes-worker-manager/plugins/smit-opaque-handoff --enable
hermes plugins install duong141001/hermes-worker-manager/plugins/smit-sanitization-guard --enable
```

Install the Desktop plugin separately because native Desktop plugins use a different on-disk SDK:

```text
Copy desktop-plugins/smit-worker-router/plugin.js
  to $HERMES_HOME/desktop-plugins/smit-worker-router/plugin.js
```

Hermes' official plugin locations are:

```text
$HERMES_HOME/plugins/<plugin-id>/plugin.yaml
$HERMES_HOME/plugins/<plugin-id>/__init__.py
$HERMES_HOME/desktop-plugins/<plugin-id>/plugin.js
```

## First-run setup

1. Open the **Worker Manager** pane in Hermes Desktop.
2. Choose an authenticated provider.
3. Click the model trigger and select a model from the native Hermes catalog.
4. Configure reasoning/Fast options supported by that model.
5. Choose whether handoff is enabled. External-sanitized profiles are always locked on.
6. Click **Test selected worker profile**.
7. Open the separate **Worker Monitor** pane for activity and history.

Worker Manager persists the selected route in the dynamic Hermes delegation profile:

```text
smit-router-selected
```

It updates only bounded routing fields such as provider, model, reasoning, and Fast. Existing sandbox, workdir, allowlist, role, resource, and security settings are preserved.

## Optional Docker isolation

This repository does not silently create a Docker policy for public users. Configure `smit-router-selected` using Hermes' delegation settings if you want Docker isolation. A hardened profile can include:

```yaml
delegation:
  profiles:
    smit-router-selected:
      role: leaf
      docker_sandbox: true
      allowed_toolsets:
        - file
        - terminal
      max_iterations: 22
      trust_class: external_sanitized
      # Set provider/model/workdir/source_allowlist for your own environment.
```

Do not publish your real `workdir`, source allowlist, provider endpoint, API key, or credentials.

## External-sanitized handoff

For a provider or profile classified as external-sanitized, `run_worker` fails closed unless:

- handoff is enabled;
- the goal starts with `[SMIT_SANITIZED_V1]`;
- context is non-empty and sanitized;
- routing remains fixed to `role=leaf` and `profile=smit-router-selected`.

Use `prepare_smit_handoff` to create an abstract EN/FR/RU payload from typed entity placeholders and uppercase relation labels. It is semantic obfuscation, not encryption. Provider operators can still read payloads sent to them.

## Tests

From the repository root:

```bash
python -m unittest -q plugins/smit-worker-router/test_plugin.py
python -m unittest -q plugins/smit-worker-router/dashboard/test_plugin_api.py
python -m unittest -q plugins/smit-opaque-handoff/test_plugin.py
python -m unittest -q plugins/smit-opaque-handoff/test_language_assignment.py
node --check desktop-plugins/smit-worker-router/plugin.js
node --test desktop-plugins/smit-worker-router/test_plugin_ui.mjs
```

The published snapshot passed 68 Worker Manager tests before packaging, plus the opaque-handoff test suites.

## Repository layout

```text
plugins/
  smit-worker-router/       Agent tool router + scoped backend API
  smit-opaque-handoff/      Optional local sanitized-handoff builder/hook
  smit-sanitization-guard/  Fail-closed delegation boundary validator
desktop-plugins/
  smit-worker-router/       Native Hermes Desktop panes
scripts/
  install.ps1               Windows installer
  install.sh                Linux/macOS/WSL installer
```

## Updating

```bash
cd hermes-worker-manager
git pull --ff-only
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1  # Windows
# or
bash scripts/install.sh                                         # Linux/macOS/WSL
```

The installer backs up the previous installed copies on every run.

## Security

Read [SECURITY.md](SECURITY.md) before connecting an external provider. Never commit Hermes `config.yaml`, `.env`, provider credentials, browser profiles, delegation logs, manifests, session transcripts, memories, or production data.

## Compatibility

The public name is **Worker Manager**. Internal `smit-*` IDs are intentionally retained for migration compatibility with existing Hermes profiles and history.

## License

Licensed under the [MIT License](LICENSE). Copyright © 2026 duong141001.

## Upstream

Hermes Agent and Hermes Desktop are developed by [Nous Research](https://github.com/NousResearch/hermes-agent). This repository is an independent plugin package and is not an official Nous Research release.
