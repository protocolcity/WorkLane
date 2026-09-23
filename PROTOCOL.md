# WorkLane protocol

WorkLane is a durable work-order engine for people and agents. It owns records,
project identity, gates, claims and evidence. An execution system may consume
its ready feed; WorkLane does not run AI providers. See [INSTALL.md](INSTALL.md)
for setup and [ARCHITECTURE.md](ARCHITECTURE.md) for component boundaries.

## 1) Core model

One explicitly selected project resolves to one SQLite store. Use composite
work-order IDs and explicit `project=` on MCP calls. `project=all` is for
cross-project reads, never mutations. The HTTP `surface` field and legacy
`product` alias identify that same project; they do not create another store.

| Status | Meaning |
|---|---|
| `backlog` | Work awaiting execution; only the ready feed establishes eligibility |
| `in_progress` | Claimed work; status alone is not process liveness |
| `in_review` | Reserved or parked work, including a review handoff |
| `done` | Accepted work with structured completion evidence |
| `canceled` | Intentionally abandoned work with a recorded reason |

Assignment, readiness, dispatch, claim, verification and installation are
separate events. A worker label or old Owner comment is not proof of a running
process. Consumers must not steal a claim because a record is quiet.

## 2) Agent flow

1. Read the selected workspace/project instructions and the assigned order.
2. Read `wl_ready` with explicit project and worker label; respect gates and
   dependencies. `wl_list` is an inventory, not a dispatch feed.
3. Use `wl_reserve` when a short reading reservation is necessary, or
   `wl_claim` to enter `in_progress` and record ownership before editing.
4. Implement only the assigned scope in a known working copy. Preserve
   unrelated edits and record decisions and useful checkpoints.
5. Verify the result. Use `wl_park` for a review/integration handoff. Use
   `wl_release` with a reason and next action for a stopped attempt. The
   executor must actually stop before another executor resumes its work.
6. Use `wl_close` only when the acceptance criteria and applicable integration
   or installation checks are satisfied. An empty eligible feed ends the run.

Use explicit lifecycle tools rather than relying on a comment heading to change
status. With `WORKLANE_COMMENT_TRANSITIONS=0`, MCP evidence comments cannot
perform lifecycle transitions; explicit tools retain their guards. This is an
evidence profile, not an authentication or access-control boundary.

### 2.1) Routing and dependencies

Use one `worker:<registered-id>` label. When the project has registered lane
workers, creation requires a valid seat. Before workers are registered,
unrouted work receives `needs:routing`. Never invent an executor. An interactive
host operation uses `worker:you` plus `you:host`; personal items use an explicit
`you:note`, `you:remind` or `you:todo` kind. Assignment does not itself guarantee
execution: the host must configure the runner, trigger, tools and permissions.

Readiness excludes non-backlog work, active gates, umbrellas and unresolved
explicit or structured `blocks` dependencies. Missing prerequisites remain
blocking. Done/canceled prerequisites resolve dependencies. Context-only prose
and arbitrary classification labels do not establish dependency semantics.
Cross-store dependencies use composite identities. Ready reads do not modify
relation data. Direct status changes also apply dependency guards.

## 3) Rules

1. Record actionable implementation work in its owning project. Cross-product
   changes require separately scoped orders; coordinating parents link them.
2. Work only within current authorization. Host instructions and worker contracts
   define access, publication and review policy; this protocol does not grant
   permission to deploy, spend money, publish history or change credentials.
3. Keep the assigned worker on a human blocker. Describe the specific action
   needed; do not move failed agent work into the personal queue.
4. Never cancel or close work merely to improve queue counts. Required acceptance
   stays open. Optional residual work needs an owning order and next action.
5. Preserve unique edits, revisions, runtime data and history before cleanup or
   a handoff. Do not fabricate evidence to satisfy a structural guard.
6. Tests use disposable stores and configured fake providers. Public documents,
   packages and support artifacts must not contain private runtime data.
7. No provider has implicit authority over another project's files or accounts.
8. **Signed writes:** every mutation identifies its actor; comments and Owner
   markers must agree. Attribution is not authentication. Keep the API bound
   to a trusted interface unless a deployment supplies appropriate protection.

### Gates

