# MCP Inspector v2: isolated CLI verification lane

**Status: proposal / no production install / no remote MCP service / no credentials.**

## Why this is separate

The engineering hub lacks live product extension source and doesn't have a configured public/private MCP target that may safely be probed in CI. Before connecting a real MCP server, this PR creates a deterministic local test verifying that the official Inspector v2 CLI can initialize an MCP stdio connection, list tools with portable schemas and call a safe echo tool.

**Upstream:** https://github.com/modelcontextprotocol/inspector and https://www.npmjs.com/package/@modelcontextprotocol/inspector

**Version selected:** `@modelcontextprotocol/inspector@2.13.0` (public version checked 2026-10-30); requires Node.js `>=22.19.0`. GitHub-hosted CI installs a specific Node 22.19.0, with the official setup-node action pinned to `49933ea5288caeca8642d1e84afbd3f7d6820020`.

## Minimal offline server fixture

The JavaScript file `mock-stdio-server.mjs` implements a small synthetic JSON-RPC 2.0 stdio MCP server with:
- `initialize` / `ping` responses.
- `tools/list` exposing the harmless `echo_text` tool with a strict JSON Schema.
- `tools/call` returning exactly its input text without touching files, networks, user accounts, credentials or the actual product code.

The fixture has no third-party runtime dependencies. It is **not** a production MCP server and not a test of Agent-Reach or SkillSpector's MCP integration.

## Isolated CI

`.github/workflows/mcp-inspector-smoke.yml`:
1. Checks out the PR code with no persisted credentials.
2. Pins Node.js 22.19.0.
3. Runs Node syntax validation for the fixture.
4. Installs only `@modelcontextprotocol/inspector@2.13.0` in GitHub's temporary directory with npm lifecycle scripts disabled.
5. Runs `mcp-inspector --cli --method tools/list --strict --format json` and verifies the expected tool.
6. Calls `echo_text` once and verifies its deterministic response.

The CLI does **not** start the Inspector's web server or open a listening port. Never place real API keys, browser cookies, personally identifying records or authentication state into the workflow.

**Security limits:** npm transitive dependencies are not locked; package install still has network access; `--ignore-scripts` prevents install lifecycle scripts but does not sandbox code invoked when CLI tests run. The CI runner is ephemeral and has `contents: read`. Lockfiles and artifact digest verification remain promotion gates before use with privileged MCP targets.

## Next real-product prerequisites

- Identify and authenticate the exact server's source and tools; review its full requested permissions.
- Run SkillSpector/static scans on any third-party MCP skill/code before allowing execution.
- Enforce an explicit allowlist of only known local target servers. Evaluate inspector secret storage: without a keychain, it can use an unencrypted local secrets file; use an in-memory store or an isolated test home for any authentication tests.
- Keep remote URL connections, browser session imports, OAuth, web Inspector UI, cross-origin and network listening **disabled** until intentionally scoped and separately approved.
- Add product-specific contract tests only when the authoritative source is actually present.

## Evidence states

- Upstream version, Node requirements and CLI syntax: official source documentation checked.
- GitHub branch source, CI registration and execution: record links when observed.
- Real MCP server, remote login, Windows local install, production compatibility, browser extension runtime: **NOT_RUN**.
