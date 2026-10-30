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


## 2026-10-30 verified source-candidate intake

The owner's ChatGPT Library contains actual candidate ZIPs that are **not** on GitHub main. All local checks below were read-only in an isolated directory. Only non-secret hashes, version metadata and findings are added to this public Draft PR. Raw archives, any personal recordings, logs or credentials were never uploaded to GitHub.

| Candidate | Independent verification | Gate |
|---|---|---|
| RPLAY Stable Player v2.68.0 | 5,425 entries, ZIP CRC PASS, 0 unsafe paths, 47 Python test modules and MV3 manifests identified | **NO_GO**, real-site and real-browser NOT_RUN |
| Three Addons v11 | ZIP CRC PASS and six inner packages verified against sizes and SHA-256 in package manifest | GO_CANDIDATE, comparison reference |
| Three Addons v12 | ZIP CRC PASS, six nested packages verified, JavaScript static syntax **226/226 PASS** using Node 22.16.0, bundled DataTools 1.4.0 --selftest **41/41 PASS** | GO_CANDIDATE, not a released build |

The v12 inner sources are StreamHarbor v2.71.1, OmniStream & YouTube Optimizer v2.13.0, Tab & Stream Workspace v0.80.0 for both Firefox and Chromium. RPLAY v2.68.0 is an **independent older candidate**, not interchangeable with StreamHarbor v2.71.1.

A previously mentioned v13 archive has **not been located in the inspected Library folder**; do not promote v12 over an uninspected newer authoritative version. GitHub branch proposal/rplay-3genre-2026-10-28 is a prototype, not a replacement for the complete RPLAY runtime.

### Intake and reproduction

- Machine-readable observed candidate inventory: ai/candidate-source-observations.json.
- Offline checker: python ai/check_candidate_archive.py <local-candidate.zip>. It does not extract, execute code, connect to external services or copy ZIPs to GitHub. Validates path safety, size, CRC, SHA-256 sums and nested package manifests.
- Synthetic regressions: ai/test_candidate_archive.py. They deliberately use generated fake archives; real candidate archives remain Library-only and are not ingested by public CI.

### Current official guidance

- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/): use a committed universal uv.lock, verify via uv lock --check, install with uv sync --locked once the project and source references are selected.
- [Mozilla web-ext command reference](https://extensionworkshop.com/documentation/develop/web-ext-command-reference/): static lint does not substitute for native Firefox extension runtime testing.
- [Firefox Gecko manifest details](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/browser_specific_settings): verify Gecko ID, minimum version and any data-collection permissions.
- [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations): reserve for distributable builds; not an assertion that synthetic tests prove production safety.

### Remaining gates

Review actual candidate source and provenance in a private isolated workspace, identify newer canonical versions, then reuse the Playwright/Firefox and MCP test infrastructure on reviewed product code. All real RPLAY service, long-duration recording, Windows Firefox 159 and user machine tests remain NOT_RUN. Publication and main merge require separate owner approval.

## 2026-10-30 follow-up: real-source smoke and manifest gate

- **RPLAY v2.68.0 source-only local tests**: Python unit tests 41/41 PASS (ledger cross 15, assembly 13, self cross report 13), JavaScript Node tests 47/47 PASS (21, 14, 12 respectively). In total 88 focused tests. This is a subset of the candidate's suite and **does not** assert successful live recording or completion of all published test claims.
- **Three Addons v12 manifest references**: both browser packages of the three products were inspected locally. Referenced background scripts, service worker, declared content scripts, icons and popup/options pages were all present; the new validator reports each package's startup mode, listed permissions, declared hosts and review flags. This is validation, not automatic permission minimization.
- **Permission review**: StreamHarbor's Chrome/Firefox manifest declares `https://*/*`. It is an important site-scope review item but was deliberately **not** removed because broad host access may be required for the recorder's current architecture. Narrowing it requires explicit site-by-site behavior testing.
- **Chromium local runtime**: an attempt to load the actual v12 Chrome extension in this ephemeral local Chromium 144 environment did **not** expose a service worker; the environment also blocked `chrome://extensions/`. The result is **BLOCKED by local browser environment / NOT_VERIFIED for the product**, not an observed product failure. Existing PR #38 synthetic Chromium PASS is a separate test and cannot replace this gate.
- **Manifest checker hardening**: new synthetic negative tests cover missing worker/background resources, missing popup files, invalid manifest field types, broad host access as an advisory, and sensitive API permissions. Tests must pass without executing scripts from archives.

The original archived candidates remain unchanged, and none are published into this public repository. Progress is recorded in `ai/candidate-source-observations.json`.
