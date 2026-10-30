#!/usr/bin/env bash
# Disposable GitHub-hosted Ubuntu runner only. Synthetic MV3 fixture; no user extensions.
set -euo pipefail
[[ "$(uname -s)" == Linux ]] || { echo 'BLOCKED: Linux required'; exit 2; }
[[ "${RUNNER_ENVIRONMENT:-}" == 'github-hosted' ]] || { echo 'BLOCKED: github-hosted runner required'; exit 2; }
[[ "$(id -u)" != 0 ]] || { echo 'BLOCKED: must start unprivileged'; exit 2; }
command -v sudo >/dev/null
command -v unshare >/dev/null
command -v apparmor_parser >/dev/null
command -v python3 >/dev/null
command -v ip >/dev/null
BROWSER="$(command -v chromium || command -v chromium-browser)"
[[ -n "$BROWSER" ]] || { echo 'BLOCKED: system Chromium not found'; exit 2; }
PYTHON="$(command -v python3)"
CHROME_REAL="$(readlink -f "$BROWSER")"
PARENT_NS="$(readlink /proc/self/ns/net)"
RUNNER_USER="$(id -un)"
python3 - "$CHROME_REAL" <<'PY'
import pathlib, sys
b = pathlib.Path(sys.argv[1])
for part in (b, *b.parents):
    m = part.stat()
    if m.st_uid != 0 or m.st_mode & 0o022:
        raise SystemExit('BLOCKED: Chromium path is not root-owned or is writable by others')
if any(c in str(b) for c in ('"','\n','\r','{','}','*','?','[')):
    raise SystemExit('BLOCKED: unexpected browser executable path')
PY
# AppArmor adjustment on this disposable runner only; does not certify browser sandbox.
PROFILE="$(mktemp -t gpt1-synthetic-apparmor.XXXXXX)"
trap 'rm -f "$PROFILE"' EXIT
printf '#include <tunables/global>\nprofile gpt1_python_synthetic_chromium "%s" flags=(unconfined) {\n  userns,\n}\n' "$CHROME_REAL" > "$PROFILE"
sudo apparmor_parser -r "$PROFILE"
# Capture parent namespace before unshare, then drop root and run synthetic-only.
export GPT1_PARENT_NETNS="$PARENT_NS" GATE_PYTHON="$PYTHON" GATE_BROWSER="$CHROME_REAL" GATE_RUNNER="$RUNNER_USER"
sudo env PATH="$PATH" GPT1_PARENT_NETNS="$GPT1_PARENT_NETNS" GATE_PYTHON="$GATE_PYTHON" \
    GATE_BROWSER="$GATE_BROWSER" GATE_RUNNER="$GATE_RUNNER" unshare --net -- bash -c '
set -euo pipefail
ip link set lo up
exec sudo -u "$GATE_RUNNER" -H env PATH="$PATH" GPT1_PARENT_NETNS="$GPT1_PARENT_NETNS" \
    "$GATE_PYTHON" ai/isolated_extension_e2e.py --synthetic-only --browser-executable "$GATE_BROWSER" --json
'
