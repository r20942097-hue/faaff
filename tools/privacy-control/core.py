"""Conservative ABP network-rule analysis; this module does NOT block traffic.

Only proven exact normalized overlap is identified. Unknown rules, exceptions,
source-domain modifiers, redirects and URL modifiers remain NOT_VERIFIED.
This is not an adblock engine, a DNR compiler or an efficacy measurement.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha1, sha256
import json
from pathlib import Path
import re

PATTERN = re.compile(r"^\|\|([a-zA-Z0-9.-]+)\^(?:\$([^\s]+))?$")
SUPPORTED = frozenset({
    "third-party", "first-party", "script", "image", "stylesheet",
    "xmlhttprequest", "subdocument", "font", "media", "ping",
    "document", "other",
})


@dataclass(frozen=True)
class Rule:
    raw: str
    canonical: str | None
    host: str | None
    options: tuple[str, ...]
    reason: str

    @property
    def supported(self) -> bool:
        return self.reason == "EXACT_NETWORK_SYNTAX"


def valid_host(name: str) -> bool:
    if len(name) > 253 or "." not in name:
        return False
    labels = name.split(".")
    return all(
        0 < len(label) <= 63 and
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
        is not None for label in labels
    ) and not name.replace(".", "").isdigit()


def parse_rule(raw: str) -> Rule:
    text = raw.strip()
    if not text or text.startswith(("!", "[")):
        raise ValueError("metadata lines must be removed before parsing")
    match = PATTERN.fullmatch(text)
    if not match:
        return Rule(text, None, None, (), "UNSUPPORTED_OR_COMPLEX_SYNTAX")
    host = match.group(1).lower()
    if not valid_host(host):
        return Rule(text, None, None, (), "INVALID_OR_UNSAFE_HOST")
    raw_options = match.group(2)
    parts = raw_options.split(",") if raw_options is not None else []
    if any(not part for part in parts):
        return Rule(text, None, host, (), "UNSUPPORTED_OPTIONS")
    options = tuple(part.lower() for part in parts)
    if len(options) != len(set(options)) or any(x not in SUPPORTED for x in options):
        return Rule(text, None, host, options, "UNSUPPORTED_OPTIONS")
    if "first-party" in options and "third-party" in options:
        return Rule(text, None, host, options, "CONTRADICTORY_PARTY_SCOPE")
    opts = tuple(sorted(options))
    canonical = "||" + host + "^" + ("$" + ",".join(opts) if opts else "")
    return Rule(text, canonical, host, opts, "EXACT_NETWORK_SYNTAX")


def extract_active(source: str) -> list[str]:
    return [line.strip() for line in source.splitlines()
            if line.strip() and not line.lstrip().startswith("!")
            and line.strip() != "[Adblock Plus 2.0]"]


def parse_list(source: str, label: str) -> list[Rule]:
    parsed = [parse_rule(raw) for raw in extract_active(source)]
    seen = set()
    for row in parsed:
        key = row.canonical if row.supported else row.raw
        if key in seen:
            raise ValueError("duplicate " + label + " rule: " + key)
        seen.add(key)
    return parsed


def git_blob_sha(data: bytes) -> str:
    return sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def pinned_lists(repository: Path):
    prefix = repository / "integrations/browser-filters/source/s"
    index = json.loads((repository / "ai/imports/s.json").read_text(encoding="utf-8"))
    if (index.get("schema") != "pinned-source-import/v1"
            or index.get("source_repository") != "r20942097-hue/s"
            or not re.fullmatch(r"[0-9a-f]{40}", index.get("source_commit", ""))):
        raise ValueError("invalid pinned import manifest")
    files = {e["path"]: e for e in index["files"]}
    data = {}
    metadata = {}
    for name in ("tracking.txt", "v2/tracking.txt"):
        item = files.get(name)
        if item is None:
            raise ValueError("missing pinned file entry: " + name)
        content = (prefix / name).read_bytes()
        digest = git_blob_sha(content)
        if digest != item.get("git_blob_sha") or len(content) != item.get("size"):
            raise ValueError("pinned blob mismatch: " + name)
        data[name] = content.decode("utf-8", errors="strict")
        metadata[name] = {
            "path": "integrations/browser-filters/source/s/" + name,
            "git_blob_sha": digest,
            "sha256": sha256(content).hexdigest(),
            "bytes": len(content),
        }
    return index["source_commit"], data, metadata


def assess(stable: list[Rule], proposed: list[Rule]) -> dict:
    baseline = {item.canonical for item in stable if item.supported}
    findings = []
    for item in proposed:
        if not item.supported:
            status = "UNSUPPORTED_NOT_VERIFIED"
        elif item.canonical in baseline:
            status = "EXACT_OVERLAP_WITH_PINNED_STABLE"
        else:
            status = "NO_EXACT_STABLE_OVERLAP_NOT_VERIFIED"
        findings.append({
            "rule": item.raw, "canonical": item.canonical,
            "host": item.host, "options": list(item.options),
            "status": status, "parser_reason": item.reason,
            "real_world_incremental_blocking": "NOT_ESTABLISHED",
            "safe_to_publish": False,
        })
    return {"findings": findings, "counts": dict(sorted(
        Counter(r["status"] for r in findings).items()))}


def build_report(repository: Path) -> dict:
    commit, sources, source_info = pinned_lists(repository)
    stable = parse_list(sources["tracking.txt"], "stable")
    candidate = parse_list(sources["v2/tracking.txt"], "candidate")
    analysis = assess(stable, candidate)
    return {
        "schema": "upc-coverage-report/v1",
        "mode": "READ_ONLY_OFFLINE",
        "source": {
            "repository": "r20942097-hue/s",
            "source_commit": commit, "role": "PINNED_NON_PUBLISHING_SNAPSHOT",
            "files": source_info,
        },
        "baseline": "pinned_s_stable_tracking_ONLY_NOT_BROWSER_STOCK_LISTS",
        "stable_rules": len(stable), "candidate_rules": len(candidate),
        "coverage": analysis,
        "browser_stock_coverage": "NOT_RUN",
        "real_engine_efficacy": "NOT_RUN",
        "live_site_compatibility": "NOT_RUN",
        "release": "NO_GO", "rules_published": 0,
    }


def verify_report(report: dict, expected=(9, 38, 9)):
    if (report.get("schema") != "upc-coverage-report/v1"
            or report.get("mode") != "READ_ONLY_OFFLINE"
            or report.get("release") != "NO_GO"
            or report.get("rules_published") != 0
            or report.get("browser_stock_coverage") != "NOT_RUN"
            or report.get("real_engine_efficacy") != "NOT_RUN"
            or report.get("live_site_compatibility") != "NOT_RUN"):
        raise ValueError("evidence or release gate invalid")
    rows = report["coverage"]["findings"]
    count = sum(x["status"] == "EXACT_OVERLAP_WITH_PINNED_STABLE" for x in rows)
    if (report["stable_rules"], report["candidate_rules"], count) != expected:
        raise ValueError("pinned-list baseline changed; review required")
    if len(rows) != report["candidate_rules"] or any(
        item["real_world_incremental_blocking"] != "NOT_ESTABLISHED"
        or item["safe_to_publish"] is not False for item in rows
    ):
        raise ValueError("incomplete or misleading candidate evidence")
    return True
