# Retention policy v4

Protect references from latest_observed, product_verified, integration_verified, stable AND previous_known_good, including their unique test/recovery evidence. Unknown rollback versions remain null and must be resolved from actual product evidence.

The planner only emits KEEP references. No archive candidate is generated without a complete artifact inventory, exact hashes, reference graph and uniqueness checks. Filename age alone is insufficient. This run neither moved nor deleted prior product artifacts.

CI evidence is temporary. Save important release evidence independently of CI retention. Do not assume one retention period across all repositories, plans and artifact/log categories; inspect the applicable repository settings before planning expiry.
