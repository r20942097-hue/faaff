# GPT1 v3.1 | Isolated synthetic MV3 control and ZIP-root support

Date: 2026-10-30. Development candidate only; **CANDIDATE_NO_GO** remains in force.

## Verified background

- Previously, the product ZIP was mandatory to test the synthetic browser harness. This coupled an environment fault to product validation.
- The v2.8 static source verifier recognized root-level `manifest.json`, but v3.0 E2E rejected its `root: .` selector. The 12 inspected inner ZIPs in Three Addons v4 all have root-level manifests.
- 2026-10-30 local actual run: Python Playwright 1.57.0 plus system Chromium 144.0.7559.96, nonroot isolated Linux user/network namespace; Chromium started but the synthetic MV3 worker was **NOT_OBSERVED**. Product was NOT_RUN. No --no-sandbox fallback was used.
- Prior GitHub Actions Node Playwright 1.62.1 + Chromium 156 synthetic control passed. See https://github.com/r20942097-hue/faaff/actions/runs/40938571378 . These are different runtime configurations.

## Independent synthetic-only diagnostic

Execute inside an externally prepared isolated, nonroot Linux network namespace:

```sh
python ai/isolated_extension_e2e.py --synthetic-only --json
```

An explicit system-browser override may be used for isolated diagnostics only:

```sh
python ai/isolated_extension_e2e.py --synthetic-only --browser-executable /usr/bin/chromium --json
```

- The synthetic-only CLI rejects any ZIP, --sha256 or --root argument. No actual product source, real site, cookies, recording, credentials or persistent user browser profile is accessed.
- The trusted wrapper must prove the parent namespace identity. An environment-variable value by itself is not authenticated evidence.
- A PASS needs control status PASS, worker PASS, popup PASS, including a dynamic popup→Worker→storage→popup round trip. Merely launching Chromium or loading an HTML page is insufficient.
- Synthetic-only always leaves product_browser, real_site, recording, windows_device as NOT_RUN and release_decision as CANDIDATE_NO_GO.

## Root-level ZIP support

- Product mode accepts --root . for source ZIPs with manifest.json at their archive root; --root subdir/ is also supported.
- Malformed roots, traversal and duplicate slashes are rejected; nested ZIP safety and bounded CRC checks remain delegated to the existing preflight.
- The trusted expected SHA256 must be supplied independently; digest verification alone does not provide a source signature.

## Regression tests

```sh
python -m unittest discover -s ai/tests -p test_isolated_extension_e2e.py -v
```

37 offline unit tests passed locally; the browser is mocked in these tests. Environment-specific real-browser proof must be recorded independently.

## Next gate

Execute this Python synthetic-only CLI on an isolated runner using a compatible bundled Chromium and the new headless Chromium channel. If the positive control passes, evaluate a SHA-pinned authentic product ZIP in a separate gated job. Do not infer Firefox/Windows device success or release approval.

Official reference: https://playwright.dev/python/docs/chrome-extensions ; https://playwright.dev/python/docs/browsers ; https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/
