# Codex readiness and first-task runbook

This page is the shortest route from **Codex account access** to a **verified repository task**. It does not install another agent, duplicate `AGENTS.md`, or certify any product runtime. The authoritative state remains `ai/PROJECT_STATE.json`; current work is in `ai/HANDOFF.md` and `ai/WORK_QUEUE.md`.

## 1. Distinguish the three independent gates

| Gate | How to establish it | Failure / unknown |
| --- | --- | --- |
| **ACCOUNT / CLOUD** | In the intended ChatGPT account and workspace, open Codex, create and publish a cloud environment, and successfully start a task in it. | A ChatGPT GitHub connector alone does **not** prove Codex cloud access. Account quota, workspace switches and cloud task startup are not verifiable from this repo. |
| **REPOSITORY READ** | Add `r20942097-hue/faaff` to the environment; start a Codex task that reads its files and can fetch the expected Git ref. | Public GitHub API access or a ChatGPT connector alone does **not** prove the task's Git credentials work. |
| **REPOSITORY WRITE (optional)** | Only after read checks pass, deliberately push a trivial text-only commit to a separate proposal branch from an authenticated Codex task and open a Draft PR. | A read-only task, `git remote -v`, `ls-remote` or the ChatGPT connector cannot certify Codex push/PR permissions. No main push or merge. |
| **PRODUCT** | Independently verify the selected product's full source/version/hash, relevant build, targeted checks, browser and device E2E. | Hub/static/synthetic CI does **not** establish RPLAY/YouTube/add-on runtime readiness. |

Codex Cloud setup and limitations: https://help.openai.com/en/articles/20001545-using-codex-cloud  
Codex plan and CLI/Windows entry points: https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan  
CLI commands and `codex doctor`: https://learn.chatgpt.com/docs/developer-commands?surface=cli

## 2. Minimal safe setup (Codex web / desktop)

1. Sign in using the intended ChatGPT account and workspace. Create a **cloud environment** on web or desktop, connect the intended GitHub account, and select the exact repository `r20942097-hue/faaff`. Environment access, GitHub permissions and individual task Git configuration are distinct.
2. Start with the existing repository runtime; **do not preinstall Agent-Reach, SkillSpector, MCP servers, browser extensions, or extra credentials**. Add a dependency only if a scoped test actually requires it, with provenance and version control.
3. Publish the environment only after its setup check works. Do not add real service cookies, login tokens, customer content or recordings as task prompts, commits or CI fixtures.
4. Start a **read-only inspection task** first. This validates task startup and code access, not push authority. Only if a write-path test is needed, use a separate proposal branch and Draft PR with a trivial text-only change; never push directly to main or merge automatically.

If Codex environment creation, repository selection, task startup or Git push fails, record the **exact failed stage**. Treat that stage as BLOCKED; do not infer it was fixed from unrelated CI.

## 3. First repository task — copy into Codex

> Read `AGENTS.md`, `ai/README.md`, `ai/projects.json`, `ai/PROJECT_STATE.json` and `ai/HANDOFF.md`. Inspect the actual repository, branch and HEAD SHA; explain the difference between `faaff/main` engineering/bootstrap, `s/main` live filter distribution, and any external product ZIP or Draft PR. Do not write, install dependencies, alter public subscriptions, merge, release or use credentials. Run the relevant **existing offline checks** below, reporting the actual exit codes and PASS/FAIL/BLOCKED/NOT_RUN. State separately whether the exact RPLAY/three-addon product sources and actual Windows/Firefox/browser E2E are present. Give a short, concrete next step; do not mark unexecuted work PASS.

Suggested commands from the repository root:

```sh
git remote -v
git ls-remote --heads origin main
git branch --show-current
git rev-parse HEAD
git status --short
python --version
python ai/check_hub.py
python -m unittest discover -s integrations/browser-filters/source/s/tests -p 'test_*.py' -v
python integrations/browser-filters/source/s/scripts/validate_lists.py
python integrations/browser-filters/source/s/scripts/generate_lists.py --check
```

The checks are the existing `ai/README.md` baseline. Run only commands supported by the environment. A missing dependency or environment limitation is BLOCKED/NOT_RUN, not a success. Record whether the checkout is main or a proposal branch and check actual current HEAD rather than trusting a dated state document.

## 4. Diagnose failures by stage

| Symptom | Narrow next check |
| --- | --- |
| Cloud controls are unavailable | Confirm account, eligible plan, workspace permissions, available allowance; do not treat this as a GitHub failure. |
| Repository cannot be selected | Confirm GitHub account, repository-scoped authorization and inclusion in that *Codex* environment. |
| Repository can be read, but push/PR fails | Check task Git identity, credential scope, target branch and protection rules; do not relax main protection. |
| Environment setup or command fails | Capture failing command and exit code; use existing dependencies first and change setup only when necessary. |
| Python runtime test skipped | Check that the specific product source exists; in faaff/main a skipped RPLAY job is not a product PASS. |

If a second **write-path** task is necessary, ask Codex to create a new `proposal/codex-connectivity-...` branch off the verified base, commit only a small harmless Markdown change, push that branch and open a **Draft PR**. Record the PR URL and actual push result. Do not delete the branch, add a ZIP, change subscriptions, approve a merge or deploy as part of the smoke test. Such a task is optional and consumes usage; do not manufacture commits just to increase a PASS count.

## 5. Acceptance and handoff

Record these fields in the task response, not in a new competing state registry:

- **Account/Cloud:** environment creation, setup and task startup PASS, FAIL or NOT_RUN, independently of GitHub. Check remaining allowance separately in Settings → Usage.
- **Repo:** full repository name, branch, exact HEAD SHA, clean/dirty worktree, instructions read; separate read/fetch and (optional) push/Draft-PR proofs.
- **Checks:** command + exit code + relevant output for each actually executed check.
- **Source provenance:** product/version and source commit or immutable artifact hash, or BLOCKED_BY_SOURCE.
- **Verification scope:** hub/static, synthetic, installed browser extension, actual target site, Windows/Firefox native run — each separately.
- **Changes and next step:** modified paths, PR URL, rollback, owner approval needed; do not upgrade Draft/GO_CANDIDATE to production-ready.

Do not add a new CI workflow solely for Codex access: **only an authenticated Codex task can confirm its own cloud connection**. Reuse the existing hub and product-specific checks. Current proposed toolchains and source gaps are described in Draft PR #35–#39; confirm their actual state before adopting them.

## 6. Optional local Windows Codex diagnosis

Use the existing Codex CLI **only if installed** (never install it on the owner's production Windows profile merely to pass this check):

```sh
codex --version
codex login status
codex doctor --summary
```

Inside an active Codex session, `/status` shows usage and limits. `codex login status` verifies local authentication, while `codex doctor` checks the local installation and runtime. Neither establishes Codex **Cloud** connectivity or native Firefox extension behavior. Do not paste raw diagnostic reports containing local paths or secrets into a public PR; review and redact first.

## 7. Safety / publication boundary

Follow `AGENTS.md`: no direct push to main, forced history rewrite, silent merges, ZIP/binary publication, public filter URL changes or production deployment. The source of truth for published filter subscriptions remains `r20942097-hue/s`. Keep product source, verified build output and runtime results distinct.
