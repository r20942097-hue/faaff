# Project Index

Updated: 2026-10-05

This file is a management index only. It does not replace product-specific release evidence or automatically promote any product.

| Project | Latest observed | Product verified | Integration verified | Stable | State | Decision |
|---|---|---|---|---|---|---|
| YouTube Home Optimizer | 2.6.0-dev70 | 2.6.0-dev70 | — | — | DEV | NO_GO |
| WP10 2025 Companion | 0.38.0 | 0.38.0 | — | — | DEV | NO_GO for real-game All Horses |
| Universal Live Watcher | 6.49.12 | 6.49.12 | 6.49.12 | 6.38.0 | CANDIDATE | HOLD |
| AI Orchestrator | 1.51 | 1.51 | 1.51 | — | CANDIDATE | HOLD |
| Windows Control | 0.1.8 | 0.1.8 | 0.1.8 | — | CANDIDATE | NO_GO |
| Browser Control | 0.4.2 (Suite-integrated) | 0.3.0 | 0.4.2 | — | DEV | NO_GO |
| Universal Control Suite Integration | 0.50.0 | 0.50.0 | 0.50.0 | — | DEV | NO_GO |
| Browser Filter Lists | `browser_filter_lists` + distribution mirror | stable lists | v2 candidate | current stable lists | CANDIDATE | CONSOLIDATE |

## Evidence levels

- **Latest observed**: a version/artifact was found.
- **Product verified**: matching product-level evidence exists for that exact version/artifact.
- **Integration verified**: evidence exists only through a Suite/integration chain.
- **Stable**: required real-environment acceptance is complete enough for normal use.

Artifact presence, a filename, or a checksum alone never promotes a version.

## Current blockers

- YouTube Home Optimizer: real browser/YouTube, CPU/GPU/FPS, A/V sync and long-duration acceptance.
- WP10 2025 Companion: live Windows/WP10 validation, restart-validated horse-table mapping, confirmed game builds and real-game performance.
- Watcher: real Windows, authenticated RPLAY, monitor/notify/record continuity, Firefox/Edge, soak and rollback.
- Windows Control: real Windows API/settings/multi-monitor/restart/rollback.
- Browser Control: standalone 0.4.2 evidence plus real logged-in multi-browser YouTube acceptance.
- Universal Control Suite: Windows Job/process races, real browser/YouTube and long-duration soak.

## Retention rule

Keep only `CURRENT`, `STABLE` where applicable, `PREVIOUS_KNOWN_GOOD`, current documentation, current verification evidence and checksums in the active area. Move older intermediate builds to archive after preserving unique failure/recovery evidence.
