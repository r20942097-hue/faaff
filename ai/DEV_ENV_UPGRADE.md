# Development environment upgrade / 2026-10-30

This PR adds **toolchain validation** and **read-only candidate ZIP intake**. It does not import, execute, sign or publish any existing product. Source presence is not proof of product execution.

## Commands (from repository root)

```bash
python -m unittest ai.test_audit_environment ai.test_browser_preflight ai.test_extension_fixture_e2e ai.test_archive_intake -v
python ai/audit_environment.py . --output environment-readiness.json
python ai/audit_environment.py . --require-source watcher
# The strict source command exits 2 while watcher sources are absent.
python ai/archive_intake.py "/path/to/untested-product.zip" --output zip-intake.json
python -m pip install -r ai/requirements-browser.txt
python -m playwright install --with-deps chromium firefox
python ai/browser_preflight.py --browser firefox --output firefox-toolchain.json
python ai/extension_fixture_e2e.py --output chromium-extension-fixture.json
```

The disposable Chromium MV3 fixture tests a Content Script loaded on a loopback origin and a message round-trip to a service worker, with a fresh temporary user data directory. The test depends on local HTTP access; environments blocking loopback may fail this gate despite normal browser startup. Do not silently mark a failure as PASS. Browser and localhost requests never contact external websites in this test.

`zip-intake/v1` hashes the archive, reads bounded members to verify ZIP CRC, checks path traversal, duplicate case-folded names, symlinks, encrypted entries, decompression ratios and size limits. It **never extracts** or executes the content. `PASSED_INTAKE_ONLY` is not a signature, provenance or safety guarantee; dynamic product tests remain required. Do not commit ZIP archives to this repo.

## CI evidence and status

- `environment-readiness.yml`: Ubuntu 24.04 and Windows 2025, Python 3.14; run audit/fixture contracts and attach JSON.
- `browser-toolchain.yml`: Chromium and Firefox Playwright in-memory page fixture; extension loading is **NOT_RUN** there.
- `chromium-extension-fixture.yml`: load disposable MV3 Chromium extension and verify actual page injection + service-worker messaging; **not** a product-specific E2E.
- `ai/archive_intake.py`: user-supplied ZIP can be inspected locally in isolation, without changing its bytes.
- `ai/audit_environment.py`: source SHA-256 and missing source list. Product release-readiness remains `NO_GO`.

## Next-stage acceptance (requires verified product sources)

1. Verify immutable source ZIP SHA-256 and provenance; record variant and dependency paths separately. No promotion based solely on the filename.
2. Run Firefox `web-ext lint` and `web-ext run` for actual temporary add-on, then execute real content-script assertions using a separate Firefox-supported driver.
3. Run Chromium unpacked MV3 E2E against the real extension, then test persistent worker recovery, popup/options, media listener, and Storage.
4. Run local synthetic HLS/DASH capture with timed stream interruption, segment omissions/duplicates, authenticated requests without recording secrets, stop/recover, FFprobe packet and decode checks, and CRC-backed saved file logs.
5. Run Windows-native Firefox/Chromium real product E2E with reproducible version inventory and regression evidence. Maintain `NO_GO` until verified.

## Sources

- Playwright Chrome extension testing: https://playwright.dev/docs/chrome-extensions
- Playwright CI: https://playwright.dev/python/docs/ci
- PyPI Playwright 1.64.1: https://pypi.org/project/playwright/1.64.1/
- Mozilla web-ext: https://extensionworkshop.com/documentation/develop/getting-started-with-web-ext/
- ZIP format processing: https://docs.python.org/3/library/zipfile.html

## Constraints
`faaff` remains an engineering hub; `s/main` remains the live filter distribution authority. Do not alter subscribed raw URLs. Keep `main` protected and candidate-only branches unmerged until explicit owner authorization.
