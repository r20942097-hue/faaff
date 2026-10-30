#!/usr/bin/env bash
# Only run this script INSIDE 'unshare --user --net' invoked by the Python gate.
set -euo pipefail
[[ "$(readlink /proc/self/ns/net)" != "${GPT1_PARENT_NETNS:-}" ]] || exit 80
[[ -z "$(ip -4 route)" ]] || exit 81
[[ -z "$(ip -6 route)" ]] || exit 82
[[ "$(ip -o link show | wc -l)" == "1" ]] || exit 83
printf "%s\n" "GPT1_ISOLATION_PROVEN_BY_WRAPPER"
# The target suite and three JS modules are the only extra filesystem reads
# permitted to product code; Node's permission model disables networking.
export GPT1_PURE_MODULE_DIR="$GPT1_MODULE_DIR"
exec setpriv --reuid=1 --regid=1 --clear-groups \
  node --permission \
    --allow-fs-read="$GPT1_MODULE_DIR" \
    --allow-fs-read="$GPT1_TEST_SUITE" \
    "$GPT1_TEST_SUITE"
