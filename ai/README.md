# AI engineering hub / AI開発の入口

This directory is the cross-project navigation and verification layer for `faaff`. It is **not** a second release registry. Current state: `PROJECT_STATE.json`; handoff: `HANDOFF.md`.

## First read
- `../AGENTS.md`: shared coding-agent instructions and safety boundaries.
- `projects.json`: machine-readable index of verified GitHub sources and their *observed* state, not an always-live inventory.
- `imports/s.json`: pinned file-level provenance for the imported `s` source.
- `WORK_QUEUE.md`: staged integration plan.

## Ownership
- `faaff/main` is currently the engineering/bootstrap hub; keep its existing `browser_filter_lists/` unchanged.
- `s/main` is the live subscription authority. Existing raw GitHub URL paths stay there.
- `integrations/browser-filters/source/s/` is the byte-for-byte pinned import of the **included files listed in** `ai/imports/s.json`. The manifest's exact `excluded_paths` list is authoritative: do not treat the entire `.github/`, `.cursor/`, or `ai/` directories as excluded. In particular, source-policy-only changes (such as `s/AGENTS.md`) do **not** require a re-import when no included source file changes. Only when included files actually change: choose an explicit `s` source commit, copy the complete included file set, update `ai/imports/s.json` (`source_commit`, `source_tree_sha`, Git blob SHA/size entries), and reconcile `ai/projects.json` (`s` `observed_head`) with the observed source. Run `python ai/check_hub.py` and both source suites before considering a merge. A separate scoped workflow runs checks here.
- Earlier **faaff** PR #14 was merged; **faaff** PRs #15/#16 (historical stacked portfolio changes containing ZIPs) were closed unmerged on 2026-10-28. These are distinct from the currently open **s** PR #16; don't confuse identical numbers across repositories.

## CI run efficiency and cancellation scope (2026-10-31)

Five PR workflows (AI hub, CI, CodeQL, Dependency Review and filter validation) can overlap when a PR receives successive commits. Each workflow uses a **workflow-scoped, PR-number-specific concurrency group** and cancels only obsolete `pull_request` runs for that same PR. This avoids expensive stale-SHA jobs and noisy stale results. `main` push, cron and `workflow_dispatch` runs use unique run identifiers and are **not** canceled by this optimization. Cancellation is a normal outcome for superseded commits and must never be called a PASS; a merge decision still requires all mandatory check contexts on the latest HEAD.

Published list files, release gates, CI job identities, required checks, and the separate `s` filter source remain unchanged. The goal is eliminating redundant execution, not skipping coverage on current changes.

## Workflow dependency hardening (2026-10-31)

