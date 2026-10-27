# AI workspace instructions (faaff)

> `CLAUDE.md`、`.cursor/rules/agents.mdc`、`.github/copilot-instructions.md` はこのファイルを参照するだけの入口です。ルールはここに一本化してください。

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

## Current gate and status vocabulary / 統制ゲートと状態語
- Current owner gate: **P0 / PUBLICATION_HOLD / NO_NEW_INTERNAL_PUSH**. Without explicit owner approval, do not push, open/update/merge PRs, create releases, change visibility/settings, delete branches, or re-run CI.
- Report each check as **PASS / FAIL / BLOCKED / NOT_RUN / NEEDS_HUMAN / PARTIAL**. Never mark unexecuted real-device, Windows, Firefox, login or recording checks as PASS.
- `main` does **not** contain the Universal Live Watcher runtime (`rplay_watcher/`, `extension/`, `tests/`). Do not claim its tests ran here; see `README.md`.

## Shared context outside the repo / リポジトリ外の共通コンテキスト
- Master entry (Google Drive, access required): 00_AI作業環境_統合マスター入口 — https://docs.google.com/document/d/1ajeph-Kynrpmza3cn06SdKrCYkW-FF3x1ZgRaTzbrkE/edit
- Master ledger (all project lines, IDs P01–P48): https://docs.google.com/spreadsheets/d/1fkeLrgmN29t8WY9ft4B5AKqreG0wEyh3T-gXaKa6ODQ/edit
- Drive documents are navigation aids. Git state (branch, HEAD SHA, CI) is authoritative for code; re-read it before acting.

## Session handoff files / セッション引継ぎ
- `ai/PROJECT_STATE.json` (machine-readable current state) and `ai/HANDOFF.md` (next single task, checks run / not run, blockers) **do not exist yet** on `main` (observed 2026-10-27). If you are asked to create them, place them under `ai/`, never record secrets, and do not create parallel copies elsewhere.
- Until then, use `ai/projects.json` and `ai/WORK_QUEUE.md`.

## Commands / コマンド
Offline checks are listed in `ai/README.md` and `README.md`. Workflows: `ci.yml`, `ai-hub.yml`, `validate-browser-filter-lists.yml`, `codeql.yml`, `dependency-review.yml`. Pin third-party Actions to full commit SHAs.
