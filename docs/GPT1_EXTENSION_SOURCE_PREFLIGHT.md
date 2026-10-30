# GPT1 v2.7 | Extension source preflight proposal

Date: 2026-10-30. Proposed against `faaff` Draft PR #23, HEAD at review time `48a00b13320428e7aa96e4fae580b9342ac49c93`. No main-branch changes or release/publication actions are authorized by this package.

## Purpose and trust boundary

The new `ai/extension_source_preflight.py` scans unpacked extension source directories or ZIP archives without executing code, launching a browser, accessing the network, or extracting ZIPs. It identifies root and multi-root `manifest.json` files; checks manifest JSON, MV2/MV3, required identity/version fields, local source-file references (background workers, popups, content scripts, options, icons, side panels, overrides); and detects source symlinks, case/Unicode collisions and dangerous path components. A broad `<all_urls>` host permission produces a warning, not a false runtime failure.

ZIPs are validated by the existing `ai/artifact_gate.py`, including its CRC, path and size safety checks, **before** any manifest contents are read. Optional `--sha256` binds a ZIP to a trusted expected digest; a digest computed alone does not establish provenance. Manifests are only read up to 256 KiB + 1 byte. A source directory with unknown nested ZIPs, or a ZIP containing nested ZIPs, is `PARTIAL`, never silently `PASS`.

## Commands

From repository root, after copying the two Python files into `ai/` and `ai/tests/`:

```sh
python -m unittest discover -s ai/tests -p test_extension_source_preflight.py -v
python ai/extension_source_preflight.py /path/to/unpacked/extension --json
python ai/extension_source_preflight.py /path/to/source.zip --sha256 TRUSTED_64_LOWER_HEX --json
```

Exit codes: `0` = PASS for offline source layout only; `1` = FAIL; `2` = PARTIAL (e.g. source-only ZIP, nested uninspected ZIP). Even PASS always reports `browser_install`, `browser_e2e`, `real_site_e2e`, and `windows_device` as `NOT_RUN`, with `release_decision: CANDIDATE_NO_GO`.

## Integration

Add the new test step to the existing `.github/workflows/gpt1-workspace-preflight.yml`, immediately after `Test bounded ZIP artifact security gate`:

```yaml
      - name: Test extension source preflight (offline)
        run: python -m unittest discover -s ai/tests -p test_extension_source_preflight.py -v
```

Do **not** create a separate action workflow unless its SHA pins are included in the repository's Actions lockfile and audit graph. The workflow addition above uses no additional GitHub Actions dependency. Verify `lockfile_parity.py` and `workflow_supply_chain.py` when integrating.

The source packages to be checked (RPLAY/StreamHarbor/YouTube Optimizer/Three Addons) are not bundled here and are not independently verified by this proposal. Product archives must be traced to their original release candidate, expected SHA256 and source commit before their results can be entered into the product QA evidence registry. Nothing here establishes genuine browser installation, service-worker lifecycle, captured media correctness, authenticated site compatibility, secure Chromium sandboxing, or release approval.

## Local verification scope

26 synthetic regression tests executed under Python 3.13.5 on the ChatGPT isolated container and all passed on 2026-10-30. These tests mock `artifact_gate.inspect` for archive interactions; they do not yet constitute an integration test against the complete GitHub checkout. Testing on Python 3.11/3.14, GitHub Actions, Windows, real extension ZIPs and Firefox/Chromium integration is **NOT_RUN**. The next step is to merge this candidate **into a feature branch**, run existing CI, and then select an authentic product ZIP for a full preflight. `PUBLICATION_HOLD`, `NO_NEW_INTERNAL_PUSH`, main protection, and the requirement for owner approval before publishing/merging remain in force.

## References

- Existing integration Draft PR: https://github.com/r20942097-hue/faaff/pull/23
- GitHub Actions baseline: https://github.com/r20942097-hue/faaff/actions
- Playwright real extension testing: https://playwright.dev/docs/chrome-extensions
- Mozilla web-ext run: https://extensionworkshop.com/documentation/develop/web-ext-command-reference/
## v2.8 | Extended packaged-resource validation (2026-10-30)

Follow-up to v2.7 after GitHub PR #25 passed 19 checks (one unrelated check skipped). This revision closes false-positive source-layout PASS cases:

- `declarative_net_request.rule_resources[]`: valid IDs, unique IDs, boolean `enabled`, mandatory local `path` and packaged file presence (including disabled rulesets).
- `sandbox.pages[]`: local files must be packaged when declared.
- `web_accessible_resources`: MV2 string arrays, MV3 objects with `resources` and `matches`/`extension_ids`; referenced files must exist; leading slash and `*` glob patterns are supported. An unmatched glob is a **warning**, not a claim of browser failure.
- Reject invalid background and content-script field types that were previously ignored.
- Includes actual `artifact_gate.py` integration fixtures when run inside the full repository: one valid ZIP and one path-traversal ZIP. The standalone package skips only those two integration fixtures when `artifact_gate.py` is absent. GitHub CI must run them rather than skip them.

This remains an offline, bounded manifest/source-layout check; it **does not** validate DNR rule syntax/semantics, all browser-specific manifest constraints, actual extension installation, popup/service worker runtime, real-site behavior, Windows end-device, or release status. The product archive's trusted source SHA is still required before its evidence can be used in release decisions.

References (checked 2026-10-30):
- Chrome DNR: https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest/
- Mozilla DNR manifest: https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/declarative_net_request
- Mozilla WAR manifest: https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/web_accessible_resources
- Chrome WAR migration: https://developer.chrome.com/docs/extensions/develop/migrate/manifest
