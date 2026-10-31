#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
gate="$source_dir/check_runtime_source.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
make_file() {
  mkdir -p "$(dirname "$1")"
  printf '%s\n' 'fixture-content' > "$1"
}
make_complete() {
  local root="$1"
  make_file "$root/rplay_watcher/__init__.py"
  make_file "$root/pyproject.toml"
  make_file "$root/extension/bridge.js"
  make_file "$root/extension/content.js"
  make_file "$root/extension/popup.js"
  make_file "$root/extension/options.js"
  mkdir -p "$root/tests"
}
assert_case() {
  local name="$1" expected_rc="$2" expected_state="$3" expected_present="$4"
  local root="$tmp/$name" rc
  mkdir -p "$root"
  case "$name" in
    empty) ;;
    bootstrap) make_file "$root/pyproject.toml" ;;
    runtime_partial) make_file "$root/extension/content.js" ;;
    empty_marker) mkdir -p "$root/rplay_watcher" ;;
    tests_only) mkdir -p "$root/tests" ;;
    no_tests) make_complete "$root"; rmdir "$root/tests" ;;
    empty_required) make_complete "$root"; : > "$root/extension/popup.js" ;;
    complete) make_complete "$root" ;;
    *) echo "Unknown fixture $name" >&2; exit 2 ;;
  esac
  : > "$tmp/output"
  : > "$tmp/summary"
  if GITHUB_OUTPUT="$tmp/output" GITHUB_STEP_SUMMARY="$tmp/summary" bash "$gate" "$root" > "$tmp/log" 2>&1; then
    rc=0
  else
    rc=$?
  fi
  if [[ "$rc" != "$expected_rc" ]] ||
     ! grep -Fxq "present=$expected_present" "$tmp/output" ||
     ! grep -Fxq "state=$expected_state" "$tmp/output" ||
     ! grep -Fq -- "- Source: **$expected_state**" "$tmp/summary"; then
    echo "FAIL $name: expected rc=$expected_rc state=$expected_state present=$expected_present, got rc=$rc" >&2
    cat "$tmp/output" "$tmp/summary" "$tmp/log" >&2
    exit 1
  fi
  echo "PASS: $name ($expected_state)"
}
assert_case empty 0 BOOTSTRAP_ONLY false
assert_case bootstrap 0 BOOTSTRAP_ONLY false
assert_case runtime_partial 1 PARTIAL_SOURCE false
assert_case empty_marker 1 PARTIAL_SOURCE false
assert_case tests_only 1 PARTIAL_SOURCE false
assert_case no_tests 1 PARTIAL_SOURCE false
assert_case empty_required 1 PARTIAL_SOURCE false
assert_case complete 0 COMPLETE_SOURCE true
echo "Runtime source gate fixtures: 8/8 PASS"
