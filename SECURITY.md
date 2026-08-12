# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately to the repository owner through GitHub's private vulnerability reporting feature when available. Do not open a public issue containing credentials, private payloads, exploit details against a live deployment, or user data.

## Security model

Worker Manager separates local route selection from delegated execution. Its public settings/activity/history APIs intentionally return allowlisted metadata only.

The included `smit-sanitization-guard` applies generic deterministic checks for the required marker/boundary, typed placeholders, leaf role, secrets, email addresses, private URLs/IPs, local paths, and selected business-language leakage patterns. Project-specific identity policies remain the installer's responsibility and are not shipped in this public package.

The plugin must never expose:

- API keys, tokens, passwords, cookies, or private keys;
- provider endpoint URLs or authentication headers;
- prompts, contexts, transcripts, tool output, or private logs;
- browser profiles, session storage, memory/profile stores, or production data;
- absolute local paths or private infrastructure identifiers.

## External providers

Treat any external inference provider as an external data processor. For profiles marked `external_sanitized`, Worker Manager requires an enabled handoff, an exact `[SMIT_SANITIZED_V1]` marker, non-empty sanitized context, and a fixed leaf profile.

Opaque handoff is semantic obfuscation, not encryption. Provider operators can read and correlate payloads sent to them. Do not send confidential or secret data.

## Local history

Worker history reads only bounded `manifest.json` metadata from Hermes' authoritative delegation live root. The Clear History action deletes only matching manifest files; it does not delete transcripts, logs, configuration, source trees, Docker images, or diagnostics.

## Installation

The included installers:

- write only under `HERMES_HOME`;
- back up existing plugin directories before replacement;
- do not modify credentials or provider configuration;
- enable plugins without granting built-in tool override;
- do not terminate running Hermes processes.

Review scripts before execution, especially when installing from a public network.

## Supported versions

This snapshot targets current Hermes Agent/Desktop builds that provide:

- `hermes plugins`;
- native Desktop disk plugins under `$HERMES_HOME/desktop-plugins/`;
- `@hermes/plugin-sdk` with `ModelCatalogMenu` and pane registration;
- scoped backend routes through `dashboard/plugin_api.py`.
