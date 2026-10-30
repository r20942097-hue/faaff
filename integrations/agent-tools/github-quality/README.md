# GitHub development tool assessment / 2026-10-30

**State:** proposal only. The automation is committed to `proposal/github-devtools-audit-20261030`, not merged into `main`. Tool installation in this branch's GitHub Actions is only confirmed after an actual workflow run. It does not install anything on the owner's Windows PC.

## Existing baseline checked on `faaff/main`

- Present: Python CodeQL, Dependabot, dependency-review, AI hub and imported source validation, filter validation, source/ZIP guard.
- Absent: an explicit GitHub Actions expression/YAML checker and GitHub Actions-focused security auditor.
- Not present in `main`: production RPLAY/Watcher and YouTube add-on runtime sources. Their browser-level E2E cannot be claimed from this CI.

## Selection matrix

| Candidate | Upstream | Priority | Why / outcome |
|---|---|---|---|
| **actionlint 1.7.12** | https://github.com/rhysd/actionlint | P0 / staged in workflow | Catches workflow configuration, syntax, expression and shell-related errors. Release tarball SHA-256 verified. |
| **zizmor 1.31.1** | https://github.com/zizmorcore/zizmor | P0 / staged in workflow | Focuses on GitHub Actions security: untrusted expressions, privileges, insecure triggers and supply-chain risks. Offline, report-only until findings are reviewed. |
| **Gitleaks 8.30.1** | https://github.com/gitleaks/gitleaks | P1 / evaluated, not installed | Detects accidental tokens and credentials. Evaluate secret-safe output and historical false positives before enabling CI. |
| **Playwright 1.64.1** | https://github.com/microsoft/playwright | P1 / evaluated, not installed | Real browser tests for UI/synthetic sites. Its bundled Firefox is not proof of compatibility with the user's installed Firefox. Requires runnable extension source. |
| **MCP Inspector** | https://github.com/modelcontextprotocol/inspector | P1 / evaluated, not installed | Explicit inspection of local MCP servers. Run in an isolated local session only; do not expose the inspector's web UI to a network or insert secrets into CI. |
| **Opengrep** | https://github.com/opengrep/opengrep | P2 / evaluated, not installed | Wider rule-based scanning for JavaScript/Python; assess false positives/coverage against existing CodeQL before CI adoption. |

## The new scoped workflow

`.github/workflows/github-tooling-audit.yml` runs on PRs that touch workflows, composite actions or this documentation; it can also be started manually after the workflow exists on the default branch.

Security safeguards:
- `permissions: contents: read`; no write token, credentials persistence, external secrets, deployment or publishing.
- Official `actions/checkout` and `actions/setup-python` pinned by full SHA, matching this repository's established versions.
- actionlint `v1.7.12` Linux AMD64 tarball downloaded from upstream release and checked against SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` before execution.
- zizmor `1.31.1` installed as a binary wheel from PyPI (`--only-binary`), forcing `--offline`. **PyPI wheel hashes are not locked yet**, so this is a candidate setup rather than a supply-chain-hardened final gate.
- actionlint returns a failure for lint errors. zizmor deliberately uses `--no-exit-codes`, reports findings, and does not mutate files. Installation or audit runtime failures must still be investigated.
- Neither tool is allowed to commit or auto-fix. No branches are merged automatically.

## Local use

Install and verify actionlint from https://github.com/rhysd/actionlint/releases/tag/v1.7.12 (verify the archive digest for your OS/architecture, not the Linux digest above), then from repository root:

```sh
actionlint -oneline
```

For zizmor (requires Python and an available `uvx`):

```sh
uvx --from zizmor==1.31.1 zizmor --offline --format=plain --no-exit-codes .
```

For **Windows**, use PowerShell/appropriate release binary: no machine-level installer, browser driver, personal cookie or API key is installed by this PR. Audit outputs must be sanitized before publishing.

## Promotion criteria

1. Confirm the new GitHub Actions jobs actually executed from the PR. Investigate all nonzero results and every high-severity zizmor finding.
2. Verify downloaded release file checksum and wheel artifacts, ideally lock exact zizmor wheel hashes or switch to SHA-verified upstream release artifacts.
3. Confirm the new workflow does not change existing required checks or published filter URLs.
4. Switch zizmor to a blocking severity gate only once a reviewed baseline exists.
5. Add Gitleaks with redacted output and a secrets-handling review. Add Playwright/MCP Inspector in separate product-scoped PRs after an authoritative source is available.
6. Owner must separately authorize merge and production changes.

## Evidence status

- Upstream tool names, version tags and documented CLI usage: **CHECKED from official upstream documentation** on 2026-10-30.
- Repository baseline: **CHECKED from GitHub files** on 2026-10-30.
- Branch source upload, blob readback and diff inspection: **can be verified here**.
- Tool execution on GitHub-hosted runner, Windows installation, actual browser checks, full dependency integrity: **NOT_RUN unless linked CI evidence is recorded separately**.
