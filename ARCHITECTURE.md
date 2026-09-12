# WorkLane architecture

WorkLane is an independent local-first work-order engine. One explicitly selected project resolves to one SQLite store. BluePrint presents the work; WorkForce may execute it. Neither is required for the store, API, CLI, or MCP to function.

## Boundaries and layers

- `worklane/products.py` resolves project identities, compatible prefixes, and runtime locations. Callers must not select a store by a guessed default when operating across projects.
- `worklane/trackers/` owns persistent tasks, comments, relations, and transitions. SQLite state lives under the configured runtime directory outside installed package files.
- `worklane/api/tasks/` provides scoped HTTP operations; `worklane/mcp/handlers/` provides equivalent signed tool operations; `worklane/cli/` provides local commands. These adapters use the owning tracker and process guards.
- `worklane/board/` and `worklane/surfaces/` retain compatibility presentation components. BP is the optional operational interface. A UI redirect is not an engine dependency.
- Routing, lifecycle, evidence, and child-coverage checks remain in engine modules, not in BP. Host-only evidence is constrained by the interactive author and host-work labels; source changes still cite actual commits.

`PROTOCOL.md` is the process source of truth; `INSTALL.md` is the setup reference. Historical identifier compatibility does not revive the former Python package. Public-safe canonical source is maintained directly in protocolcity/WorkLane; runtime and private operational history remain outside it.

## Readiness policy

HTTP and MCP use WorkQueue for dispatch eligibility: backlog, no active gate, no umbrella label, and every explicit declared or structured `blocks` dependency resolved. Done and canceled prerequisites resolve the dependency; missing references remain blocking. Context-only prose does not create a dependency. SQLite also checks both dependency forms when a direct status transition attempts a claim. Ready reads never materialize or rewrite relation data. Assignment filters narrow this eligible set; a selected seat does not itself dispatch or claim work.
