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

## Migration gate
After import checks pass, compare `s/main` against the pinned source commit, pick a single writable canonical source, then establish a tested least-privilege publishing path (or keep `s` authoritative). Reconcile the `filter-profiles.json` `faaff` output scope with existing `browser_filter_lists/` policy before any cutover. Do not infer parity from similar filenames or pass a release based only on an imported snapshot.

## Pinned import safety regressions

The existing `python ai/check_hub.py` validates the local import against the
recorded Git blob hashes and manifest file set. It also rejects malformed JSON
metadata, unsafe or colliding portable paths, excluded/imported path overlap,
and symlinks in the imported tree or its parent components.

Run the offline fault-injection tests with:

```sh
python -m unittest discover -s ai/tests -p 'test_*.py' -v
```

`.github/workflows/ai-hub-import-safety.yml` runs these tests on Python 3.11
and 3.14 when the validator, tests, or workflow change. The existing AI hub
workflow continues to run the validator on the actual pinned import.

**Boundary:** matching the manifest's local blob hashes does *not* independently
prove that the manifest corresponds to the upstream `s` Git commit/tree.
Compare the upstream Git tree at the pinned SHA separately before changing
source ownership, publication, or release status. These checks are neither
product runtime tests nor real-browser E2E tests.
