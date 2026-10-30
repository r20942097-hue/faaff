# Tool and data readiness / 2026-10-30

This page complements, **does not replace**, `ai/PROJECT_STATE.json`, `ai/HANDOFF.md` and `ai/projects.json`. For source/build state, Git commits and actual CI runs take precedence over a copied inventory.

## Priorities

| Class | Status | Meaning | Next practical step |
|---|---|---|---|
| GitHub-native CI, CodeQL, Dependabot, Dependency Review, filter validators | MAIN_PRESENT | Existing, do not duplicate | Keep required checks and stable filter URLs |
| actionlint, zizmor, Gitleaks | DRAFT_VERIFIED | PR [#36](https://github.com/r20942097-hue/faaff/pull/36), static and synthetic positive controls | Review remaining ignored zizmor findings before required-check promotion |
| Agent-Reach, SkillSpector, uv | DRAFT_VERIFIED_SYNTHETIC | PR [#35](https://github.com/r20942097-hue/faaff/pull/35), ephemeral OS installs and synthetic scans | Python cross-platform locking and actual target validation |
| MCP Inspector | DRAFT_VERIFIED_SYNTHETIC | PR [#37](https://github.com/r20942097-hue/faaff/pull/37), local stdio and negative-path checks | Only integrate an approved, scoped MCP server |
| Playwright, Mozilla web-ext | DRAFT_VERIFIED_SYNTHETIC | PR [#38](https://github.com/r20942097-hue/faaff/pull/38), Chromium MV3 mock, Firefox page, static addon lint | Obtain actual extension sources; native Firefox runtime test |

The main blockers are **authoritative RPLAY and three-add-on source trees, their version-to-hash mapping, real product test fixtures, and the native Firefox validation host**. Neither installing another CLI nor repeating synthetic tests resolves a missing product source.

## Required data contract

Each product import should carry the following, stored in a source-specific area after review:

- Product/version and complete source commit or immutable artifact hash; original download/ownership reference.
- Manifest, permissions, browser/OS support, content-script/background architecture, dependency versions and build instructions.
- Safe synthetic fixtures and acceptance behavior (including interruption, restart, corrupted input and settings round-trip as relevant).
- Distinct test evidence: static, dependency audit, isolated install, synthetic browser/API, actual target site, actual user-device. No inferred PASS.
- No credentials, account cookies, personal browsing profiles, live recordings, original ZIPs or binaries committed to this hub.

### Concrete follow-on execution order

1. **Source provenance:** locate and verify current authoritative RPLAY and three-addon source. If available only in archived ZIPs, inspect in isolated workspace, record hashes and extract only reviewable code; do not automatically upload archives or private data to public GitHub.
2. **Product test mapping:** reuse [PR #38](https://github.com/r20942097-hue/faaff/pull/38) and [PR #37](https://github.com/r20942097-hue/faaff/pull/37) to write product-specific tests, rather than building another generic automation framework.
3. **Python dependency reproducibility:** use a per-project `pyproject.toml` and generated `uv.lock` from pinned upstream source references, then `uv lock --check` and `uv sync --locked`. Evaluate OS/Python markers and binary hashes per Linux/Windows. uv's universal lock is designed to encode platform markers, but no lock has yet been verified for the two external agents. <https://docs.astral.sh/uv/concepts/projects/sync/>
4. **Security evidence:** resolve or document existing zizmor suppressions and review the three low-severity Mozilla lint dependency advisories. Do not claim complete safety from an audit showing zero known high-severity issues.
5. **Real-device gates:** Firefox 159 extension/API and Windows recording/long-duration/forced-termination tests remain separate human/isolated hardware gates.

## Maintenance

The machine-readable inventory is [`ai/tooling-readiness.json`](tooling-readiness.json). Validate it with `python ai/check_tooling_readiness.py`. PR status and evidence age must be refreshed before a promotion or merge decision.

**Authority/permissions:** `faaff` remains the integration hub. `r20942097-hue/s` remains the primary filter distributor. P0 / PUBLICATION_HOLD applies; Draft PRs are proposals, not installed production components. No `main` push, auto-merge, release, URL mutation or product publication is authorized here.
