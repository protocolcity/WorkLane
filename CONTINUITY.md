# Continue work across providers

WorkLane preserves the work record. An execution owner such as WorkForce
controls processes, provider capacity and filesystem access. Neither component
assumes another provider can import a proprietary chat session.

The checkpoint/handoff API described here is part of the current source
candidate. Install a version containing these operations before calling them;
older clients retain the ordinary work-order tools. Automatic provider selection
and failover additionally require a qualified execution integration.

## Checkpoint

The current owner calls `wl_checkpoint` with explicit project, task ID,
`expected_version` equal to the latest task `updated_at`, and a checkpoint:

```json
{
  "version": 1,
  "project": "example",
  "workspace_id": "workspace-example",
  "objective": "Fix the failing import",
  "acceptance": "Import works in the built package",
  "scope": "The owning package and its regression tests",
  "instruction_revision": "rules-v1",
  "source_revision": "the observed commit",
  "branch": "fix/import",
  "decisions": ["Keep the public import compatible"],
  "artifacts": [],
  "checks": ["Unit regression passed"],
  "remaining": ["Test the installed wheel"],
  "blocker": "Provider quota exhausted",
  "next_action": "Build and install the candidate in a disposable environment"
}
```

Artifact entries contain `ref`, a lowercase SHA-256 digest and `access`
requirements. Capture uncommitted changes as protected artifacts before a
handoff. Keep credentials and transcripts outside the checkpoint. Large
artifacts are referenced rather than embedded; the record is limited to 64 KiB.

The operation appends a signed versioned comment without changing status.
Its result includes `checkpoint_id` and the new `updated_at`. Another owner's
write or an outdated expected version is refused. A checkpoint is a verified
handoff input only when the receiving runner checks its facts independently.

## Stop, transfer, validate, claim

1. Stop the previous writer and preserve its working copy and artifacts. The
   runner records process/lock exit evidence; a quiet work order is insufficient.
2. Reread the work and its latest checkpoint. Choose a registered executor with
   matching project, tools, host authority and observed available capacity.
3. The previous owner or authorized host actor calls `wl_handoff` with explicit
   project, task ID, `previous_owner`, `next_owner`, current `expected_version`,
   latest `checkpoint_id` and nonempty `stopped_evidence` reference.
4. The receiving runner reads and acknowledges the checkpoint, checks workspace,
   project, instructions, source revision and artifact hashes, and then claims
   eligible work under its own identity. `validate_resume` provides the shared
   comparison contract; the runner supplies independently observed values.

Handoff atomically records lineage, reassigns the existing work order and returns
it to backlog. Gates and dependency restrictions remain intact. It does not
launch a provider or wake a worker. Stale versions, changed owners, an older or
foreign checkpoint, and unregistered receiving seats are refused. Repeating a
successful request with its old version fails rather than transferring twice.

Stopped-writer evidence is an execution-owner attestation. WorkLane cannot
inspect arbitrary remote processes or prove the assertion from a string. The
runner must enforce process/lock checks; permission or authentication refusal
does not authorize switching to a less restricted executor. A crash before a
checkpoint requires explicit artifact recovery, never an invented checkpoint.

## Interfaces and limits

MCP supplies `wl_checkpoint` and `wl_handoff`. HTTP POST endpoints are
`/api/admin/tasks/{id}/checkpoint`, `/handoff` and `/claim`; their JSON body
includes `author` and explicit `project`. They use the same handlers as MCP.
Conflicts return a refusal; reread and resolve the cause rather than blind retry.

MCP claim/reserve and the HTTP claim endpoint persist ownership and status in
one transaction. Concurrent claims have one winner. Legacy raw status changes
are not a replacement for this ownership protocol. Legacy Owner comments are
checked transactionally before insertion; a different worker cannot overwrite
an active owner, release their work, or mark it terminal. An authorized host
actor may reconcile lifecycle state but still must prove a stopped writer before
launching another executor. Actor attribution is not
authentication; deployments still need a trusted API boundary and scoped tools.

See [PROTOCOL.md](PROTOCOL.md) for lifecycle and [INSTALL.md](INSTALL.md) for
runtime selection. Tests exercise races, stale versions, gates, lineage,
wrong-workspace/source inputs and missing artifacts in disposable stores.