| Gate | Meaning |
|---|---|
| `human` | A specific human action is required; clear only with applicable authority |
| `timer` | Execution embargo until the recorded time |
| `deferred` | Intentionally parked work; name its activation condition |
| `tracking` | Structural coordination wrapper, excluded from dispatch |

Gates are independent of lifecycle status and assignment. A reminder date is
not an embargo. A browser-local mute is not a WorkLane state change. Clearing
a gate is an authorized decision; a runner must not thaw work to fill a queue.

## 4) Transitions

`wl_claim`, `wl_reserve`, `wl_park`, `wl_release`, `wl_close`, `wl_cancel` and
`wl_reopen` express lifecycle intent. Their server-side eligibility and
closeout guards apply regardless of the client. A rejected transition is a
visible failure, not permission to edit SQLite directly. Legacy lifecycle
comments remain compatible where enabled; new integrations should use explicit
operations. Check fresh status/ownership before resuming an interrupted task.

## 5) Intake and closeout

A useful intake contains a short Glance, Where, scope, risk, Done when and
Verify. It should be understandable without the originating conversation.
Use synthetic examples in public papers and keep host details in private
workspace records.

A claim records an Owner marker with the agent identity, Workdir, optional
Branch, Start timestamp and Plan. Provider/model details may accompany the
marker; they are not the author identity.

All completion evidence uses these four literal sections:

```text
Completed:
- What changed and which acceptance criteria it satisfies.
Verification:
- Commands/checks performed, results and relevant limits.
Links:
- Actual landing revision and useful artifact references.
Follow-ups:
- Existing work-order IDs, or none when nothing remains.
```

### 5.1) Closeout guard

Source implementation cites a real landing commit (7–40 hexadecimal digits)
in Links. A path or PR may accompany it. The structural check does not prove
that a SHA exists or that tests passed; the executor verifies both. Publication,
integration and deployment follow the selected workspace's policy, never a
hardcoded organization rule. Work parked for integration is not complete.

Configured closeout checks may require named verification evidence. The engine
checks the supplied record; it does not execute those commands. Required child
work also remains subject to coverage guards. Inspect dirty/untracked files
and unique commits before leaving or removing a working copy.

An interactive operation authored by `you` and labeled `worker:you` plus
`you:host` may cite a navigable local evidence path for a host-only change.
This exception does not excuse source changes from real revision evidence.

### 5.2) Identity and attribution

Use `you` for an interactive human session and a dedicated registered worker
identity for unattended execution. Provider names, model names and people are
separate from worker identities. Legacy IDs remain readable history; they do
not register current capacity. Each installation owns its roster and host
profiles outside distributable product source.

### 5.3) New worker onboarding

Define project scope, allowed paths/tools, identity, execution host, trigger,
budget, verification, stop conditions and recovery procedure. Connect its MCP
with explicit runtime/project settings. Verify the wiring in a disposable
project before allowing live work. A configuration check is not a live capacity
or quota test. See [HOST_PROFILE_TEMPLATE.md](HOST_PROFILE_TEMPLATE.md).

### 5.4) Wiring verification

Verify the selected runtime directory, project/store identity and worker
configuration from observed responses. Test missing/unavailable sources and
refusals. Do not silently substitute another service or workspace.

### 5.5) Concurrent-edit safety

Use isolated working copies or explicitly exclusive paths. A task claim does
not itself lock arbitrary filesystem writes. A handoff preserves artifacts,
records a checkpoint, proves the previous writer stopped and transfers work
through the owning engine. Native provider conversation state is not presumed
portable. Current continuation guarantees are documented and tested separately.

## 6) Host profiles

Each installation owns its own host profile. The product includes no personal
roster, cron schedules, private repository names or organization-specific
publication process. Reusable setup is in [INSTALL.md](INSTALL.md).

## 7) API and surface

MCP exposes `wl_*`, the CLI is `wl`, and the service entrypoint is `worklane`.
They address the same project stores. BluePrint is an optional interface;
WorkForce is an optional executor. Supported UI actions must use the same
engine guards and explicit scope as CLI/MCP clients.

### 7.1) Project registration

Bootstrap through the products API before filing work. When a workspace root
is configured, its project-folder and instruction registration rules apply.
Keep backups and retired stores outside the live data directory. Do not copy,
rename or discard SQLite/WAL files as an informal migration; stop writers and
use a reviewed backup/recovery procedure. Package updates preserve runtime data.
