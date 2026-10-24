# AI workspace instructions (faaff)

## Start here
1. Read `ai/README.md` and `ai/projects.json` before planning cross-project changes.
2. Inspect the exact branch/commit of the requested product. `main` is a bootstrap/engineering surface; a feature described in a PR or an external ZIP is not necessarily present in `main`.
3. Treat source code, generated output, release ZIP, test evidence, approval, and deployment as separate entities. Never infer live product E2E from static or synthetic tests.

## Repository boundaries
- `faaff` is the engineering/integration hub.
- `browser_filter_lists/` is the existing conservative filter review and stable-list subtree. Preserve its stable paths.
- `integrations/browser-filters/source/s/` is a pinned **non-publishing** copy from `r20942097-hue/s`. Do not silently substitute a live branch for its recorded commit.
- `s/main` still owns its live subscription URLs. Do not delete, archive, redirect, or change those URLs as part of this source import.
- `workspace-management/` is currently maintained in stacked draft PRs #15/#16, not `main`. Coordinate rather than recreate its registry or rewrite committed release history.

## Agent execution contract
- Identify authoritative input/source commit, intended files, dependencies, verification gate, and rollback before changing a workstream.
- Work in isolated branches and submit PRs. Never force-push unrelated branches, automatically merge stacked PRs, or commit credentials, tokens, cookies, private personal data, live recordings, runtime SQLite databases, or caches.
- Preserve published paths and release hashes. Verify provenance; reject missing, mismatched, or expired evidence rather than filling gaps by inference.
- Run targeted checks (see `ai/README.md`) and then applicable CI. Report executed checks separately from tests only described in source documents.
- Report changed paths, observed commands/results, outstanding unverified items, release impact, and exact PR/commit. Real-device gates remain UNVERIFIED until actually executed.
- AI-authored changes are proposals; approval, deployment, and release are distinct explicit steps.
