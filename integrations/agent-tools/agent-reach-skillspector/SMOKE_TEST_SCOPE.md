# Agent tools Windows smoke-test contract

The permanent workflow [`.github/workflows/agent-tools-windows-smoke.yml`](../../../.github/workflows/agent-tools-windows-smoke.yml) exercises `-DryRun`, opt-in `-RunSetup`, target selection and invalid flag combinations on a GitHub-hosted Windows runner.

**Verified PASS:** [GitHub Actions run 41028614540](https://github.com/r20942097-hue/faaff/actions/runs/41028614540). The script is evaluated without an actual third-party package installation, login, external service call or mutation of the operator's Windows environment. Real install and MCP/browser connections remain `NOT_RUN`.

A temporary smoke job was previously inserted into `.github/workflows/ci.yml` and passed (run 41027720842); that duplicate job has been removed from the proposal branch to keep original CI unchanged. Keep the dedicated Windows workflow and review new results after future changes.
