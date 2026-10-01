from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
REPORT_PATH = ROOT / "experimental" / "CANDIDATES.md"


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def escape_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render():
    manifest = load_json(MANIFEST_PATH)
    queue = load_json(ROOT / manifest["candidate_queue"])
    candidates = queue.get("candidates", [])

    counts = {"candidate": 0, "hold": 0, "rejected": 0}
    for candidate in candidates:
        state = candidate.get("state")
        if state in counts:
            counts[state] += 1

    lines = [
        "# Experimental Candidate Review",
        "",
        "> Generated from `experimental/candidates.json`. These entries are inactive and are not subscription rules.",
        "",
        f"Last verified: `{queue.get('observed_at', 'unknown')}`  ",
        f"Evidence freshness limit: `{manifest.get('candidate_evidence_max_age_days', 'unknown')} days`  ",
        f"Queue: `{counts['candidate']} candidate`, `{counts['hold']} hold`, `{counts['rejected']} rejected`",
        "",
        "| Domain | Category | State | Risk | Verified | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for candidate in candidates:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(candidate.get(key, ""))
                for key in ["domain", "category", "state", "risk", "verified_at", "reason"]
            )
            + " |"
        )

    lines.extend(["", "## Evidence snapshots", ""])
    for candidate in candidates:
        lines.append(f"### `{candidate.get('domain', '<unknown>')}`")
        lines.append("")
        for record in candidate.get("evidence", []):
            kind = escape_cell(record.get("kind", "unknown"))
            checked_at = escape_cell(record.get("checked_at", "unknown"))
            url = record.get("url", "")
            lines.append(f"- `{kind}` checked `{checked_at}`: {url}")
        blocker = candidate.get("promotion_blocker")
        if blocker:
            lines.append(f"- Promotion blocker: {blocker}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed report is stale")
    parser.add_argument("--write", action="store_true", help="write the generated report")
    args = parser.parse_args()

    rendered = render()

    if args.check:
        try:
            current = REPORT_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"candidate report cannot be read: {exc}", file=sys.stderr)
            return 1
        if current != rendered:
            print("candidate report is stale; run render_candidate_report.py --write", file=sys.stderr)
            return 1
        print("CANDIDATE REPORT CHECK PASSED")
        return 0

    if args.write:
        REPORT_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
        return 0

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
