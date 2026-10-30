# Agent-Reach + NVIDIA SkillSpector — Windows setup candidate

**Status: PROPOSAL / NOT_RUN on Windows / NOT RELEASED.** This directory contains a proposed PowerShell installer and operator guidance. Adding these files to GitHub does **not** install either tool on the operator's Windows PC, enable new MCP connections, or establish security coverage.

## Source and scope

- Agent-Reach: https://github.com/Panniantong/Agent-Reach (script targets tag `v1.6.0`).
- NVIDIA SkillSpector: https://github.com/NVIDIA/SkillSpector (script installs **un-pinned upstream Git HEAD**; review and pin a commit before production use).
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
| PowerShell execution and `-DryRun` on Windows | NOT_RUN |
| Actual Agent-Reach and SkillSpector installation | NOT_RUN |
| Channel connectivity and MCP integration | NOT_RUN |
| Runtime security assessment of upstream projects | NOT_RUN |

This PR is only a **source-registration proposal**. Do not merge, release, or deploy without the repository owner's separate approval. Public GitHub history must never contain personal credentials, cookies, or local diagnostic data.

## 2026-10-30 safety revision

- Installer now requires an explicit `-RunSetup` to enable Agent-Reach's default channels and agent skill placement; `-DryRun` never executes commands. Existing install stays untouched unless setup is explicitly requested.
- Actual Windows execution, Agent-Reach setup, and third-party dependency network fetch are NOT_RUN. The on-repository script was changed from the original ZIP, so its checksum is intentionally different from the original ZIP-entry checksum.
- Only `v1.6.0` Agent-Reach source archive is pinned; dependencies and SkillSpector Git HEAD are not content-addressed, so manual provenance review remains mandatory before running on the main Windows PC.
- Upstream procedure: https://github.com/Panniantong/Agent-Reach/blob/main/docs/install.md and https://github.com/NVIDIA/skillspector
