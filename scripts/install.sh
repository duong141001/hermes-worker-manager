#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"
backup_root="$hermes_home/backups/hermes-worker-manager-$(date +%Y%m%d-%H%M%S)"
skip_enable="${SKIP_ENABLE:-0}"

install_plugin_files() {
  local source_root="$1"
  local target_root="$2"
  shift 2
  local files=("$@")

  if [[ ! -d "$source_root" ]]; then
    printf 'Missing source directory: %s\n' "$source_root" >&2
    exit 1
  fi

  local relative
  for relative in "${files[@]}"; do
    if [[ ! -f "$source_root/$relative" ]]; then
      printf 'Missing source file: %s\n' "$source_root/$relative" >&2
      exit 1
    fi
  done

  if [[ -e "$target_root" ]]; then
    local relative_target="${target_root#"$hermes_home"/}"
    local backup_target="$backup_root/$relative_target"
    mkdir -p "$(dirname "$backup_target")"
    cp -a "$target_root" "$backup_target"
    rm -rf -- "$target_root"
  fi

  mkdir -p "$target_root"
  for relative in "${files[@]}"; do
    mkdir -p "$target_root/$(dirname "$relative")"
    cp "$source_root/$relative" "$target_root/$relative"
  done
}

install_plugin_files \
  "$repo_root/plugins/smit-worker-router" \
  "$hermes_home/plugins/smit-worker-router" \
  '__init__.py' 'plugin.yaml' 'dashboard/manifest.json' 'dashboard/plugin_api.py'

install_plugin_files \
  "$repo_root/plugins/smit-opaque-handoff" \
  "$hermes_home/plugins/smit-opaque-handoff" \
  '__init__.py' 'plugin.yaml'

install_plugin_files \
  "$repo_root/plugins/smit-sanitization-guard" \
  "$hermes_home/plugins/smit-sanitization-guard" \
  '__init__.py' 'plugin.yaml'

install_plugin_files \
  "$repo_root/desktop-plugins/smit-worker-router" \
  "$hermes_home/desktop-plugins/smit-worker-router" \
  'plugin.js'

if [[ "$skip_enable" != '1' ]]; then
  if command -v hermes >/dev/null 2>&1; then
    hermes plugins enable --no-allow-tool-override smit-worker-router
    hermes plugins enable --no-allow-tool-override smit-opaque-handoff
    hermes plugins enable --no-allow-tool-override smit-sanitization-guard
  else
    printf 'Warning: Hermes CLI was not found on PATH. Enable the plugins manually later.\n' >&2
  fi
fi

printf '\nHermes Worker Manager installed.\n'
printf 'HERMES_HOME: %s\n' "$hermes_home"
if [[ -d "$backup_root" ]]; then
  printf 'Backup: %s\n' "$backup_root"
fi
printf '\nNext steps:\n'
printf '  Restart the Hermes gateway from a separate shell.\n'
printf '  Restart Hermes Desktop, or use Command Palette -> Reload desktop plugins.\n'
printf '  Open the Worker Manager and Worker Monitor panes.\n\n'
printf 'The installer did not change provider credentials, endpoints, or delegation sandbox policy.\n'
