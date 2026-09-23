# Install and operate WorkLane

WorkLane requires Python 3.9 or later. It can run independently; BluePrint,
WorkForce and a source checkout are optional.

## Package installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install protocolcity-worklane
export WORKLANE_RUNTIME_DIR="$HOME/.worklane"
worklane
```

`worklane` starts the HTTP service, `worklane-mcp` starts a stdio MCP server,
and `wl` is the HTTP CLI. These are different entrypoints, not aliases for
one command. The service defaults to `127.0.0.1:8799`; `TASK_HOST` and
`TASK_PORT` override it. Keep the endpoint on a trusted interface. Actor
names provide attribution, not authentication.

Verify the configured endpoint:

```bash
curl -s http://127.0.0.1:8799/api/admin/products
wl --help
```

## Runtime location

An installed package defaults to `~/.worklane/`. `WORKLANE_RUNTIME_DIR` selects
an explicit runtime root shared by the service and MCP clients. The legacy
`TICKETING_PROTOCOL_RUNTIME_DIR` variable remains compatible. Stores live in
`data/` and configuration in `config/` beneath that root.

Source checkouts default to `worklane/local/` in the main checkout. Linked git
worktrees follow that main runtime unless `WORKLANE_RUNTIME_LOCAL=1` is set.
For tests and isolated trials, use an absolute disposable runtime directory.
Never install two editable copies of the same Python package in one environment.

## Project setup

Bootstrap a project before filing work:

```bash
curl -s -X POST http://127.0.0.1:8799/api/admin/products \
  -H 'Content-Type: application/json' \
  -d '{"slug":"example","display":"Example","prefix":"ex"}'
```

The slug starts with a lowercase letter, contains lowercase letters, digits,
underscores or hyphens, and has at most 40 characters. A custom prefix has
2–8 lowercase alphanumeric characters and must be unique. The products API
creates the store and records its metadata. Unknown stores reject work writes.

When the service is configured for a workspace, register the actual project
folder and its AGENTS.md under that workspace before creating its store.
A `.protocolcity/desk-join.json` points the project at the existing store.
Do not register reference/archive clones as projects or bypass registration
by copying a database. Backups and retired stores stay outside `data/`.

File scoped work:

```bash
curl -s -X POST http://127.0.0.1:8799/api/admin/tasks \
  -H 'Content-Type: application/json' \
  -d '{"surface":"example","author":"you","title":"Verify setup","description":"Confirm the project and author of this work record.","labels":["worker:you","you:host"]}'
wl list --project example --status backlog
```

Every write names its actor. A project with registered workers requires one
valid `worker:<id>`; host work uses `worker:you` with `you:host`. See
[PROTOCOL.md](PROTOCOL.md) for readiness, ownership and evidence.

## Agent connection

Configure the MCP client with the Python executable from the installation:

```json
{
  "mcpServers": {
    "worklane": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "worklane.mcp", "--author", "example-agent"],
      "env": {
        "WORKLANE_RUNTIME_DIR": "/absolute/path/to/runtime",
        "WORKLANE_COMMENT_TRANSITIONS": "0"
      }
    }
  }
}
```

Substitute the registered executor identity and real absolute paths. For an
interactive human session, use author `you`. Pass explicit `project=` on tools.
No provider-specific work-order store is needed.

`WORKLANE_COMMENT_TRANSITIONS=0` keeps MCP comments as evidence without
performing lifecycle transitions. Explicit lifecycle tools retain their guards.
This setting is useful for review-stage workers but does not implement tool
authorization. Configure exposed tools to match the worker's authority. The
default retains legacy comment transitions; restart MCP after changing its env.

For workspace-scoped assignment checks, `WL_WORKFORCE_LOCAL_ONLY=1` together
with `WL_WORKFORCE_ROSTER=/absolute/path/to/roster.json` selects only that
roster. Missing/unreadable selected rosters do not fall back to another
workspace. Without this setting, service-first roster lookup remains supported.

CLI clients use `WL_BASE_URL` for the endpoint and `WL_AGENT_ID` for the actor.
Consult `wl --help` and each subcommand's help for the installed version.
Use [HOST_PROFILE_TEMPLATE.md](HOST_PROFILE_TEMPLATE.md) for scope, execution,
verification and recovery instructions.

## Source development

```bash
git clone https://github.com/protocolcity/WorkLane.git
cd WorkLane
python3 -m venv .venv
source .venv/bin/activate
pip install -e . pytest httpx
python -m pytest tests -q
```

CI runs the full suite on supported test interpreters. Tests use disposable
stores; do not run maintenance commands against production to validate a patch.
Optional macOS startup: inspect `scripts/install-macos-service.sh --help` and
its dry-run before installing the service.

## Updates and recovery

Keep runtime data separate from installed package files. Before an upgrade,
record the installed version and runtime path and create a consistent backup.
Use SQLite's backup API for a live database, or stop all writers before copying
its database and sidecar files. Test restore in a separate runtime. Retain the
previous environment/package until the updated service and project identities
are verified. Do not assume an older binary supports a migrated schema.

The repository includes `scripts/backfill_relations.py`: its default is a
read-only report, and `--apply` is a separate, authorized migration. The backup
freshness monitor is optional; configure its directory, endpoint and project
explicitly and inspect `--dry-run` before enabling alert writes. Neither script
is needed for ordinary installation or work-order use.

## Troubleshooting

- **Unknown project:** inspect `/api/admin/products` at the configured endpoint;
  verify registration and runtime selection before creating another store.
- **Different data in MCP and HTTP:** compare their absolute runtime paths and
  installed package locations, then restart the misconfigured client.
- **No ready work:** inspect gates, dependencies, status and worker assignment;
  a nonempty backlog can have no eligible work.
- **Rejected closeout:** inspect the error and supply real verification/revision
  evidence. Do not invent a SHA or bypass the owning engine.
- **Interrupted executor:** preserve edits and checkpoint evidence; verify the
  previous writer stopped before an authorized ownership transfer.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [PROTOCOL.md](PROTOCOL.md).
