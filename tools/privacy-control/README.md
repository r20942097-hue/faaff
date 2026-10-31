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

## Isolated Firefox / full uBlock Origin browser verification (experimental)

The CI-only `firefox-full-ubo-real-loopback` job uses `ubuntu-24.04`
explicitly to avoid the ongoing GitHub `ubuntu-latest` migration to
Ubuntu 26. It uses a **real Firefox and GeckoDriver** plus Selenium's
documented Firefox add-on API. Official signed uBO `1.75.0` XPI is downloaded
and SHA-256/size verified (GitHub release asset digest
`5b74415860456370644bd80f16125e865b0e6c356bb5dfcfb84069967eaa5287`).

The disposable runner resolves `probe.scorecardresearch.com`,
`pages.example.com`, `assets.example.com` and `unrelated.example.org`
to RFC5737 documentation IP `192.0.2.10` assigned to the runner's `lo`
interface, serves a local synthetic image,
disables Firefox's independent tracking-protection feature inside the
temporary profile, and measures the actual HTTP requests (not HTML-only
visibility). Test transitions: baseline HTTP received → addon installed,
target block observed while same-site/same-origin controls remain reachable →
addon uninstalled, target HTTP restored. An independent third-party control
is recorded separately. If that control is blocked, target-specificity
remains NOT_ESTABLISHED and the outcome is PARTIAL, never falsely PASS. The independent
`verify_firefox_report.py` rejects missing lifecycle observations or
misleading claims. No user browser profile, production network rule,
Windows registry, DNS configuration or real website is touched.

**Limits:** this can demonstrate behavior of an installed uBO's default
rules against a locally mapped tracking hostname. It is not a test that the
38 candidate rules are enabled, nor evidence that a user's browser lists,
login, checkout, media or signed requests are safe. Any failure means the
browser gate is **FAIL/NOT_VERIFIED**, not permission to weaken the probe.
Release stays NO_GO.

### Measured installed-Firefox gate: BLOCKED, not a pass (2026-10-31)

Five independent GitHub Actions attempts were run with the official signed
uBO 1.75.0 and synthetic HTTP against isolated test hostnames. A target
tracking-host request stopped after installing the extension. **However,
ordinary cross-host images also stopped**, including a benign same-site
hostname even when an RFC5737 TEST-NET IP was assigned to CI's loopback
device. A same-origin request continued to reach the local server. Because
the benign cross-host negative control fails, these observations **cannot
prove target-specific blocker efficacy**. Post-uninstall restoration was
not reached in a valid run. Root cause remains unknown.

For transparency, immutable run IDs and precise PASS/FAIL/NOT_RUN results
are recorded in `verification/firefox-isolation-diagnostic.json`.
The experimental installed-Firefox job is now limited to explicit manual
`workflow_dispatch` research. The normal pull-request CI independently
asserts the browser status is `BLOCKED`, preventing accidental elevation
to `PASS`; 38 candidate rules remain unapproved. This is not a workaround
for a real Firefox profile and **no user PC or installed extension was
modified**. Future work must establish a valid benign cross-host control
and full removal/rollback before this gate can be marked PASS.

## Phase 2d — nonforwarding Firefox HTTP-proxy lab

Earlier five trials mapped external-looking hostnames to 127.0.0.1 or a
TEST-NET IP on CI loopback. Benign cross-host requests did not arrive,
making attribution to a tracker-specific rule **BLOCKED**. uBlock Origin
has documented LAN-protection filters, a plausible confounder, although
no matched-filter logger entry was captured, so the root cause is NOT proven.

`firefox_proxy_probe.py` is a separate experiment: in an ephemeral
Firefox profile, configure an explicit localhost HTTP proxy. The browser
URLs retain the public-style hostname instead of resolving that hostname
to a local destination. This local proxy answers only four hard-coded
synthetic HTTP hostnames and a fixed image/page fixture; it rejects all
HTTPS CONNECT, POST, unknown hostname, route or port requests with 403,
**never forwards to the public internet**, and never changes system DNS.
The official signed uBO XPI is still hash-pinned and temporary.

Observe all four hosts with no extension, then with the real extension,
then **after uninstall even if controls fail**. The report is written
even if the test result is BLOCKED, with separate reason, actual result
booleans and rollback evidence. An independent verifier rejects any
unproven PASS, lost benign control, missing rollback, or live-site claim.
No raw private URL, credentials or user data are collected.

The existing failing hosts-file tests and `BLOCKED` history remain
preserved; their results must not be silently reclassified. Even if this
restricted proxy trial passes, that only demonstrates isolated HTTP
behavior, **not** a real browser's enabled subscriptions, user settings,
candidate v2 adoption, video/auth compatibility or real website efficacy.