Official GitHub Actions dependency lockfiles became generally available on 2026-10-28 (https://docs.github.com/en/actions/how-tos/secure-your-work/lock-workflow-dependencies). They can cover transitive action dependencies and repository identity. The lockfile must be **generated** with `gh actions-lock` and must never be edited or fabricated manually. A lockfile does not prove that a dependency is safe or pin reusable-workflow implementations.

**Implemented now:** `ai/tests/test_workflow_security.py` uses only Python's standard library to guard existing full-SHA `uses` pins, nonpersistent checkout credentials, least-privilege workflow permissions, PR-only cancellation, and Windows Git blob CRLF preservation. No workflow or required CI job names were changed. This test is only an offline configuration regression; it is not a transitive dependency audit.

**Pending:** this environment lacks `gh` CLI and external network resolution. No `.github/workflows/actions.lock` has been generated. After a suitable authenticated environment is available, separately onboard each repository using the official extension `gh extension install github/gh-actions-lock` and `gh actions-lock`, review every generated change, and verify with real Actions before applying a lockfile requirement. Update SHA-only tests when a verified migration adopts version references plus a valid lockfile; never weaken policy preemptively.

The current GitHub REST API header version `2022-11-28` remains officially supported through 2028-03-10; changing to version `2026-03-10` would require a separate breaking-change review and live API regression, not an automatic migration.
## Offline checks (from faaff root)

```sh
python ai/check_hub.py
python -m unittest discover -s integrations/browser-filters/source/s/tests -p 'test_*.py' -v
python integrations/browser-filters/source/s/scripts/validate_lists.py
python integrations/browser-filters/source/s/scripts/generate_lists.py --check
python browser_filter_lists/scripts/test_validator.py
python browser_filter_lists/scripts/test_evidence.py
python browser_filter_lists/scripts/test_promotion.py
```

`ai/check_hub.py` validates the index and checks the original Git blob hashes of every imported source file. These checks do not update external subscriptions. Online engine checks and real Firefox, Windows, login, recording or product acceptance are separate gates.

## AI decision contract (advisory, offline)

`ai/decision_contract.py` classifies a proposed change by **highest risk** and checks evidence required before a human-authorized merge. It never performs GitHub writes and **does not replace** `AGENTS.md`, Rulesets, required reviews, or publication gates.

- Inputs: actual changed file paths, exact PR HEAD SHA, the SHA attached to CI observations, current Ruleset-required job names and outcomes, explicit owner approval, and (for product implementation) product verification evidence.
- Outcomes: `BLOCKED`, `AWAITING_OWNER_APPROVAL`, and `ELIGIBLE_FOR_REVIEW`. The latter means *only* that the supplied evidence passes this advisory contract; it does **not** grant merge or release permission.
- Missing/failed/skipped checks, mismatched SHA, invalid paths, archives and published-list changes remain blocked. Product implementation changes cannot be mistaken for verified E2E merely because the infrastructure CI passed.
- This is a deterministic **policy contract test**, not an evaluation of an LLM's natural-language judgment, real browser behavior or end-to-end autonomy. Do not report it as such.

Run locally from repository root:

```sh
python -m unittest discover -s ai/tests -p 'test_*.py' -v
```

The existing `AI hub and pinned filter source` workflow includes this suite on pull requests under Python 3.11, 3.14 and 3.15.2; the pre-existing 3.11/3.14 required check identities remain unchanged and required jobs are **not** path-skipped as an optimization. Inspect the exact CI result and current GitHub Ruleset before any approval decision.

### Cross-platform input hardening

The advisory policy classification treats ASCII path prefixes case-insensitively to prevent Windows-path variants from downgrading published-list changes; it rejects NTFS alternate-stream syntax and suspicious secret-bearing paths. It does **not** expand the set of authorized GitHub operations.

The pinned-source integrity verifier now rejects a symlink in any manifest path component (including an import-root ancestor), rejects extra symlinks and reports non-object metadata cleanly. The full byte-for-byte Git blob check remains unchanged. Regression tests include negative fixtures; Windows runners may skip symlink-creation fixtures when the OS disallows test symlinks, while Linux executes them. The Windows workflow disables automatic CRLF conversion before checkout to preserve canonical imported bytes.

## Live GitHub evidence inspection (read-only)

After all PR jobs have completed, fetch actual evidence directly from GitHub rather than copying green check names into a handoff. This command uses only **GET** API requests and outputs an advisory JSON assessment:

```sh
python -m ai.inspect_pr r20942097-hue/faaff 44 --ruleset-id 26005483
python -m ai.inspect_pr r20942097-hue/s 16 --ruleset-id 26005481
```

The ruleset IDs above are the branch-protection rulesets verified on 2026-10-31. Re-read applicable active Rulesets if the configuration changes; the command audits the **one explicitly selected ruleset** and is **not** proof that other protections are absent. For public repositories, the GitHub API may work without a token subject to its request rate limits. `GH_TOKEN` or `GITHUB_TOKEN` can optionally be supplied via the process environment (never commit or print credentials).

`ai/inspect_pr.py` paginates the complete changed-file/check-run collections, checks exact HEAD/base stability by re-fetching the PR, uses both names on rename, checks active ruleset scope, and matches the required check `context`, issuing GitHub App `integration_id`, HEAD SHA, completed status, and successful conclusion. Missing, duplicate, skipped, in-progress, mismatched, inaccessible or incomplete evidence is **BLOCKED**. `AWAITING_OWNER_APPROVAL` means evidence passed this selected snapshot's checks but owner authorization and every other GitHub/release gate are **still required**. It does not merge, review, post data, write files, or claim product E2E acceptance. Re-run the command after any PR head, ruleset, or CI status changes.

For reproducible checks, pass the expected PR head from the event or immediately prior trusted PR read:

```sh
python -m ai.inspect_pr r20942097-hue/faaff 44 --ruleset-id 26005483 --expected-head-sha <40-hex-PR-head>
```

The PR CI smoke passes `github.event.pull_request.head.sha` automatically and fails if a newer commit replaced it before the audit. The CLI re-reads both the effective-branch rules and the selected ruleset before recording its result, rejecting a mid-audit policy change. Successful network collection records `observed_at_utc`, `repository`, `pr_number`, `head_sha`, `base_sha` and `event_head_verified`. These describe a **point-in-time observation**, not an indefinitely reusable merge decision. Do not reuse the JSON for a later HEAD or after rule/check changes.

The live CLI also checks GitHub's **effective rules for the main branch** (`GET /repos/{owner}/{repo}/rules/branches/main`), which includes inherited organization rules. A second active ruleset or unknown rule association returns `BLOCKED` instead of silently ignoring additional protections. This does not replace a separate owner-authorization or legacy branch-protection review.

The live audit emits `pending_checks` for queued/in-progress required jobs and `nonpassing_checks` for completed unsuccessful/skipped checks. Its conservative overall `BLOCKED` status is unchanged. A snapshot with only pending checks is **not** a test failure; inspect the latest PR HEAD checks again rather than raising a new incident. Unknown or incomplete evidence is never treated as successful.

The existing AI hub workflow now includes a non-required `Read-only GitHub API smoke (not a merge gate)` job on PRs after the Linux/Windows checks. Its token is scoped to repository contents, PR and check **read** access. `LIVE_API_SMOKE_PASS` means that all read-only API requests completed and a valid advisory result was produced; the policy result can still be `BLOCKED`, and neither result authorizes a merge. The existing 3-hour GitHub quality audit can inspect this run; no additional scheduled task is created.

The deterministic adversarial fixtures are tested offline in `ai/tests/test_github_evidence.py`; executing those fixtures does **not** prove the remote GitHub API was contacted successfully. Network failures must be reported `BLOCKED`, not silently inferred as a green gate.

## Python 3.15 compatibility (2026-10-31)

Python 3.15.2 (released 2026-10-25) is the first 3.15 patch tested here; 3.15.0/3.15.1 are not an acceptable security baseline for this evaluation. The pinned `3.15.2` setup-python entry runs actual hub state/import verification, decision-contract regression tests, imported filter unit tests, and generated-list parity. Versions 3.11 and 3.14 remain available and required by the current Ruleset.

- **Purpose:** catch 3.15 interpreter, stdlib, and UTF-8 default encoding compatibility problems without modifying the owner's Windows installation or publishing releases.
- **Scope:** Linux Python 3.15.2 runs the hub and pinned snapshot tests. A separate optional Windows-hosted Python 3.15.2 job runs the same checks. Even if both pass, this does **not** establish compatibility with the owner's PC, arbitrary wheels/extensions, a production watcher runtime, or real browsers.
- **Promotion:** require a successful job for the exact PR HEAD and reproduce with the actual application source and dependencies before treating 3.15 as a supported production target.
- **Security:** prefer the latest security-maintained patch in the 3.15 line for future upgrades after checking upstream changes and test evidence; do not silently downgrade below 3.15.2.

Sources: [Python 3.15.2 release](https://www.python.org/downloads/release/python-3152/), [Python 3.15 changes](https://docs.python.org/3.15/whatsnew/3.15.html).

## Migration gate
After import checks pass, compare `s/main` against the pinned source commit, pick a single writable canonical source, then establish a tested least-privilege publishing path (or keep `s` authoritative). Reconcile the `filter-profiles.json` `faaff` output scope with existing `browser_filter_lists/` policy before any cutover. Do not infer parity from similar filenames or pass a release based only on an imported snapshot.
