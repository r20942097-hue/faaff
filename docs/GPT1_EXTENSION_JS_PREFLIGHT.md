# GPT1 v3.4 — JS syntax and MV3 worker import preflight

**Scope:** Offline source review only; not extension installation, real-browser execution, recording, packaging provenance, or release approval. `CANDIDATE_NO_GO` remains mandatory.

## Motivation / official references

- Chrome Manifest V3 supports `importScripts()` in classic extension service workers and static `import` in `background.type="module"` workers, but dynamic `import()` is not supported. [Chrome service-worker basics](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/basics).
- Node `--check` parses JS without executing it. [Node CLI](https://nodejs.org/api/cli.html#-c---check).
- Playwright extension E2E requires a persistent Chromium profile and the actual extension worker. [Playwright Python](https://playwright.dev/python/docs/chrome-extensions).
- Firefox's MV3 event page is not equivalent to Chromium's MV3 worker. [MDN background](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background).

## Command

```bash
python ai/extension_js_preflight.py /path/to/verified-source.zip \
  --sha256 TRUSTED_64_CHAR_LOWERCASE_SHA256 \
  --root rplay-stable-player-extension/ --json
```

The user must supply an expected digest from an **independently trusted build receipt**. Computing a digest during the check does not authenticate source origin. Never add candidate ZIPs, signed URLs, profiles, browser data, or credentials to public GitHub repos or CI artifacts.

This utility calls `extension_source_preflight.inspect()`, which calls the pre-existing `artifact_gate` to verify ZIP structure, CRC and bounded archive layout. Only after both gates PASS does it read JavaScript bytes from the ZIP. JavaScript files are supplied to `node --check --input-type=commonjs|module` over stdin; JS is never evaluated. Module imports directly reachable from a worker declared with `type="module"` receive module parse mode. The tool checks statically detectable literal `importScripts('file.js', ...)` references against files in the chosen extension root. The script uses a conservative textual heuristic, **not a complete JavaScript parser**. Unrecognized dynamic imports or missing Node produce `PARTIAL`, not PASS. Passing does not prove `importScripts` will execute, popup JS will execute, a background service worker will register, or API methods will work.

Result meanings:

| Status | Meaning |
| --- | --- |
| `PASS_SYNTAX_REFS_ONLY` | CRC/manifest prerequisites passed, Node syntax checks passed and all detected literal worker imports were present; no unsupported/unknown cases detected by the heuristic |
| `PARTIAL` | Missing tool, unparseable/dynamic imports, module graph ambiguity, or another unresolved check |
| `FAIL` | Digest mismatch, artifact preflight failure, specified root unavailable, invalid syntax, or a detected missing/unsafe literal worker import |

Every result preserves `browser_e2e=NOT_RUN`, `recording=NOT_RUN`, `windows_user_device=NOT_RUN`, `release_decision=CANDIDATE_NO_GO`.

## Local evidence, 2026-10-30

RPLAY v2.67 Chromium 67-file source ZIP (not checked into repository), SHA256 `7bfdc92cc8c5cee421548f5a86a03b4dd4bdd097c088d09c58b4becf6c2cce35`: Node 22.16 `--check` succeeded on **49/49 JS files**. The classic MV3 background file contains four detected literal imports, all present: `session_export_ledger.js`, `export_manager.js`, `creator_registry.js`, `media_catalog.js`. Prior ZIP/manifest static checks passed separately. **Local full integration with the repository artifact_gate was not rerun**; GitHub CI runs full synthetic integration tests for this utility. A trusted independent build receipt and actual product browser E2E are outstanding.

## Tests and boundaries

`python -m unittest discover -s ai/tests -p test_extension_js_preflight.py -v`: 21 synthetic tests, including two actual-`artifact_gate` integration tests. When run from an isolated source-only bundle without `artifact_gate.py`, 19 PASS / 2 SKIP; in the checked-out repository, neither should skip. The source ZIP is never executed and must remain outside public GitHub.

Subsequent steps: use verified SHA256 and only the approved isolated browser harness with synthetic positive control to load RPLAY; separately test Firefox and long-running synthetic HLS/DASH capture, file integrity, crash recovery, and Windows end device.