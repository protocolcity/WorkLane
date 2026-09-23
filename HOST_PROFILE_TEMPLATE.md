# Host profile template

Copy and complete this in the adopting workspace. Keep real paths, account
configuration and private operational history out of public product source.
The [protocol](PROTOCOL.md) supplies lifecycle and evidence rules; this profile
supplies the installation's authority and execution details.

| Field | Fill in |
|---|---|
| Project | Registered slug, store identity and project instructions |
| Executor | Dedicated worker ID; use `you` for an interactive session |
| Working copy | Allowed repository/path, branch and isolation procedure |
| Scope | Allowed paths and work kinds; explicit exclusions |
| Connection | MCP/CLI/API endpoint and absolute runtime path |
| Queue | Explicit project and `worker:<id>` readiness filter |
| Provider | Supported model/tools and account quota pool; no secrets here |
| Host | Local or explicitly configured remote execution environment |
| Trigger | Manual or verified schedule; configuration is not run evidence |
| Budget | Time/usage limits, retry cap and stop conditions |
| Verification | Exact behavior checks and required integration evidence |
| Publication | Applicable review, branch, release and deployment authority |
| Recovery | Checkpoint location, stopped-writer proof and ownership-transfer procedure |

Before dispatch, verify the selected store and identity, authentication and
scope. Keep real credential values in the host's secret mechanism. A provider
change must preserve the same authority and work record. Test the setup with
disposable data and do not automatically retry authentication/permission refusal.

## Agent instruction snippet

```markdown
This project tracks work in WorkLane. Read the project instructions and its
host profile. Pass project=<registered-slug> on every WorkLane call and sign
with the configured executor identity. Claim eligible work before editing.
Use the owning API/MCP/CLI, never direct SQLite mutation. Record decisions,
artifacts, verification and the next action on the same order. Park for review
when integration remains; close only with verified acceptance and the required
Completed, Verification, Links and Follow-ups sections. Empty queues stop.
```
