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
python tools/privacy-control/cli.py --check --report ../upc-coverage.json --html ../upc-coverage.html
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

## Phase 1.5: actual pinned engine comparison

The CI now also installs the pinned uBlock Origin matching engine and locked Ghostery 2.20.1 dependency **outside the publishing pipeline**. It verifies each of the 47 tracking rules from the two pinned lists against six synthetic request cases (third-party, subdomain, first-party, hostname boundary, URL text, image), comparing both engines. Separate in-memory exception tests ensure that explicit `@@` overrides win. No dynamic browser extension or production website is used.

Run the engine matrix in CI; it requires the verified `s` engine bundle and the lockfile. An isolated engine match confirms parser/selector behavior on synthetic traffic, **not** incremental blocking over stock subscriptions. The stock-coverage and real-site markers remain `NOT_RUN`.

## Offline HTML viewer

`--html` generates a self-contained, Japanese-language **read-only** report
with all candidate rule classifications and the current evidence limitations.
It does not execute JavaScript, load fonts/assets or call remote services; its
CSP blocks scripts and external resources. Raw rules are HTML-escaped and the
report is written outside the Git checkout. It is a static review artifact,
**not** proof of current browser protection or a management extension.

## Pinned EasyPrivacy upstream comparison (Phase 2a)

The engine comparison optionally reads **five immutable EasyPrivacy source
components**, pinned to an exact upstream Git commit with byte-size and Git
blob SHA checks. Source is downloaded only into isolated CI temporary space;
the repo stores only the path/size/hash manifest. This prevents invisible
upstream drift and respects EasyPrivacy attribution/licensing.

This is deliberately **NOT the full compiled EasyPrivacy subscription**,
nor proof that a particular browser has enabled these lists. The selected
fragments include third-party, general, specific and allowlist components.
The synthetic comparison runs 38 pinned candidate domains against six
request scenarios in both the official uBO matching engine and locked
Ghostery. It compares the selected source fragments against their union
with candidate v2 rules. Results distinguish existing synthetic matches,
additional synthetic matches, matching regressions and engine disagreement;
none should be confused with live user traffic or real-world privacy benefit.

EasyList contributors' rights: the upstream repository is dual licensed under
GPL v3-or-later / CC BY-SA 3.0-or-later. The source itself is **not copied
into git**; records include provenance and the official license reference:
https://easylist.to/pages/licence.html .

Run in ephemeral CI under `pinned-upstream-stock-comparison`. All network
fetches are bounded, pinned, and validated before being used. Any mismatch
fails closed. Approved publication remains **NO_GO**; browser real stock
configuration, Firefox full-uBO, and real sites are still not verified.

### Phase 2b: candidate-level explainability and fail-closed evidence

The selected-source comparison now tests **seven** scenarios per each of 38 candidate
hosts: third-party scripts/images/XHR, subdomains, first-party traffic, boundary
hosts and URLs containing the host only as text. For each request, two real
engines are evaluated both *before* and *after* adding the candidates:
**266 synthetic requests, 1,064 engine observations**.

The machine-readable report contains all raw request-case booleans and a
38-host classification of stock-fragment matches and additional synthetic
matches. `verify_stock_report.py` independently recomputes every count,
checks source blob provenance, ensures the three negative controls never gain
a new block, detects false assertions of verified live-site safety and rejects
automatic adoption. It also verifies that per-host summaries agree with all
underlying cases. The report itself remains in temporary CI storage and may
be regenerated with pinned sources.

The absence of an incremental match is NOT proof that an entire default
browser profile covers the candidate. Likewise the presence of an incremental
match is NOT proof of real-world privacy benefit. No upstream changes are
automatically promoted.

### Japanese standalone review

The validated `upc-stock-fragment-comparison/v1` JSON can now be rendered
offline through `verify_stock_report.py --html <output.html>`. The HTML
contains a 38-host comparison table: baseline synthetic matches versus the
additional candidate matches for uBO and Ghostery. It is a **read-only static
file**, with HTML escaping, no JavaScript, no remote fonts/assets, and a
restrictive Content Security Policy. Generated outputs remain outside Git.

The `pinned-upstream-stock-comparison` CI job also renders the viewer to its
temporary runner directory and includes the candidate-delta host list in the
Actions step summary. This is *not* proof of real sites or actual enabled stock
subscriptions; no automatic filter adoption is authorized.

## Phase 2c: full official EasyPrivacy template **source components** (new)

To reduce the uncertainty from the prior five-component benchmark, an additional
independent CI job resolves the **39 components included by**
`easylist/easylist/easyprivacy.template` at immutable upstream commit
`a69e7f5f3ed2b4893796da9b37bd2db9b6896eb1`. The lock records each
official Git blob SHA and length, including `template_header.txt`, plus the
original template blob. Source inputs total **1,508,164 bytes**. The template
itself is verified and its include order must equal the manifest exactly.

`fetch_full_stock.py` fetches all sources into CI temporary space, verifies
every blob, compares the template include order and aborts on missing/extra
entries. `compare_full_stock.mjs` reuses the 38-host, 7-case synthetic
comparison under the official pinned uBlock Origin and Ghostery engines.
`verify_stock_report.py --full-template` checks each raw verdict,
candidate-level summary and source/template identity before rendering a
self-contained, script-disabled Japanese HTML report.

**Evidence boundary:** this assembles the complete set of source fragments
listed in the official template at one pinned revision. It is **not a
cryptographic verification of the published built `easyprivacy.txt`
artifact**, since official build/transformation settings and the distribution
snapshot can differ. It also does not verify all lists active in any
particular Firefox, uBO Lite, Ghostery, AdGuard or Brave installation.
Real websites, authentication, checkout and video playback remain NOT_RUN.
The five-component benchmark stays available as a separate reproducible
comparison. Underlying upstream source is not committed or redistributed,
and no rule is auto-adopted. Publication remains NO_GO.
