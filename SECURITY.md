 # Security

Report suspected security issues privately when exploit details or sensitive information are involved.

The watcher uses bounded network actions and does not accept browser passwords, cookies, localStorage, or Authorization headers as runtime credentials.

Security-sensitive areas include URL/DNS validation, manifest validation, subprocess isolation, sanitized logs, Browser Bridge authentication, and persisted recovery state.

Automated tests do not prove complete resistance against all future network or provider changes.
