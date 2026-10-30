# Unified Privacy Control (UPC) — Phase 1 read-only evaluator

**Status: prototype under Draft PR #43; not a new content blocker. Release NO_GO.**

## What is implemented

- A deliberately restricted, conservative ABP `||hostname^[$options]` normalizer. It understands a subset of network filters and preserves unsupported rules as `UNSUPPORTED_NOT_VERIFIED`.
- A **verified, pinned Git blob** source reader for `ai/imports/s.json` and the copied `s/main` lists. The source pin is an engineering snapshot, **not** the `s` Draft PR #14 branch.
- Exact normalized overlap detection between `s/main` stable tracking and optional v2 tracking. This is **not** an assessment of EasyPrivacy/uBO Lite active stock lists. Non-overlapping rules are not assumed useful.
- Versioned evidence JSON, a GitHub Actions Markdown summary, count integrity tests and release NO_GO checks.
- Python 3.11/3.14 isolated CI. No third-party Python dependencies, outbound HTTP, browser profile access, proxy certificates, Windows changes or automatic publication.

## Run (repository root)

```sh
python -m unittest discover -s tools/privacy-control -p 'test_*.py' -v
python tools/privacy-control/cli.py --check --report ../upc-coverage.json
```

Reports must be created outside the source checkout. The current pinned baseline is expected to be 9 stable tracking entries, 38 optional v2 entries, 9 exact normalized overlaps, and 29 with no demonstrated exact stable overlap. These fixed counts are a **snapshot-change detector**, not a performance metric. A legitimate new pinned source requires reviewing the baseline and updating the tests and release checks intentionally.

## How to interpret results

| Label | Meaning |
|---|---|
| `EXACT_OVERLAP_WITH_PINNED_STABLE` | Same normalized text and options within the two pinned lists |
| `NO_EXACT_STABLE_OVERLAP_NOT_VERIFIED` | Not exactly present in pinned stable; might be covered by other rules/stock lists |
| `UNSUPPORTED_NOT_VERIFIED` | Complex or unimplemented syntax, including exceptions, cosmetic selectors, URL modifiers |
| `NOT_RUN` | Actual browser stock blocking, real engine matching, real sites and compatibility not measured |
| `NO_GO` | No publication authorized; reports are read-only research |

No rule is classified as safe or effective based solely on string normalization. Domain hierarchy, exception precedence, redirects, first/third-party context, resource-type specificity, CNAME/DNR limitations and browser stock configuration require actual engines and request fixtures.

## Implementation boundaries

- The public subscription authority remains `r20942097-hue/s/main`; `faaff/main` is not a replacement.
- `tools/privacy-control/` is isolated from `browser_filter_lists/` and `integrations/browser-filters/source/s/`.
- Existing CC0-1.0 and GPL-3.0-only sources retain their original license and provenance. The prototype does not copy upstream engine implementations.
- No blocking profiles, DNS routes, TLS certificates, system firewall controls, extension settings or user traffic are modified.
- Next development: pin effective stock rules (with actual enabled configuration); use Ghostery/uBO/AdGuard semantics to test sample requests and exception precedence; isolated Firefox full-uBO/browser HTTP; only then UI and optional DNS.

See [architecture](docs/ARCHITECTURE.md) for the full plan.

## CLI output and security

`--check` verifies pinned integrity and fail-closed counts. Missing source files, Git blob/size mismatch, duplicate rules or a changed baseline are treated as failures. The CLI refuses writing reports under the repo path; GitHub Actions writes temporary outputs outside checkout. No request URLs or user credentials are collected.
