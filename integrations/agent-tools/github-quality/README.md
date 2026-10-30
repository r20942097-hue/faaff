# GitHub development tool assessment / 2026-10-30

**State:** proposal only. The automation is committed to `proposal/github-devtools-audit-20261030`, not merged into `main`. The three new jobs have run successfully on GitHub-hosted Ubuntu runners (see evidence below). It does not install anything on the owner's Windows PC.

## Existing baseline checked on `faaff/main`

- Present: Python CodeQL, Dependabot, dependency-review, AI hub and imported source validation, filter validation, source/ZIP guard.
- Absent: an explicit GitHub Actions expression/YAML checker and GitHub Actions-focused security auditor.
- Not present in `main`: production RPLAY/Watcher and YouTube add-on runtime sources. Their browser-level E2E cannot be claimed from this CI.

## Selection matrix

| Candidate | Upstream | Priority | Why / outcome |
|---|---|---|---|
| **actionlint 1.7.12** | https://github.com/rhysd/actionlint | P0 / staged in workflow | Catches workflow configuration, syntax, expression and shell-related errors. Release tarball SHA-256 verified. |
| **zizmor 1.31.1** | https://github.com/zizmorcore/zizmor | P0 / staged in workflow | Focuses on GitHub Actions security: untrusted expressions, privileges, insecure triggers and supply-chain risks. Offline, report-only until findings are reviewed. |
| **Gitleaks 8.30.1** | https://github.com/gitleaks/gitleaks | P1 / staged in workflow | Scans PR Git changes in a Docker container with source mounted read-only, no network, secret redaction and report-only exit policy. |
| **Playwright 1.64.1** | https://github.com/microsoft/playwright | P1 / evaluated, not installed | Real browser tests for UI/synthetic sites. Its bundled Firefox is not proof of compatibility with the user's installed Firefox. Requires runnable extension source. |
| **MCP Inspector** | https://github.com/modelcontextprotocol/inspector | P1 / evaluated, not installed | Explicit inspection of local MCP servers. Run in an isolated local session only; do not expose the inspector's web UI to a network or insert secrets into CI. |
| **Opengrep** | https://github.com/opengrep/opengrep | P2 / evaluated, not installed | Wider rule-based scanning for JavaScript/Python; assess false positives/coverage against existing CodeQL before CI adoption. |

## The new scoped workflow

`.github/workflows/github-tooling-audit.yml` runs on **all** PRs to detect newly introduced secrets, and can be started manually after the workflow exists on the default branch.

