# GPT1 v2.9 — Real-extension offline browser gate (CANDIDATE / NO_GO)

## Current evidence, 2026-10-30 JST

- `faaff` PR #25 (stacked on Draft PR #23) is the integration baseline; existing 47 offline preflight cases previously passed on Ubuntu and Windows with Python 3.11 and 3.14.
- The attached **RPLAY v2.67 Chromium 67-file ZIP** was previously SHA256- and CRC-checked; the independent archive SHA256 observed here is `7bfdc92cc8c5cee421548f5a86a03b4dd4bdd097c088d09c58b4becf6c2cce35`.
- The container provides Linux, Chromium 144.0.7559.96 and Python Playwright 1.57.0. A synthetic ordinary browser can be launched **without** `--no-sandbox` in an unprivileged execution context inside a separate network namespace.
- A real RPLAY archive was supplied to the isolated browser command. The browser process started; **the extension registration / service worker did not become observable**, and the popup was not evaluated. The same lack of worker was observed for a minimal synthetic MV3 extension. Consequently **environment/harness is BLOCKED** and there is no evidence that the product itself failed.
- `chrome://extensions/` was blocked by the headless browser with `ERR_BLOCKED_BY_ADMINISTRATOR`; no inference is made from that page.
- Prior GitHub Actions' Node Playwright 1.62.1 synthetic extension jobs passed, but these are **not** real-product load or user-device tests. A bundled Playwright Chromium or the previously verified GitHub Actions implementation may be necessary. Official Playwright documentation says bundled Chromium is recommended for extension headless testing; using a custom executable can behave differently.

## Gate order (fail closed)

1. External wrapper creates a dedicated Linux **network namespace**, configures loopback, drops privileges, supplies parent namespace receipt via `GPT1_PARENT_NETNS`; verify nonroot and **no default IPv4/IPv6 route**. An environment-variable receipt alone is not authentication: the wrapper/trusted runner configuration is part of the evidence.
2. Check supplied, trusted 64-char SHA256 digest; execute the pre-existing `extension_source_preflight` / `artifact_gate` (CRC, path traversal, Manifest references, decompression bounds). An internally computed digest by itself is not an origin signature.
3. Run a **synthetic positive control** in a disposable Chromium user profile with a normal Chromium sandbox: verify service worker runtime manifest and an extension popup. The browser **must** run with sandbox enabled. Never fall back to `--no-sandbox` for product ZIPs.
4. **Only after** the positive control passes, extract the selected exact extension root from the verified ZIP into a disposable directory with independent member/path/bounds verification. Exercise product's MV3 worker and popup only, using an empty browser profile. **No real site, streaming, downloads, cookies, credentials or external network access.**
5. Emit separate `synthetic_control`, `product_browser`, `real_site`, `recording`, `windows_device`, `release_decision` fields. Positive offline tests may only set `PASS_OFFLINE_ONLY`; `CANDIDATE_NO_GO` remains.

## Source-only integration

- `ai/isolated_extension_e2e.py` — fail-closed CLI and browser wrapper. Python Playwright is a runtime dependency **only for this optional E2E gate**, not a dependency of offline CI/unit tests.
- `ai/tests/test_isolated_extension_e2e.py` — 19 offline regression cases including negative control, wrong SHA, root mismatch, unsafe ZIP member names, symlinks, duplicate names, isolation preconditions and NO_GO invariant.
- Add to `gpt1-workspace-preflight.yml` unit-test job, with Python 3.11/3.14 and Linux/Windows; do not invoke the actual browser from these generic jobs. Real product execution should be a separate manual, isolated job with access to a verified candidate source ZIP and a trusted expected SHA256, never as a public PR artifact.

## Typical isolated-run outline (Linux with authorized user-namespace mapping)

The runner must be isolated before invoking the CLI. This **example is not an installer**; it assumes authorized disposable CI infrastructure and verified UID mappings. For the specific sandbox tested, the wrapper uses an isolated network/user namespace, loopback, and an unprivileged mapped user. Do **not** copy arbitrary external extension source into a persistent normal browser profile.

```sh
# Conceptual: run from a trusted privileged wrapper in a disposable runner.
# On the Ubuntu GitHub runner, use the existing proven network-namespace launcher;
# do not blindly assume these userns mappings exist or work on Windows.
ORIGIN_NETNS="$(readlink /proc/self/ns/net)"
export ORIGIN_NETNS
unshare --user --net --map-users 0:0:3 --map-groups 0:0:3 -- sh -c '
  ip link set lo up
  setpriv --reuid=1 --regid=1 --clear-groups -- env \
    HOME=/tmp XDG_RUNTIME_DIR=/tmp GPT1_PARENT_NETNS="$ORIGIN_NETNS" \
    python3 ai/isolated_extension_e2e.py /path/to/verified-product.zip \
      --sha256 7bfdc92cc8c5cee421548f5a86a03b4dd4bdd097c088d09c58b4becf6c2cce35 \
      --root rplay-stable-player-extension/ --json
'
```

Prerequisites: `chromium` bundled with Playwright is preferred (without custom `--browser-executable`). A fallback system Chromium executable may not load extensions despite launching successfully. The CLI fails closed in that case, rather than claiming product incompatibility.

## Scope and remaining tasks

| Gate | Status |
| --- | --- |
| SHA256 / ZIP CRC / Manifest references | PASS for the previously checked RPLAY candidate; original source provenance not independently signed |
| Isolated browser process, no `--no-sandbox` | PASS in controlled user/network namespace |
| Synthetic MV3 positive control on this container | BLOCKED (worker not observed) |
| Real RPLAY extension worker/popup | NOT VERIFIED, because control does not pass |
| Chrome/Firefox cross-browser E2E | NOT_RUN |
| HLS/DASH recording/MP4 correctness, restart, long-duration | NOT_RUN |
| Windows user device, authenticated sites | NOT_RUN |
| Release | CANDIDATE_NO_GO |

Primary references: https://playwright.dev/docs/chrome-extensions ; https://playwright.dev/docs/api/class-browsertype ; https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/ .