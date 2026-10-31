#!/usr/bin/env bash
set -euo pipefail
repo_root="${1:-.}"
if [[ ! -d "$repo_root" || -L "$repo_root" ]]; then
  echo "::error::Runtime source root must be a real directory: $repo_root"
  exit 1
fi
cd "$repo_root"
required_files=(rplay_watcher/__init__.py pyproject.toml extension/bridge.js extension/content.js extension/popup.js extension/options.js)
required_dirs=(rplay_watcher extension tests)
runtime_markers=(rplay_watcher extension tests)
runtime_seen=false
for marker in "${runtime_markers[@]}"; do
  if [[ -e "$marker" || -L "$marker" ]]; then runtime_seen=true; break; fi
done
# A symlinked package manifest must not pass as an ordinary bootstrap placeholder.
if [[ -L pyproject.toml ]]; then runtime_seen=true; fi
missing=()
for path in "${required_files[@]}"; do
  if [[ -L "$path" || ! -f "$path" || ! -s "$path" ]]; then
    missing+=("$path (missing/empty/symlink)")
  fi
done
for path in "${required_dirs[@]}"; do
  if [[ -L "$path" || ! -d "$path" ]]; then
    missing+=("$path/ (missing/not-directory/symlink)")
  fi
done
if [[ "$runtime_seen" == false ]]; then
  state=BOOTSTRAP_ONLY; present=false; test_state="NOT_RUN (runtime source absent)"; result=0
elif (( ${#missing[@]} > 0 )); then
  state=PARTIAL_SOURCE; present=false; test_state="BLOCKED (missing/empty/symlinked required source)"; result=1
else
  state=COMPLETE_SOURCE; present=true; test_state="SCHEDULED (separate test results required)"; result=0
fi
echo "Runtime source gate: $state; product tests: $test_state"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'present=%s\nstate=%s\n' "$present" "$state" >> "$GITHUB_OUTPUT"
fi
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "### Runtime source gate"
    printf -- '- Source: **%s**\n' "$state"
    printf -- '- Product tests: **%s**\n' "$test_state"
    if [[ "$state" == PARTIAL_SOURCE ]]; then printf -- '- Missing/empty/symlinked: %s\n' "${missing[@]}"; fi
  } >> "$GITHUB_STEP_SUMMARY"
fi
if [[ "$state" == BOOTSTRAP_ONLY ]]; then
  echo "::notice::Runtime source absent; product tests NOT_RUN."
elif [[ "$state" == PARTIAL_SOURCE ]]; then
  printf '::error::Partial runtime source: %s\n' "${missing[*]}"
fi
exit "$result"
