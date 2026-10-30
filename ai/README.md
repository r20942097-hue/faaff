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
- `integrations/browser-filters/source/s/` is a byte-level pinned import of the source, tests, docs, build scripts and lockfiles, excluding the original repository `.github/` files and AI instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursor/`, `ai/`). Re-import: copy every file of the chosen `s` commit except `excluded_paths`, then update `imports/s.json` (`source_commit`, `source_tree_sha`, file blob SHAs/sizes) and `projects.json` (`s` `observed_head`) together; `python ai/check_hub.py` must pass. A separate scoped workflow performs its checks here.
- PR #14 was merged. PRs #15/#16 (stacked portfolio changes containing ZIPs) were closed unmerged on 2026-10-28; their branches survive only in the owner's git bundle backup.

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

## Python 3.15 compatibility (2026-10-31)

Python 3.15.2 (released 2026-10-25) is the first 3.15 patch tested here; 3.15.0/3.15.1 are not an acceptable security baseline for this evaluation. The pinned `3.15.2` setup-python entry runs actual hub state/import verification, decision-contract regression tests, imported filter unit tests, and generated-list parity. Versions 3.11 and 3.14 remain available and required by the current Ruleset.

- **Purpose:** catch 3.15 interpreter, stdlib, and UTF-8 default encoding compatibility problems without modifying the owner's Windows installation or publishing releases.
- **Scope:** Linux Python 3.15.2 runs the hub and pinned snapshot tests. A separate optional Windows-hosted Python 3.15.2 job runs the same checks. Even if both pass, this does **not** establish compatibility with the owner's PC, arbitrary wheels/extensions, a production watcher runtime, or real browsers.
- **Promotion:** require a successful job for the exact PR HEAD and reproduce with the actual application source and dependencies before treating 3.15 as a supported production target.
- **Security:** prefer the latest security-maintained patch in the 3.15 line for future upgrades after checking upstream changes and test evidence; do not silently downgrade below 3.15.2.

Sources: [Python 3.15.2 release](https://www.python.org/downloads/release/python-3152/), [Python 3.15 changes](https://docs.python.org/3.15/whatsnew/3.15.html).

## Migration gate
After import checks pass, compare `s/main` against the pinned source commit, pick a single writable canonical source, then establish a tested least-privilege publishing path (or keep `s` authoritative). Reconcile the `filter-profiles.json` `faaff` output scope with existing `browser_filter_lists/` policy before any cutover. Do not infer parity from similar filenames or pass a release based only on an imported snapshot.
