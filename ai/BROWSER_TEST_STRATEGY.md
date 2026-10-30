# Browser-tooling isolation and acceptance gates (2026-10-30)

Source status and browser availability are separate from any product acceptance decision.

## Tooling and source checks
- `python -m unittest ai.test_audit_environment ai.test_browser_preflight -v`
- `python ai/audit_environment.py . --output evidence.json` (NO_GO until real product tests exist)
- `python ai/audit_environment.py . --require-source watcher` (exit 2 when watcher source absent)
- `python -m pip install -r ai/requirements-browser.txt`
- `python -m playwright install --with-deps chromium firefox`
- `python ai/browser_preflight.py --browser chromium --output chromium.json`
- `python ai/browser_preflight.py --browser firefox --output firefox.json`

## Platform/product E2E still NOT_RUN
- Chromium extension: Playwright persistent context using bundled Chromium and unpacked MV3 source; never use generic Firefox Playwright page tests to claim Firefox extension support.
- Firefox extension: `web-ext lint` and separate Firefox temporary-addon integration with real content script assertions.
- Video recorder: local HLS/DASH and authenticated-URL simulation with redacted fixtures, segment gaps/retries, stop/recovery, MP4/TS integrity using ffprobe.
- Windows native browser integration and real-site tests require separate evidence, logs, versions, and reproducibility.
- Keep immutable source ZIPs and binaries outside this source-only Git repo; use hashes for intake.
- Publishing ownership of `s/main` is unchanged. Do not merge, release, or change URLs without explicit authorization.

## Official references
- https://playwright.dev/python/docs/ci
- https://playwright.dev/docs/chrome-extensions
- https://github.com/mozilla/web-ext
- https://pypi.org/project/playwright/1.64.1/
- https://github.com/actions/upload-artifact
