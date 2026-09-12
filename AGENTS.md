# WorkLane product instructions

WorkLane is the standalone local-first work-order engine. Its Python package is `worklane`; public tools are `wl_*`. Historical task IDs and compatible client aliases remain resolvable without restoring an old package or a second data store.

Read [ARCHITECTURE.md](ARCHITECTURE.md) for product structure, [PROTOCOL.md](PROTOCOL.md) for lifecycle, ownership, routing and evidence requirements, [INSTALL.md](INSTALL.md) for setup, and [README.md](README.md) for the product overview. Host instructions belong in the workspace, not in this distributable product source.

## Boundaries

WorkLane owns work-order state and history. BluePrint is an optional interface. WorkForce is an optional execution integration. Independent business products do not embed WorkLane or require it at runtime. WorkLane must remain usable without BluePrint or a particular host repository.

Every write uses an explicit project and its resolved store. Runtime data is outside installed packages, selected by `WORKLANE_RUNTIME_DIR`; updates must preserve it. Compatibility aliases resolve to the same store and handlers. Never manufacture a commit reference or mark incomplete work done to satisfy a guard.

## Development

Canonical product repository: `protocolcity/WorkLane`. Keep source safe for distribution; credentials, host configurations, customer records, and private operational history do not belong here. No additional private-to-public export hop is required for changes made in this canonical source.

Use Python3.9-compatible syntax. Match existing package boundaries: API and handler packages separate routing, reads, writes, and shared helpers. Public imports remain compatible across refactors. Run `python -m pytest tests -q` with a disposable runtime directory; tests must not call a live desk or wake real agents. Stage explicit paths. Local verification is distinct from publication and deployment.
