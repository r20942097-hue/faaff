#!/usr/bin/env python3
"""Agent-Reach v1.6 smoke checks. No setup, login, cookies or private profiles.

Runs on an isolated GitHub Actions runner, with a fresh HOME and no auth tokens.
Public network probes are reported separately; transient upstream failures are
BLOCKED and do not masquerade as a product PASS.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

EXPECTED_DEFAULTS = frozenset(("web", "github", "youtube", "bilibili", "v2ex"))
STATES = frozenset((
    "not_added", "needs_setup", "needs_login", "cooldown", "needs_user_action",
    "broken", "unverified", "search_ready", "ready",
))
ALLOWED_PUBLIC_ERRORS = frozenset((
    "NEED_SETUP", "NEED_LOGIN", "UPSTREAM_BROKEN", "TIMEOUT", "RATE_LIMITED",
    "PLATFORM_BLOCKED", "NOT_FOUND",
))


def run(args: list[str], home: Path, timeout: int = 30) -> tuple[int, dict]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    # These are not required for the anonymous public checks and MUST NOT leak.
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN",
                "GIT_ASKPASS", "SSH_ASKPASS", "TWITTER_AUTH_TOKEN", "TWITTER_CT0"):
        env.pop(key, None)
    try:
        p = subprocess.run([os.environ.get("AGENT_REACH_TEST_BINARY", "agent-reach"), *args], env=env,
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout,
                           encoding="utf-8", errors="replace", check=False)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError("CLI timed out: " + args[0]) from exc
    if len(p.stdout) > 2_000_000:
        raise AssertionError("CLI response too large: " + args[0])
    try:
        response = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError("CLI did not return a single JSON response: " + args[0]) from exc
    if not isinstance(response, dict) or response.get("schema_version") != 1:
        raise AssertionError("Wrong CLI response schema: " + args[0])
    if not isinstance(response.get("ok"), bool):
        raise AssertionError("CLI response lacks an ok flag: " + args[0])
    if p.returncode not in (0, 1) or (p.returncode == 0) != response["ok"]:
        raise AssertionError("Exit status and JSON ok disagree: " + args[0])
    return p.returncode, response


def local_checks(home: Path) -> None:
    rc, version = run(["version"], home)
    assert rc == 0 and version.get("action") == "version"
    assert version.get("result", {}).get("version") == "1.6.0"
    print("PASS: pinned Agent-Reach v1.6.0 returned its v1 JSON version envelope")

    rc, registry = run(["channels"], home)
    assert rc == 0 and isinstance(registry.get("channels"), list)
    channels = registry["channels"]
    names = [x.get("name") for x in channels]
    assert len(names) == len(set(names)) and EXPECTED_DEFAULTS.issubset(names)
    for ch in channels:
        assert ch.get("level") in ("default", "optional", "experimental")
        assert isinstance(ch.get("actions"), list)
        for action in ch["actions"]:
            assert action.get("name") and isinstance(action.get("backends"), list)
    print(f"PASS: {len(channels)} declared channels and core public-channel action schemas")

    rc, doctor = run(["doctor"], home, timeout=40)
    assert rc == 0 and doctor.get("action") == "doctor"
    result = doctor.get("result")
    assert isinstance(result, dict) and result.get("version") == "1.6.0"
    observed = result.get("channels")
    assert isinstance(observed, list) and len(observed) == len(channels)
    assert {x.get("channel") for x in observed} == set(names)
    assert all(x.get("status") in STATES for x in observed)
    # The doctor has not tested the network. Never call a channel ready just
    # because its implementation exists or its local binaries are installed.
    statuses = {}
    for ch in observed:
        statuses[ch["status"]] = statuses.get(ch["status"], 0) + 1
    print(f"PASS: offline doctor parsed (status counts: {json.dumps(statuses, sort_keys=True)})")

    rc, bad = run(["github", "nonexistent-smoke-action"], home)
    assert rc == 1 and bad.get("ok") is False
    assert (bad.get("error") or {}).get("code") == "BAD_INPUT"
    print("PASS: invalid GitHub action rejected without contacting upstream")
    rc, skill = run(["skill"], home)
    assert rc == 0 and skill.get("action") == "skill"
    assert isinstance(skill.get("result"), dict)
    print("PASS: skill installation inventory readable without modifying agent configurations")

    assert not (home / ".agent-reach" / "state.json").exists(), (
        "Read-only CLI tests must not create an Agent-Reach state ledger"
    )
    print("PASS: local read-only checks made no setup or channel-state mutations")

    # These inputs must be rejected by the real CLI *before* any outbound fetch.
    # Use another disposable HOME because failed backend calls can record
    # transient error/cooldown information even though no setup took place.
    reject_home = home / "untrusted-url-negative-paths"
    unsafe_urls = (
        "http://127.0.0.1:80/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/private",
        "http://localhost/",
        "file:///etc/passwd",
        "https://example.com@127.0.0.1/",
        "https://metadata.google.internal/computeMetadata/v1/",
    )
    for url in unsafe_urls:
        rc, rejected = run(["web", "read", url,
                            "--backend", "jina", "--timeout", "4"], reject_home)
        if rc != 1 or (rejected.get("error") or {}).get("code") != "BAD_INPUT":
            raise AssertionError("Blocked/private URL was not rejected by the CLI")
    print(f"PASS: {len(unsafe_urls)} private, local, credential-disguised and file URLs rejected")



def public_probe(home: Path, label: str, args: list[str], timeout: int) -> bool:
    try:
        rc, result = run(args, home, timeout=timeout)
    except AssertionError as exc:
        # Schema/CLI crashes are product faults, not network flakiness.
        raise AssertionError(label + ": " + str(exc)) from exc
    if rc == 0:
        items = result.get("items")
        assert isinstance(items, list) and bool(items), label + ": empty result"
        assert isinstance(result.get("backend"), str) and result["backend"]
        print(f"PASS: {label}, anonymous public data returned, backend={result['backend']}, items={len(items)}")
        return True
    code = (result.get("error") or {}).get("code")
    if code not in ALLOWED_PUBLIC_ERRORS:
        raise AssertionError(label + ": unexpected public API failure code " + str(code))
    print(f"BLOCKED: {label}, external service unavailable ({code}); NOT a functional PASS")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="One anonymous read from each public provider")
    options = parser.parse_args()
    home = options.home.resolve()
    home.mkdir(parents=True, exist_ok=True)
    local_checks(home)
    if not options.live:
        print("NOT_RUN: live public network probes (use --live on isolated Linux runner)")
        return 0
    # Do not use a user's GH account, cookies, API key, or local browser.
    checks = [
        ("GitHub public repository metadata", ["github", "read", "Panniantong/Agent-Reach",
                                                  "--backend", "github-api", "--timeout", "18"], 35),
        ("Public website read", ["web", "read", "https://example.com",
                                 "--backend", "jina", "--timeout", "18"], 35),
        ("V2EX public topics", ["v2ex", "hot", "--limit", "2",
                                "--backend", "v2ex-api", "--timeout", "12"], 28),
        ("YouTube public video metadata", ["youtube", "read",
                                           "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                                           "--backend", "yt-dlp", "--timeout", "15"], 32),
        ("Bilibili public popular videos", ["bilibili", "hot", "--limit", "2",
                                            "--backend", "bilibili-api", "--timeout", "12"], 30),
    ]
    passed = sum(public_probe(home, label, cmd, budget) for label, cmd, budget in checks)
    print(f"PUBLIC_NETWORK: {passed}/{len(checks)} providers PASS; remaining BLOCKED, not falsely passed")

    # The official `check` command performs a live query, records evidence, and
    # is distinct from the offline doctor. This also tests the local-only state
    # transition in the disposable CI HOME.
    rc, check = run(["check", "github", "--search", "--timeout", "18"], home, timeout=40)
    records = check.get("results")
    assert isinstance(records, list) and len(records) >= 1
    assert all(row.get("channel") == "github" and row.get("action") == "search"
               for row in records)
    if rc == 0:
        assert any(row.get("passed") is True and row.get("item_count", 0) > 0
                   for row in records)
        dc, doctor = run(["doctor"], home)
        assert dc == 0
        github = next(x for x in doctor["result"]["channels"]
                      if x["channel"] == "github")
        assert github["status"] in ("search_ready", "ready"), github["status"]
        print("PASS: official live `check github --search` updated doctor to search_ready")
    else:
        codes = {(row.get("error") or {}).get("code") for row in records if not row.get("passed")}
        assert codes.issubset(ALLOWED_PUBLIC_ERRORS), codes
        print(f"BLOCKED: official live check github search, codes={','.join(sorted(codes))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
