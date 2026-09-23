# Changelog

Release notes describe product behavior. Deployment receipts, private incident
reports and host rosters belong to the adopting workspace.

## Unreleased

- Reconcile the public protocol, setup guide and host template around explicit
  project scope, registered workers and evidence-based completion.
- Run the complete test suite in CI and make the backup freshness check portable
  across GNU and BSD hosts.

## 0.1.7

- Improve attention states, service health handling, work-order vocabulary,
  closeout evidence and routing validation.

## 0.1.6

- Support optional route-event wake notifications to a configured WorkForce
  service. Notification success does not establish execution.
- Require one valid worker assignment when project workers are registered;
  distinguish intentionally classified personal/host work from unrouted work.
- Improve cross-store routing checks, umbrella readiness, child-coverage checks,
  explicit store addressing, event identity and SQLite read resilience.
- Keep the public commands `worklane`, `worklane-mcp` and `wl`.

## 0.1.5

- Add gate filters and improve deferred-work handling.

## 0.1.4

- Add a dedicated deferred gate and routing-gap visibility.

## 0.1.3

- Include the desk stylesheet and JavaScript assets in installed distributions.

## 0.1.0

- Initial work-order protocol and local SQLite-backed implementation.