## Phase 2e — actual Firefox signed uBO control and rollback (PASS, isolated only)

[UPC CI run 41097729808](https://github.com/r20942097-hue/faaff/actions/runs/41097729808)
proved a narrower, reproducible point with an **actual Firefox extension**.
An explicit, deny-by-default HTTP proxy bound to the ephemeral runner's
`127.0.0.1` preserves the original URL hostnames inside Firefox while
the proxy itself resolves **nothing** and does not forward traffic. Only
four named test hosts, the synthetic index and static image are served;
HTTPS CONNECT, unapproved hosts/ports/methods are refused.

With **official signed uBO 1.75.0** installed, a synthetic tracking-host
image was blocked; benign same-origin, same-site, and unrelated third-party
images were received by the isolated local server. Upon **actual uninstallation**
all four test image requests were received again. The independent report gate
rejected unproven PASS outcomes, including broken benign controls or
incomplete rollback. The proxy rejected 57 off-fixture requests. Signed
XPI SHA-256 was checked against official release metadata.

These observations are **HTTP-only and synthetic**. They do not imply that
the 38 proposed candidate rules were installed in Firefox, that real user
stock lists/settings are covered, or that a real login, checkout, stream,
signed URL or production site is safe. The five earlier failed hosts-file
attempts remain `BLOCKED` and preserved; their exact cause has not been
proven, although the local-IP mapping was an apparent confounder.

The successful isolated-proxy run is indexed in
`verification/firefox-proxy-validation.json` with exact CI run, commit,
official XPI hash and measured controls. Runtime JSON stays in the CI
runner rather than Git. **No change to active subscriptions or system
settings; release remains NO_GO.**

## Phase 2f — synthetic signed URL, cookie and byte-range regressions

The installed-Firefox/official-uBO nonforwarding proxy lab now adds three
**actual browser HTTP flow controls in each lifecycle stage**: before the
extension, while enabled, and after uninstall. A signed query includes
`utm_source=synthetic-campaign` and an in-memory HMAC-SHA256 signature
binding `token|utm_source`. Removing or altering the query parameter
makes the synthetic endpoint reject the request. A login-check route
requires an HttpOnly/SameSite cookie, and a binary endpoint returns a
206 `Content-Range: bytes 0-31/256` response only to a matching HTTP
Range request. All requests use ephemeral synthetic data, local proxy
responses and a transient browser profile; nothing is forwarded externally.

`verify_firefox_proxy.py` now requires all nine safety result booleans
(three checks across three stages) in addition to specific blocking,
the three benign network controls and full uninstall restoration.
The offline unit tests verify HMAC tamper failure, cookie enforcement,
Range 206, and forged/omitted safety-evidence rejection. A failure is
retained as BLOCKED with a reason; **never count it as safe to publish**.

This tests a baseline signed-query/cookie/byte-range scenario against the
currently installed official uBO stock configuration only. The 38
`v2/tracking.txt` candidate rules are NOT loaded, no real MP4 is played,
and no real login, signed CDN URL or website is exercised. Passing
this synthetic gate does **not** authorize `removeparam` changes or
publication: the earlier synthetic HMAC hazard remains a separate NO_GO
release finding.

## Phase 2g — actual ephemeral Firefox managed candidate rules

The new `firefox-managed-v2-candidates` CI job exercises the **38 actual
pinned optional tracking rules** inside real Firefox/uBlock Origin. Firefox's
documented per-user managed-storage manifest mechanism and uBO's supported
`toOverwrite.filters` configuration are used in a temporary hosted CI
runner, not on the user's machine. The manifest and XPI never enter Git or
a persistent user browser. No global Firefox enterprise policy is changed.

Three isolated real Firefox sessions are required: stock uBO, stock uBO with
38 v2 filters plus a synthetic `example.org` sentinel managed rule, then stock
uBO after removing the managed manifest. The test server is the same
deny-by-default, nonforwarding HTTP proxy, extended for exact pinned hosts
and a synthetic `/batch` image page. It compares all 38 host requests in
one bounded fixture without contacting any live third-party domain.
Normal first-party, same-site and unrelated third-party controls must
remain reachable in every stage; the sentinel must be reachable, then
blocked, then reachable again, and all candidate requests must block in
the middle stage. The restored stock observations must exactly match the
first stock observations. The independently validated report distinguishes
hostnames already blocked by stock uBO from *new synthetic blocks* caused
by activating the candidate rules.

A blocked/ignored managed policy, a browser fixture issue, or unstable
baseline results are a **FAIL/NOT_VERIFIED**, never silently marked as
active protection. This test does not validate any real site's traffic,
actual user-enabled filter subscriptions or behavior on Chromium/uBO Lite,
and cannot promote a public list. Signed-URL/authorization/media
real-world compatibility remains independent. **Release NO_GO**.

Upstream primary references:
- Mozilla native managed storage documentation:
  https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Native_manifests
- Official uBO managed configuration:
  https://github.com/gorhill/uBlock/wiki/Deploying-uBlock-Origin:-configuration

### Candidate-installed safety controls

The new candidate policy experiment also runs `synthetic_safety()`
during **all three separate Firefox configurations**, so each stage
checks HMAC-bound `utm_source` query integrity, a synthetic HttpOnly cookie
login and a 206 HTTP byte-range response. Its independent evidence validator
requires all nine booleans to be explicitly `true`; a synthetic failure
blocks the experiment. These remain local fixtures, not real auth or
streaming site validation. No `removeparam` rewrite is adopted.

### Fail-closed diagnostics for interrupted candidate activation

The full Firefox managed-rules experiment always deletes its ephemeral
`managed-storage/uBlock0@raymondhill.net.json` policy before leaving the CI
runner. If installation, policy loading, a normal traffic check, safe
signed-query/cookie/Range behavior, or baseline restoration fails,
`firefox_candidate_probe.py` writes a temporary **BLOCKED** evidence JSON
with the failed stage, machine-readable reason code, partial host receipts,
policy cleanup state and immutable source references. These diagnostics
do not claim verified candidate activation; the independent verifier prints
the stage and returns a failing exit status. The regular release remains
NO_GO and the incomplete result must never be counted as a pass.

The existing successful isolated signed URL/auth/Range checks are independent
of this newer candidate-activation experiment, whose success remains
unconfirmed until its own GitHub Actions job finishes.

## Phase 2h — real installed Firefox stock coverage and repeatability

[UPC CI 41102700720](https://github.com/r20942097-hue/faaff/actions/runs/41102700720)
is the first **verified PASS** for three independent ephemeral Firefox
sessions with the official signed uBO extension: stock → managed
38-candidate rules → managed policy removed and stock restored. One
synthetic third-party **image-host** request per candidate was measured.
All 38 were blocked in the candidate-activated run, **37 of those 38
were already blocked by the tested installed-uBO stock configuration**,
and just **one was additional relative to stock**. The activation
sentinel and benign first-party/same-site/unrelated cross-site requests
passed, signed-query/cookie/Range fixtures survived all three sessions,
and baseline outcomes returned after removing the managed policy.

The original run's single additional hostname was **not logged by name**;
do not invent its identity. Aggregate provenance, CI run/job/commit IDs,
scoping and NO_GO are now recorded in
`verification/firefox-managed-candidates-validation.json`.

From now on each real Firefox stage performs **two independently tokenized
batch fetches** and refuses to claim a consistent browser decision when
their per-host results disagree. Both round receipts are checked against
the recorded stage result by an independent validator. CI summary exposes
the exact additional hostname(s) and records stock-covered vs incremental
outcomes. No outcome is promoted automatically.

**Meaning of 1/38:** synthetic third-party image request blocking in
one installed pinned Firefox/uBO test configuration. It is neither the
effect of all 38 rules independently (the other 37 were masked by stock
rules), nor the number of prevented tracking events, nor a claim that
actual users have those subscriptions enabled. It cannot be numerically
compared to the earlier "23 extra synthetic request cases" from the
template-source-only two-engine study because fixture type, rule source
and effective stock lists differ.

Next checks: independent rerun of the exact live Firefox experiment,
other request methods/types, effective stock subscriptions in additional
browsers, and actual site compatibility. None authorizes publication:
**Draft / PUBLICATION_HOLD / NO_GO**.

## Phase 2i — installed Firefox resource-type comparisons

The browser experiment now runs **two independently tokenized batches for
each of two resource types** in each of three real Firefox sessions:
third-party `<img>` and third-party `<script>`. The JavaScript fixture
is an inert no-op served by the exact same nonforwarding localhost proxy;
no real tracker script is downloaded or run. The fixture includes all
38 pinned candidate hostnames, the managed-storage activation sentinel,
and first-party, same-site and unrelated third-party controls.

Image and script results are separately preserved in the runtime JSON.
The independent verifier checks both types' full host receipts, two
matching independent rounds, sentinel activation, benign controls,
stock-to-restored equality, and evidence-derived per-host incremental
classification. CI summarizes the additional and already-stock-covered
hostnames for **each type**; missing or conflicting evidence is FAIL.
The signed URL, cookie auth and HTTP 206 Range controls remain required in
all three sessions.

The confirmed preceding image fixture result was **1 additionally
blocked hostname: `rudderstack.com`**, with 37 already blocked by the
installed stock-uBO configuration, from CI run 41147465530. This is
one synthetic image URL per host, not proof of actual trackers or new
blocking value for all 38 rules. **Script outcomes remain unverified
until the revised CI run succeeds.**

Publication remains NO_GO. No real websites, production streaming or
signed-media CDN traffic are contacted, and no filter URLs or user's
Firefox settings are changed.

## Phase 2j — isolated Chromium MV3 DNR experiment (not uBO Lite)

The official Chromium `declarativeNetRequest` API provides a useful
additional **real-browser** compatibility gate for the 38 optional
domain-anchored `$third-party` rules. Chrome documents
`urlFilter` domain anchors and `domainType:"thirdParty"`; Playwright
documents testing MV3 extensions with its **bundled Chromium** in
`launch_persistent_context` (unpacked sideloading is not a supported
equivalent in production Chrome or Edge).

A new **CI-only MV3 test extension** is generated in a temporary directory,
never committed, signed, published, or installed in any user profile.
It contains exactly 38 SHA-verified domain block rules plus one synthetic
activation sentinel, limited to synthetic `image` and `script`
requests. Every rule uses `condition.urlFilter="||domain^"` and
`condition.domainType="thirdParty"`. A local-only deny-by-default
HTTP proxy from the existing Firefox lab serves the known hostnames;
unknown hosts, HTTPS tunnels and outbound forwarding are rejected.

Three isolated bundled Chromium profiles (no extension → test MV3 DNR
extension → no extension) each run two independently tokenized image
and script batches. Every target and activation sentinel must be reachable
without the extension, blocked with the test rules, and reachable again
after the extension is absent; all benign first-party/same-site/unrelated
third-party controls must always be reachable. The independent report
validator checks every response bit, full rollback and provenance.

**Not equivalent to uBO Lite**: this uses a deliberately minimal,
synthetic, hand-generated MV3 extension and **does not load the real uBO
Lite packaged stock rules or managed settings**. It cannot measure
incremental coverage against uBO Lite, deduce user defaults, test HTTPS
signed media, or demonstrate live-site compatibility. DNR's third-party
semantics and the full uBO engine's filters are not fully interchangeable.
Do not promote or publish rule candidates based on this experiment.

Sources: 
- https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest/
- https://playwright.dev/python/docs/chrome-extensions
- https://github.com/uBlockOrigin/uBOL-home/wiki/Frequently-asked-questions-(FAQ)

Release **NO_GO**. 

### Chromium baseline diagnostic correction (Phase 2j)

The first real Chromium run showed no-extension HTTP image/script requests
to four known upstream hostnames did not reach the isolated proxy:
`google-analytics.com`, `mixpanel.com`, `mouseflow.com`, and
`bat.bing.com`. The same four were absent after returning to a new
no-extension profile, while all 38 candidate host requests and the
synthetic sentinel were absent with the MV3 DNR test rules installed.
The precise cause of those baseline misses is **unknown** (possible
browser upgrade/security/network behavior); they must **not** be
claimed as newly blocked by DNR.

The corrected test requires two identical independent rounds of image
and inert script requests in each of three profiles, stable benign
controls, an active sentinel and exact **observed baseline ↔ restored
outcome equality**. Its evidence report explicitly distinguishes
requests never received without the DNR extension from newly blocked
requests attributable to switching on the test rules. Any change in
the unknown baseline set causes a fail-closed mismatch if rollback
does not reproduce it.

The initial Chromium CI was **FAIL** and remains recorded in Actions;
this change does not retroactively change that result. Chromium
compatibility is NOT_VERIFIED until the revised job passes. This
is still an independent DNR test extension, not official uBO Lite.

### Explicit third-party vs first-party compatibility gate

In addition to image/script requests from `pages.example.com` to all 38
candidate hosts, the isolated Chromium DNR experiment now uses the
`rudderstack.com` candidate as a first-party initiator and fetches an
image and an inert script from **the same domain**. Those requests must
remain reachable **with or without** the generated third-party DNR rules;
two independent requests per type per stage are independently verified.
If the DNR translation blocks a first-party request, the job FAILs
regardless of the observed third-party blocking result. No live site is
contacted; these are synthetic URLs served through the local proxy.
