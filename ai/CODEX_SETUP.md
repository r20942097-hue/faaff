# Codex readiness and first-task runbook

This page is the shortest route from **Codex account access** to a **verified repository task**. It does not install another agent, duplicate `AGENTS.md`, or certify any product runtime. The authoritative state remains `ai/PROJECT_STATE.json`; current work is in `ai/HANDOFF.md` and `ai/WORK_QUEUE.md`.

## 1. Distinguish the three independent gates

| Gate | How to establish it | Failure / unknown |
| --- | --- | --- |
| **ACCOUNT / CLOUD** | In the intended ChatGPT account and workspace, open Codex, create and publish a cloud environment, and successfully start a task in it. | A ChatGPT GitHub connector alone does **not** prove Codex cloud access. Account quota, workspace switches and cloud task startup are not verifiable from this repo. |
| **REPOSITORY** | Add `r20942097-hue/faaff` to that environment; inside its task, verify repository identity, current HEAD and read `AGENTS.md`. | Access through a different connector or a successful public GitHub API read does **not** prove the Codex task can fetch or push. |
| **PRODUCT** | Independently verify the selected product's full source/version/hash, relevant build, targeted checks, browser and device E2E. | Passing the hub's Python, filter or synthetic CI does **not** establish RPLAY/YouTube/add-on product readiness. |

Codex Cloud setup and limitations: https://help.openai.com/en/articles/20001545-using-codex-cloud  
Codex plan and CLI/Windows entry points: https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan

## 2. Minimal safe setup (Codex web / desktop)

1. Sign in using the intended ChatGPT account and workspace. Create a **cloud environment** on web or desktop, connect the intended GitHub account, and select the exact repository `r20942097-hue/faaff`. Environment access, GitHub permissions and individual task Git configuration are distinct.
2. Start with the existing repository runtime; **do not preinstall Agent-Reach, SkillSpector, MCP servers, browser extensions, or extra credentials**. Add a dependency only if a scoped test actually requires it, with provenance and version control.
3. Publish the environment only after its setup check works. Do not add real service cookies, login tokens, customer content or recordings as task prompts, commits or CI fixtures.
4. Start a **read-only inspection task** first. For a future code change, use an isolated proposal/feature branch and a Draft PR; no direct push to main.

If Codex environment creation, repository selection, task startup or Git push fails, record the **exact failed stage**. Treat that stage as BLOCKED; do not infer it was fixed from unrelated CI.

## 3. First repository task — copy into Codex

> Read `AGENTS.md`, `ai/README.md`, `ai/projects.json`, `ai/PROJECT_STATE.json` and `ai/HANDOFF.md`. Inspect the actual repository, branch and HEAD SHA; explain the difference between `faaff/main` engineering/bootstrap, `s/main` live filter distribution, and any external product ZIP or Draft PR. Do not write, install dependencies, alter public subscriptions, merge, release or use credentials. Run the relevant **existing offline checks** below, reporting the actual exit codes and PASS/FAIL/BLOCKED/NOT_RUN. State separately whether the exact RPLAY/three-addon product sources and actual Windows/Firefox/browser E2E are present. Give a short, concrete next step; do not mark unexecuted work PASS.

Suggested commands from the repository root:

```sh
git remote -v
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

## 4. Acceptance and handoff

Record these fields in the task response, not in a new competing state registry:

- **Account/Cloud:** environment and task startup PASS, FAIL or NOT_RUN, independently of repository access.
- **Repo:** full repository name, branch, exact HEAD SHA, clean/dirty worktree, instructions read.
- **Checks:** command + exit code + relevant output for each actually executed check.
- **Source provenance:** product/version and source commit or immutable artifact hash, or BLOCKED_BY_SOURCE.
- **Verification scope:** hub/static, synthetic, installed browser extension, actual target site, Windows/Firefox native run — each separately.
- **Changes and next step:** modified paths, PR URL, rollback, owner approval needed; do not upgrade Draft/GO_CANDIDATE to production-ready.

Do not add a new CI workflow solely for Codex access: **only an authenticated Codex task can confirm its own cloud connection**. Reuse the existing hub and product-specific checks. Current proposed toolchains and source gaps are described in Draft PR #35–#39; confirm their actual state before adopting them.

## 5. Optional local Windows Codex diagnosis

Only if Codex CLI is already installed on the user's machine, `codex doctor` can diagnose its local startup/connectivity and `/status` inside an active CLI session can show usage. These commands **do not** validate Codex Cloud or native Firefox extension behavior. Do not install software on the owner's Windows production profile as a substitute for isolated testing.

## 6. Safety / publication boundary

Follow `AGENTS.md`: no direct push to main, forced history rewrite, silent merges, ZIP/binary publication, public filter URL changes or production deployment. The source of truth for published filter subscriptions remains `r20942097-hue/s`. Keep product source, verified build output and runtime results distinct.
