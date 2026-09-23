"""Provider-independent checkpoints and transactional work ownership.

Records use the existing signed comment stream. Process-stop evidence is an
attestation from the execution owner; WorkLane cannot inspect a remote process.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


CHECKPOINT_PREFIX = "Work checkpoint v1:\n"
_OWNER = re.compile(r"^\s*Owner:\s*([^\s(]+)", re.MULTILINE | re.IGNORECASE)


def validate_checkpoint(value: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("checkpoint version must be 1")
    required = ("project", "workspace_id", "objective", "acceptance", "scope",
                "instruction_revision", "source_revision", "branch", "next_action")
    for key in required:
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError("checkpoint requires " + key)
    for key in ("decisions", "artifacts", "checks", "remaining"):
        if not isinstance(value.get(key), list):
            raise ValueError("checkpoint requires list " + key)
    for artifact in value["artifacts"]:
        if (not isinstance(artifact, dict) or
                not all(isinstance(artifact.get(k), str) and artifact[k].strip()
                        for k in ("ref", "sha256", "access")) or
                not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"])):
            raise ValueError("artifacts require ref, sha256 and access requirements")
    allowed = set(required) | {"version", "decisions", "artifacts", "checks",
                               "remaining", "blocker", "provider_session_ref"}
    if set(value) - allowed:
        raise ValueError("unsupported checkpoint fields; never store credentials or transcripts")
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True)
    if len(encoded.encode()) > 65536:
        raise ValueError("checkpoint exceeds 64 KiB; reference protected artifacts")
    return json.loads(encoded)


def validate_resume(checkpoint, *, project, workspace_id, source_revision,
                    instruction_revision, artifact_hashes):
    """Validate against facts independently observed by the receiving runner."""
    data = validate_checkpoint(checkpoint)
    for key, expected in (("project", project), ("workspace_id", workspace_id),
                          ("source_revision", source_revision),
                          ("instruction_revision", instruction_revision)):
        if data[key] != expected:
            raise ValueError("resume mismatch: " + key)
    for artifact in data["artifacts"]:
        if artifact_hashes.get(artifact["ref"]) != artifact["sha256"]:
            raise ValueError("missing or changed resume artifact: " + artifact["ref"])
    return data


class ContinuityMixin:
    def _continuity_row(self, conn, task_id, expected_version=None):
        row = conn.execute("SELECT * FROM tasks WHERE id = ? OR ext_id = ? LIMIT 1",
                           (self._maybe_int(task_id), str(task_id))).fetchone()
        if row is None:
            raise ValueError("task not found")
        if expected_version is not None and row["updated_at"] != expected_version:
            raise ValueError("stale work version; reread before retrying")
        return row

    def _claim_owner(self, conn, task_pk):
        for comment in conn.execute(
                "SELECT body, author FROM task_comments WHERE task_id = ? ORDER BY id DESC",
                (task_pk,)):
            marker = _OWNER.search(comment["body"])
            if marker:
                owner = marker.group(1)
                if owner != comment["author"]:
                    raise ValueError("ambiguous signed ownership; reconcile before resuming")
                return owner
        return None

    def claim_work(self, task_id, actor, body, *, reserve=False,
                   expected_version=None):
        from worklane.trackers.protocol import TaskStatus, task_is_gated
        from worklane.trackers.sqlite import _now_iso, _row_to_task
        if not actor or not _OWNER.search(body) or _OWNER.search(body).group(1) != actor:
            raise ValueError("claim requires a matching signed Owner marker")
        with self._connect() as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._continuity_row(conn, task_id, expected_version)
            task = _row_to_task(row)
            if task.status not in (TaskStatus.BACKLOG, TaskStatus.IN_REVIEW,
                                   TaskStatus.IN_PROGRESS):
                raise ValueError("cannot claim terminal work")
            if reserve and task.status == TaskStatus.IN_PROGRESS:
                raise ValueError("use wl_park for in_progress work")
            owner = self._claim_owner(conn, row["id"])
            if task.status == TaskStatus.IN_PROGRESS and owner is None:
                raise ValueError("active work has unknown ownership; reconcile before resuming")
            if task.status != TaskStatus.BACKLOG and owner and owner != actor:
                raise ValueError("work is owned by " + owner + "; explicit handoff required")
            if task_is_gated(task) or "umbrella" in task.labels:
                raise ValueError("work is gated or tracking")
            workers = [label[7:] for label in task.labels if label.startswith("worker:")]
            if workers and workers != [actor]:
                raise ValueError("work is assigned to another worker")
            if self._unresolved_blockers(conn, task):
                raise ValueError("work has unresolved dependencies")
            now = _now_iso()
            status = TaskStatus.IN_REVIEW if reserve else TaskStatus.IN_PROGRESS
            conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                         (status, now, row["id"]))
            self._insert_comment(conn, row["id"], body, actor, now)
            if status != task.status:
                self._insert_event(conn, row["id"], "status_change", status=status,
                                   actor=actor, now=now)
            if status == TaskStatus.IN_PROGRESS:
                self._freeze_dependents_for_anchor(conn, task, now)
        return self.get_task(task_id)

    def checkpoint_work(self, task_id, actor, checkpoint, expected_version):
        from worklane.trackers.protocol import TaskStatus
        from worklane.trackers.sqlite import _now_iso
        data = validate_checkpoint(checkpoint)
        if not expected_version:
            raise ValueError("checkpoint requires expected_version")
        with self._connect() as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._continuity_row(conn, task_id, expected_version)
            if row["status"] not in (TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW):
                raise ValueError("checkpoint requires owned active or parked work")
            if self._claim_owner(conn, row["id"]) != actor:
                raise ValueError("only the current owner may checkpoint work")
            now = _now_iso()
            self._insert_comment(conn, row["id"], CHECKPOINT_PREFIX + json.dumps(data,
                                 sort_keys=True, ensure_ascii=True), actor, now)
            checkpoint_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, row["id"]))
        return {"checkpoint_id": str(checkpoint_id), "updated_at": now, "checkpoint": data}

    def handoff_work(self, task_id, actor, *, previous_owner, next_owner,
                     expected_version, checkpoint_id, stopped_evidence):
        from worklane.trackers.protocol import TaskStatus
        from worklane.trackers.sqlite import _now_iso
        if actor not in (previous_owner, "you"):
            raise ValueError("handoff requires current owner or authorized host actor")
        if (not isinstance(stopped_evidence, str) or not stopped_evidence.strip()
                or not expected_version or not checkpoint_id):
            raise ValueError("handoff requires stopped-writer evidence, version and checkpoint")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", next_owner or ""):
            raise ValueError("invalid receiving worker identity")
        if next_owner == previous_owner:
            raise ValueError("handoff needs a different receiving worker")
        with self._connect() as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._continuity_row(conn, task_id, expected_version)
            if row["status"] not in (TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW):
                raise ValueError("handoff requires active or parked work")
            if self._claim_owner(conn, row["id"]) != previous_owner:
                raise ValueError("previous owner changed; reread work")
            cp = conn.execute("SELECT * FROM task_comments WHERE id = ? AND task_id = ?",
                              (checkpoint_id, row["id"])).fetchone()
            if cp is None or cp["author"] != previous_owner or not cp["body"].startswith(CHECKPOINT_PREFIX):
                raise ValueError("checkpoint does not belong to this task and owner")
            latest = conn.execute(
                "SELECT id FROM task_comments WHERE task_id = ? AND body LIKE ? ORDER BY id DESC LIMIT 1",
                (row["id"], CHECKPOINT_PREFIX + "%")).fetchone()
            if latest is None or str(latest["id"]) != str(checkpoint_id):
                raise ValueError("handoff requires the latest checkpoint")
            validate_checkpoint(json.loads(cp["body"][len(CHECKPOINT_PREFIX):]))
            labels = [x for x in json.loads(row["labels"] or "[]") if not x.startswith("worker:")]
            labels.append("worker:" + next_owner)
            now = _now_iso()
            conn.execute("UPDATE tasks SET status = ?, labels = ?, updated_at = ? WHERE id = ?",
                         (TaskStatus.BACKLOG, json.dumps(labels), now, row["id"]))
            record = {"version": 1, "previous_owner": previous_owner, "next_owner": next_owner,
                      "checkpoint_id": str(checkpoint_id), "stopped_evidence": stopped_evidence,
                      "previous_version": expected_version}
            self._insert_comment(conn, row["id"], "Work handoff v1:\n" + json.dumps(record), actor, now)
            self._insert_event(conn, row["id"], "status_change", status=TaskStatus.BACKLOG,
                               actor=actor, now=now)
        return self.get_task(task_id)