Security safeguards:
- `permissions: contents: read`; no write token, credentials persistence, external secrets, deployment or publishing.
- Official `actions/checkout` and `actions/setup-python` pinned by full SHA, matching this repository's established versions.
- actionlint `v1.7.12` Linux AMD64 tarball downloaded from upstream release and checked against SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` before execution.
- zizmor `1.31.1` installed as a binary wheel from PyPI (`--only-binary`), forcing `--offline`. **PyPI wheel hashes are not locked yet**, so this is a candidate setup rather than a supply-chain-hardened final gate.
- actionlint returns a failure for lint errors. zizmor deliberately uses `--no-exit-codes`, reports findings, and does not mutate files. Installation or audit runtime failures must still be investigated.
- Gitleaks is run using a pinned official GHCR image digest for v8.30.1 (`sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`). The container is network-disabled and mounts the checked-out source read-only. Scan scope is PR-only `origin/main..HEAD` for pull requests and the current worktree (`gitleaks dir`) for manual `workflow_dispatch` runs. `--redact=100 --exit-code 0` masks detected values and makes findings report-only; a pass does not imply a complete historical scan. A passed job does not mean there were no findings; logs need review.
- None of the tools may commit or auto-fix. No branches are merged automatically.

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
5. Review Gitleaks redacted findings and tune a blocking policy without publishing secret values. Add Playwright/MCP Inspector in separate product-scoped PRs after an authoritative source is available.
6. Owner must separately authorize merge and production changes.

## Evidence status

- Upstream tool names, version tags and documented CLI usage: **CHECKED from official upstream documentation** on 2026-10-30.
- Repository baseline: **CHECKED from GitHub files** on 2026-10-30.
- Branch source upload, blob readback and diff inspection: **can be verified here**.
- Tool execution on GitHub-hosted Ubuntu runners: **PASS** (see verified runs). Windows installation, browser E2E and full dependency integrity remain **NOT_RUN**.

## Execution note (2026-10-30)

A first CI smoke run found a malformed SHA256 verification input (`\\n` instead of a newline), and the next run detected an invalid unquoted YAML `run:` value containing `--only-binary=:all:`. Both issues were corrected and verified by real CI runs. The new `github-tooling-audit.yml` workflow itself ran on the PR. The temporary smoke jobs in `ci.yml` have since been removed, restoring the original required CI. These changes do not authorize merging into `main`.

## Verified GitHub Actions results

- [Workflow run 41028484905](https://github.com/r20942097-hue/faaff/actions/runs/41028484905): actionlint **PASS**, zizmor offline execution **PASS** (no unsuppressed findings, 12 suppressed), Gitleaks **PASS** (no leaks found in the PR-scoped scan). Detection jobs deliberately remain report-only except actionlint.
- [Workflow run 41028635580](https://github.com/r20942097-hue/faaff/actions/runs/41028635580): follow-up audit after removing temporary smoke steps from existing `ci.yml` — **PASS**.
- Dependabot `pip` and `github-actions` version-update cooldown increased from GitHub default 3 days to 7 days to address two medium-confidence zizmor findings. GitHub documents that security-update PRs are exempt from cooldown. See https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference.
- New audit is an **optional PR check until explicitly made required by repository rules**; successful report-only tool exit cannot be conflated with no security risk or full historical secret scan.

## Subsequent adoption decisions

Keep Playwright and MCP Inspector out of this hub PR until the runtime sources / dedicated isolated test hosts are available and acceptance criteria exist. Avoid adding Python/JavaScript static analyzers that largely duplicate CodeQL before a concrete missed-detection case justifies them.

The initial Gitleaks manual trigger used the same Git range as pull requests, which would be empty when HEAD matched `origin/main`. This was repaired: manual dispatch now scans the working tree with `gitleaks dir`, without reading the entire historical Git log. PR scans remain Git-diff-scoped.

## 2026-10-30 CI escalation — actual blocking checks

The project already achieved a clean (unsuppressed) offline zizmor audit and a no-leaks Gitleaks PR scan. This proposal therefore now **fails the CI job** for:

- `actionlint -oneline` errors (unchanged).
- `zizmor --offline --min-severity=medium --format=plain .` reporting new unsuppressed **medium/high** findings. Existing 12 suppressed findings remain suppressed and are **not proof of being safe**. Low severity findings are filtered; the job retains nonzero tool failures.
- `gitleaks git` (PR commit range) or `gitleaks dir` (manual worktree), both `--redact=100 --exit-code 1`. No full-history secret scanning is asserted.

Verified [blocking audit run 41030412200](https://github.com/r20942097-hue/faaff/actions/runs/41030412200): all three audit jobs succeeded. Zizmor: no unsuppressed findings (12 suppressed). Gitleaks: no leaks in scoped PR changes. This does not alter existing branch-protection required-check settings; ruleset changes require separate owner approval.

## Final audit inventory / 2026-10-30

- [GitHub Actions run 41031879081](https://github.com/r20942097-hue/faaff/actions/runs/41031879081) confirmed actionlint, blocking zizmor and blocking Gitleaks jobs **PASS** on the proposal branch.
- Gitleaks PR range: **18 commits scanned; no leaks found**. Additional Git historical baseline: **481 commits scanned; no leaks found** (fully redacted advisory; local accessible branch history, not an assurance that every lost/orphan commit or external repository was scanned).
- Zizmor blocking run: **0 active medium/high findings**; ignored/suppressed inventory step with `--no-ignores --no-exit-codes` also reported no active findings, but the tool noted **12 suppressed**. These are not automatically treated as safe and may be reviewed separately.
- The new quality workflow is CI-enforced within this PR if its job runs. Its check is **not** added to the repository's required branch-protection checks, and merge approval remains separate.

## Secret scanner positive control (2026-10-30)

[GitHub Actions run 41032532965](https://github.com/r20942097-hue/faaff/actions/runs/41032532965): actionlint, zizmor and Gitleaks jobs **PASS**. Gitleaks additionally detected an artificial high-entropy AWS-formatted identifier created exclusively inside the ephemeral runner, correctly returning exit code 1. The generated value and unredacted scanner output were not uploaded or written to Git history. Reachable history at this run: 484 commits, no leaks detected. The sensitivity test covers one signature only, not all possible secret formats.

## Hash-locked zizmor and positive audit control — 2026-10-30

The zizmor job now uses a committed wheel pin at `integrations/agent-tools/github-quality/zizmor-linux-requirements.txt` with SHA-256 `58e878eb2dbd2c6183c105e1ac28c14f7dd1eca44a783f1fe2a69647d012c410` for Linux x86_64, and installs using `pip --no-deps --require-hashes --only-binary=:all:`. It fails closed on wheel mutation or mismatch and must be separately pinned for other architectures. A synthetic dangerous GitHub workflow is generated only in runner temporary storage; zizmor is expected to return finding code **13** (medium) or **14** (high), never the audit-error code 1. This positive control was verified by [audit run 41034945285](https://github.com/r20942097-hue/faaff/actions/runs/41034945285). Scanner source and dependency locking do not mean upstream code is guaranteed safe.
