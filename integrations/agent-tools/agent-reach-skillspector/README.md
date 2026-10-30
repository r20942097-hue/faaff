# Agent-Reach + NVIDIA SkillSpector — Windows setup candidate

**Status: PROPOSAL / Windows DryRun PASS / production installation NOT_RUN / NOT RELEASED.** This directory contains a proposed PowerShell installer and operator guidance. Adding these files to GitHub does **not** install either tool on the operator's Windows PC, enable new MCP connections, or establish security coverage.

## Source and scope

- Agent-Reach: https://github.com/Panniantong/Agent-Reach (script pins release `v1.6.0` commit [`beabda7486e9a666360b18cdb5c0e759c2c4d20f`](https://github.com/Panniantong/Agent-Reach/commit/beabda7486e9a666360b18cdb5c0e759c2c4d20f)).
- NVIDIA SkillSpector: https://github.com/NVIDIA/SkillSpector (script installs **pinned upstream Git commit `54921c8c7c23008c8af2328d5ab492a904b6ece4`**; review dependencies before production use).
- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- The upstream code is **not vendored** into this repository.
- The PowerShell script is an independently revised derivative of `AgentReach_SkillSpector_Windows_Setup_20261030.zip` prepared in ChatGPT on 2026-10-30. Original ZIP SHA256: `b0ff576f0c657b2fa9d24f15b521ccc760c0399f8e2642698eb110e342fc1ec4`. No ZIP binary is tracked because this repository's governance and source synchronization CI forbid tracked archives.
- Original installer file SHA256 (source input; NOT the revised GitHub script): `b8c552c1bfd9d2d658da7e22087bad87c65e308d5a902aaa1b03e8a8c5c75b37`.

## Windows PowerShell procedure

First check `uv --version`, inspect the script locally, and run from this directory:

```powershell
.\Install-AgentReach-SkillSpector.ps1 -DryRun
.\Install-AgentReach-SkillSpector.ps1
# Review upstream changes before enabling default channels and agent skill links:
.\Install-AgentReach-SkillSpector.ps1 -RunSetup
```

To install one tool at a time:

```powershell
.\Install-AgentReach-SkillSpector.ps1 -Target AgentReach
.\Install-AgentReach-SkillSpector.ps1 -Target SkillSpector
```

`agent-reach setup` is **opt-in** via `-RunSetup` because it installs default channel tools and links/copies agent skill files to detected agent installations. Without `-RunSetup`, installation is staged without auto-enabling channels. `-SkipSetup` remains a compatibility no-op for explicit skipping. If both options are set, the script aborts before changes. If execution policy blocks the reviewed script, a temporary scope is available:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

After installation:

```powershell
agent-reach version
agent-reach doctor --text
agent-reach channels
agent-reach skill
skillspector --help
```

The script skips binaries already on PATH instead of overwriting them. It does not install `uv`, request admin rights, configure optional account logins, or upload credentials. **Do not use `pip install agent-reach`: the unrelated PyPI project may differ from Panniantong's repository.** Audit upstream source, requested permissions, dependency installation, network access, and any browser session / Cookie / API key handling before execution.

## Verification boundary

