# WorkLane

[![Tests](https://github.com/protocolcity/WorkLane/actions/workflows/tests.yml/badge.svg)](https://github.com/protocolcity/WorkLane/actions/workflows/tests.yml)

A local-first work-order engine for people and AI agents. Keep objectives,
assignments, gates, claims and verification in a shared record that outlives
any one chat or provider session.

WorkLane works independently through HTTP, MCP or the `wl` CLI. SQLite stores
are separated by project. [BluePrint](https://github.com/protocolcity/BluePrint)
is an optional operations interface; [WorkForce](https://github.com/protocolcity/WorkForce)
is an optional execution engine. WorkLane does not run AI models.

The 0.1.x series is pre-release. Supported behavior and limits are documented
in [PROTOCOL.md](PROTOCOL.md); installation and configuration are in
[INSTALL.md](INSTALL.md).

## Install

Python 3.9 or later:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install protocolcity-worklane
export WORKLANE_RUNTIME_DIR="$HOME/.worklane"
worklane
```

The default server address is `http://127.0.0.1:8799`. Set `TASK_HOST` and
`TASK_PORT` to change it. Keep the service on a trusted interface; signed
actor names are attribution, not authentication.

## First project and work order

In a separate terminal, bootstrap a project before filing work:

```bash
curl -s -X POST http://127.0.0.1:8799/api/admin/products \
  -H 'Content-Type: application/json' \
  -d '{"slug":"example","display":"Example","prefix":"ex"}'

curl -s -X POST http://127.0.0.1:8799/api/admin/tasks \
  -H 'Content-Type: application/json' \
  -d '{"surface":"example","author":"you","title":"Verify setup","description":"Create one work record and confirm its project and author.","labels":["worker:you","you:host"]}'

wl list --project example --status backlog
```

For an installation attached to an existing workspace, register its project
folder and instructions first; see [project setup](INSTALL.md#project-setup).
Always select the project explicitly. Do not create stores by copying database
files into the runtime directory.

## Connect an agent

Configure its MCP client to run:

```bash
python -m worklane.mcp --author example-agent
```

Set `WORKLANE_RUNTIME_DIR` to the same absolute runtime path used by the server.
Use a registered executor identity and its allowed project. Interactive sessions
use `you`. Claude, Grok, Cursor, Codex and other MCP clients can use the same
protocol; support in a client does not establish its authentication or quota.

Use `wl_ready`, `wl_claim`, `wl_comment`, `wl_park` and `wl_close` with explicit
`project=`. A review-stage agent can set `WORKLANE_COMMENT_TRANSITIONS=0` so
comments retain evidence without changing lifecycle status. Expose only the
operations appropriate to its role.

## Daily workflow

1. Capture an objective, scope and acceptance criteria in the owning project.
2. Assign one registered `worker:<id>`. Assignment is distinct from dispatch.
3. Claim eligible work before editing; preserve other writers' ownership.
4. Record decisions, artifacts, tests and a next action when pausing.
5. Close with Completed, Verification, Links and Follow-ups after acceptance.

Gates distinguish human action, timers, deferred work and structural tracking.
Unavailable or quiet execution is not permission to steal a claim. WorkLane
records durable work context; it does not transfer proprietary conversation
state between providers. Safe execution recovery also requires the runner.
See [continuation](CONTINUITY.md) for checkpoint and guarded handoff contracts.

## Development

```bash
git clone https://github.com/protocolcity/WorkLane.git
cd WorkLane
python3 -m venv .venv
source .venv/bin/activate
pip install -e . pytest httpx
python -m pytest tests -q
```

Tests use disposable stores. CI runs the complete suite, including the included
maintenance scripts. See [ARCHITECTURE.md](ARCHITECTURE.md), [AGENTS.md](AGENTS.md)
and [HOST_PROFILE_TEMPLATE.md](HOST_PROFILE_TEMPLATE.md). Preserve runtime state
outside package files and use SQLite's backup facilities for live databases.

## License

Apache-2.0 — see [LICENSE](LICENSE).
