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
| Actual Agent-Reach and SkillSpector installation | NOT_RUN |
| Channel connectivity and MCP integration | NOT_RUN |
| Runtime security assessment of upstream projects | NOT_RUN |

This PR is only a **source-registration proposal**. Do not merge, release, or deploy without the repository owner's separate approval. Public GitHub history must never contain personal credentials, cookies, or local diagnostic data.

## 2026-10-30 safety revision

- Installer now requires an explicit `-RunSetup` to enable Agent-Reach's default channels and agent skill placement; `-DryRun` never executes commands. Existing install stays untouched unless setup is explicitly requested.
- Windows **dry-run** was executed successfully on GitHub-hosted Windows. Real installation, Agent-Reach setup, and dependency downloads are NOT_RUN. The on-repository script was changed from the original ZIP, so its checksum is intentionally different from the original ZIP-entry checksum.
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
- **NOT_RUN**: user's PC installation; Agent-Reach `setup`, login/cookie handling or live web channels; SkillSpector's LLM analysis/MCP server; full dependency lock/wheel hash integrity.

## Positive security-scanner regression (2026-10-30)

[GitHub Actions run 41032768940](https://github.com/r20942097-hue/faaff/actions/runs/41032768940) **PASS on Linux and Windows installation**. On Linux, a harmless synthetic skill produced valid JSON. A separate inert Python source file containing a direct `exec()` call was never executed, but SkillSpector's static analysis flagged it. With `--fail-on-findings`, the scanner returned exit code 1 and its documented JSON `issues` array was nonempty. This proves detection of that one synthetic risk pattern, not comprehensive malicious-skill coverage.

## Installer identity contract — 2026-10-30

The PowerShell installer now validates the full Agent-Reach v1.6+ JSON version envelope before allowing any optional `setup`: `schema_version=1`, `ok=true`, `action=version`, and a supported semantic version. It rejects malformed, non-version or old responses without overwriting an existing installation. The permanent Windows DryRun test covers a valid response and six invalid cases. SkillSpector's documented `SkillSpector v...` CLI version is validated as well, and a newly installed copy must match the pinned v2.12.0 source. A Windows isolated install CI step exercises that preflight on an actual temporary installation. No account logins or setup are run. These checks are identity/compatibility assertions, not a full malware attestation.