| Check | Status |
|---|---|
| Original ZIP opened, CRC verified, source files inspected | PASS (2026-10-30) |
| Local SHA-256 of input ZIP and installer recorded | PASS |
| PowerShell execution and `-DryRun` on GitHub-hosted Windows | PASS ([workflow run](https://github.com/r20942097-hue/faaff/actions/runs/41028614540)) |
| Actual Agent-Reach and SkillSpector installation on isolated GitHub-hosted Linux + Windows | PASS (see latest pipeline below) |
| Anonymous public channel reads on isolated GitHub Linux | 4/5 PASS (YouTube platform BLOCKED); user PC/MCP integrations NOT_RUN |
| Runtime security assessment of upstream projects | NOT_RUN |

This PR is only a **source-registration proposal**. Do not merge, release, or deploy without the repository owner's separate approval. Public GitHub history must never contain personal credentials, cookies, or local diagnostic data.

## 2026-10-30 safety revision

- Installer now requires an explicit `-RunSetup` to enable Agent-Reach's default channels and agent skill placement; `-DryRun` never executes commands. Existing install stays untouched unless setup is explicitly requested.
- This paragraph originally documented the initial Windows dry-run gate; **subsequent GitHub CI** installed both CLIs and their dependencies on isolated Linux/Windows runners. Agent-Reach `setup`, private logins and installation on the owner's Windows PC remain NOT_RUN. The on-repository script was changed from the original ZIP, so its checksum is intentionally different from the original ZIP-entry checksum.
- Both Agent-Reach (full `beabda7486e9a666360b18cdb5c0e759c2c4d20f`) and SkillSpector (full `54921c8c7c23008c8af2328d5ab492a904b6ece4`) upstream source commits are pinned. Transitive dependencies are not locked with checksums, so manual provenance review remains mandatory before running on the main Windows PC.
- Upstream procedure: https://github.com/Panniantong/Agent-Reach/blob/main/docs/install.md and https://github.com/NVIDIA/skillspector

### SkillSpector immutable source pin

Latest repository HEAD observed via GitHub on 2026-10-30 was [`54921c8c7c23008c8af2328d5ab492a904b6ece4`](https://github.com/NVIDIA/SkillSpector/commit/54921c8c7c23008c8af2328d5ab492a904b6ece4). The proposed PowerShell installer now pins that exact revision instead of installing an unbounded branch HEAD. **Transitive dependencies remain unresolved/unlocked**, so this does not establish a fully reproducible or independently verified installation.

## Permanent Windows regression gate

`.github/workflows/agent-tools-windows-smoke.yml` runs no-install PowerShell contract checks on pull requests and pushes to main. Verified success on GitHub-hosted Windows: https://github.com/r20942097-hue/faaff/actions/runs/41028614540. The first run exposed missing capture of PowerShell's information stream, subsequently corrected and re-tested. This does not prove live installation, login, CLI access to external sites, or SkillSpector analysis quality.

## Real installation smoke (isolated GitHub runners)

The additional `.github/workflows/agent-tools-install-smoke.yml` installs pinned **uv 0.13.6**, Agent-Reach, and SkillSpector into isolated Linux and Windows GitHub Actions runners, then checks their CLIs without `agent-reach setup`, account logins or real site access. Linux additionally scans a tiny synthetic local skill with `--no-llm` and verifies JSON parsing. Real installation on the user's Windows PC is never performed by GitHub Actions.

- Source commit pins are immutable references; **transitive Python package versions/wheel hashes remain unpinned** and may resolve differently in the future.
- The ephemeral smoke test does not authorize installation on the user's PC, exporting browser credentials, or connecting live MCP services.
- Status: **PASS on Linux and Windows** for actual isolated CLI installation, with benign SkillSpector static scan on Linux. [Workflow run 41030702615](https://github.com/r20942097-hue/faaff/actions/runs/41030702615). Separate Windows PowerShell installer execution also **PASS** on an ephemeral runner: [temporary CI run 41030702664](https://github.com/r20942097-hue/faaff/actions/runs/41030702664).
- Upstream Agent-Reach CLI v1.6 requires Python >=3.10; SkillSpector 2.12.0 requires Python >=3.12,<3.16; use Python 3.12 for compatibility. Source: official `pyproject.toml` files.

## Verified real-install scope (2026-10-30)

- **PASS**: commit-pinned Agent-Reach and SkillSpector installation and CLI invocation on Linux and Windows in GitHub Actions: [41030702615](https://github.com/r20942097-hue/faaff/actions/runs/41030702615).
- **PASS**: benign fixture scan using SkillSpector `--no-llm`, JSON report parsed on Linux, same run.
- **PASS**: actual PowerShell installer in ephemeral Windows with `-Target Both` (setup not requested): [41030702664](https://github.com/r20942097-hue/faaff/actions/runs/41030702664). Temporary changes to required `ci.yml` were removed after the result was captured; the independent `agent-tools-install-smoke.yml` is retained.
- **NOT_RUN**: user's PC installation; Agent-Reach `setup`, login/cookie handling; SkillSpector's LLM analysis/MCP server; full Python dependency lock/wheel hash integrity. **Live anonymous public web channels were subsequently tested in isolated Linux CI** (see newer evidence below).

## Positive security-scanner regression (2026-10-30)

[GitHub Actions run 41032768940](https://github.com/r20942097-hue/faaff/actions/runs/41032768940) **PASS on Linux and Windows installation**. On Linux, a harmless synthetic skill produced valid JSON. A separate inert Python source file containing a direct `exec()` call was never executed, but SkillSpector's static analysis flagged it. With `--fail-on-findings`, the scanner returned exit code 1 and its documented JSON `issues` array was nonempty. This proves detection of that one synthetic risk pattern, not comprehensive malicious-skill coverage.

## Installer identity contract — 2026-10-30

The PowerShell installer now validates the full Agent-Reach v1.6+ JSON version envelope before allowing any optional `setup`: `schema_version=1`, `ok=true`, `action=version`, and a supported semantic version. It rejects malformed, non-version or old responses without overwriting an existing installation. The permanent Windows DryRun test covers a valid response and six invalid cases. SkillSpector's documented `SkillSpector v...` CLI version is validated as well, and a newly installed copy must match the pinned v2.12.0 source. A Windows isolated install CI step exercises that preflight on an actual temporary installation. No account logins or setup are run. These checks are identity/compatibility assertions, not a full malware attestation.

## Verified live Agent-Reach functionality — 2026-10-30

Agent-Reach v1.6.0 was reinstalled from the reviewed **immutable upstream source commit** in GitHub-hosted Linux and Windows. The separate [`verify-agent-reach.py`](verify-agent-reach.py) exercises the real CLI, not a mock. All tests use a fresh temporary `HOME`, deliberately remove GitHub/social tokens from the subprocess environment, have bounded timeouts, and never run `setup`, `add`, `login`, `configure` or a browser session.

**Verified [live run 41067245507](https://github.com/r20942097-hue/faaff/actions/runs/41067245507):**
- **Linux and Windows PASS**: version JSON response and return-code contract; 14 registered channel/action definitions; local-only `doctor` status; read-only `skill` inventory; invalid-action rejection; no state/config creation before live tests.
- **Linux anonymous network probes**: GitHub public repo read via `github-api` **PASS** (1 item), web read of `https://example.com` via `jina` **PASS** (1 item), V2EX `hot` via `v2ex-api` **PASS** (2 items), Bilibili `hot` via `bilibili-api` **PASS** (2 items).
- **YouTube video metadata BLOCKED** (public `yt-dlp` request returned `PLATFORM_BLOCKED`, a platform verification challenge from the GitHub runner). This is neither PASS nor evidence the owner's local browser is blocked. The test stops without bypassing verification or importing cookies.
- **Official `agent-reach check github --search` PASS**, and subsequent `doctor` reflected a fresh `search_ready` state rather than merely an installed binary.
- Other channels require explicit installation/login and were **NOT_RUN**. The initial offline `doctor` reported 3 unverified defaults, 2 needing setup and 9 not added. Offline doctor is NOT a substitute for a network check.

**This proposal is now a functioning read-only public-data smoke harness, not a fully configured Agent-Reach integration.** A pass on ephemeral GitHub runners does not install Agent-Reach into ChatGPT/Codex, enable a user's optional channels, prove Firefox/Windows browser integration, or certify upstream providers. Transitive Python wheels are not hash-locked.

The test's new negative-path security check additionally exercises localhost/private/cloud-metadata/file URL inputs through the CLI and requires `BAD_INPUT` without following untrusted URLs; successful execution is documented in the latest CI check after this revision.

## Locked Agent-Reach dependency verification — 2026-10-30

A separate and committed [Python 3.12 uv project](locked-agent-reach/pyproject.toml) with [universal `uv.lock`](locked-agent-reach/uv.lock) is now the **test authority for Agent-Reach's runtime**. It pins the complete upstream Git revision `beabda7486e9a666360b18cdb5c0e759c2c4d20f`, resolves **20 packages**, and records **147 PyPI distribution SHA-256 hashes** across the supported locked package assets. These numbers are lockfile records, not the number of actually installed wheels on each OS.

On both GitHub-hosted Linux and Windows, CI now runs:
1. `uv lock --project locked-agent-reach --check` to reject an out-of-date dependency lock.
2. `uv sync --project locked-agent-reach --locked --no-dev` to install the immutable resolution in an independent virtual environment.
3. Version and source-integrity checks with [`verify-lock.py`](locked-agent-reach/verify-lock.py) in that environment, including runtime `agent-reach==1.6.0` and `yt-dlp==2026.8.19`.
4. All subsequent `doctor`, `channels`, `check github --search`, localhost/private-URL denial, and anonymous public reads are routed to **that locked executable**, not the separately installed `uv tool` on PATH.

The older `uv tool install` path remains tested for existing Windows PowerShell compatibility. However, **the distributable Windows installer has not yet been switched to a lock-enforcing strategy**; therefore this CI lock does not claim the user's eventual installation is fully pinned. SkillSpector's transitive Python dependencies are still not universally locked. The upstream Git project is immutable, but build-system provenance and all future upstream service behavior are outside this CI guarantee.

[uv official lock and sync documentation](https://docs.astral.sh/uv/concepts/projects/sync/) distinguishes `--locked` (checks lock consistency) from `--frozen` (skips validation). The gate uses the former to avoid accepting stale lockfiles.

Status: **cross-platform locked installation and verification PASS** in [CI run 41069643298](https://github.com/r20942097-hue/faaff/actions/runs/41069643298); subsequent functional-probe routing is verified by the most recent PR checks. No setup, login, secret, Windows user's local environment modification, main merge, release, or browser profile access occurred.
