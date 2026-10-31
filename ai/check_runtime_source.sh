#!/usr/bin/env bash
set -euo pipefail
repo_root="${1:-.}"
if [[ ! -d "$repo_root" ]]; then echo "::error::Runtime source root is not a directory: $repo_root"; exit 1; fi
cd "$repo_root"
required_files=(rplay_watcher/__init__.py pyproject.toml extension/bridge.js extension/content.js extension/popup.js extension/options.js)
runtime_markers=(rplay_watcher extension tests)
runtime_seen=false
for marker in "${runtime_markers[@]}"; do
  if [[ -e "$marker" ]]; then runtime_seen=true; break; fi
done
missing=()
for path in "${required_files[@]}"; do
  if [[ ! -f "$path" || ! -s "$path" ]]; then missing+=("$path (missing/empty)"); fi
done
if [[ ! -d tests ]]; then missing+=("tests/ (directory missing)"); fi
if [[ "$runtime_seen" == false ]]; then
  state=BOOTSTRAP_ONLY; present=false; test_state="NOT_RUN (runtime source absent)"; result=0
elif (( ${#missing[@]} > 0 )); then
  state=PARTIAL_SOURCE; present=false; test_state="BLOCKED (missing/empty required source)"; result=1
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
    if [[ "$state" == PARTIAL_SOURCE ]]; then printf -- '- Missing/empty: %s\n' "${missing[@]}"; fi
  } >> "$GITHUB_STEP_SUMMARY"
fi
if [[ "$state" == BOOTSTRAP_ONLY ]]; then
  echo "::notice::Runtime source absent; product tests NOT_RUN."
elif [[ "$state" == PARTIAL_SOURCE ]]; then
  printf '::error::Partial runtime source: %s\n' "${missing[*]}"
fi
exit "$result"
