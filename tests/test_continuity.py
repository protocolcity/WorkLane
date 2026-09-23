"""Interrupted-work guarantees against real disposable SQLite stores."""
import copy
import json
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from worklane.continuity import CHECKPOINT_PREFIX, validate_resume
from worklane.mcp.handlers import TPHandlers, ToolError, dispatch_tool
from worklane.trackers.sqlite import SQLiteTracker


@pytest.fixture
def context():
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "WORKLANE_RUNTIME_DIR": tmp, "WORKFORCE_NO_DESK": "1"}):
        tracker = SQLiteTracker(db_path=Path(tmp) / "data" / "worklane.db")
        task = tracker.create_task(title="Resume safely", description="Preserve verified work")
        yield tracker, task, TPHandlers(author="alpha", default_product="worklane")


def checkpoint():
    return {"version": 1, "project": "worklane", "workspace_id": "workspace-example",
            "objective": "Complete the fix", "acceptance": "Regression passes",
            "scope": "Owned repository", "instruction_revision": "rules-v1",
            "source_revision": "a" * 40, "branch": "fix/example", "decisions": [],
            "artifacts": [{"ref": "patch.diff", "sha256": "b" * 64,
                           "access": "project checkout; do not publish"}],
            "checks": ["regression passed"], "remaining": ["review"],
            "next_action": "Review the preserved patch", "blocker": "quota exhausted"}


def claim(tracker, task, actor="alpha", **kwargs):
    return tracker.claim_work(task.id, actor, "Owner: " + actor + "\nPlan:\n- Verify", **kwargs)


def test_concurrent_claims_have_one_owner(context):
    tracker, task, _ = context
    barrier = threading.Barrier(2)

    def attempt(actor):
        barrier.wait()
        try:
            claim(tracker, task, actor)
            return actor
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = list(pool.map(attempt, ["alpha", "beta"]))
    assert sum(x is not None for x in winners) == 1
    owners = [c.author for c in tracker.list_comments(task.id) if c.body.startswith("Owner:")]
    assert owners == [next(x for x in winners if x)]
    assert tracker.get_task(task.id).status == "in_progress"


def test_mcp_cannot_reclaim_another_actors_reservation(context):
    tracker, task, alpha = context
    alpha.wl_reserve(task.id, product="worklane")
    beta = TPHandlers(author="beta", default_product="worklane")
    with pytest.raises(ToolError, match="owned by alpha"):
        beta.wl_claim(task.id, product="worklane")
    assert alpha.wl_claim(task.id, product="worklane")["task"]["status"] == "in_progress"


def test_gated_claim_leaves_no_owner_or_status_change(context):
    tracker, task, _ = context
    tracker.update_task(task.id, gate_type="human", gate_note="Need a credential")
    before = tracker.get_task(task.id)
    with pytest.raises(ValueError, match="gated"):
        claim(tracker, task)
    assert tracker.get_task(task.id).updated_at == before.updated_at
    assert not any(c.body.startswith("Owner:") for c in tracker.list_comments(task.id))


def test_raw_status_cannot_promote_another_owners_reservation(context):
    tracker, task, _ = context
    claim(tracker, task, reserve=True)
    with pytest.raises(ValueError, match="owned by alpha"):
        tracker.update_status(task.id, "in_progress", actor="beta")
    assert tracker.get_task(task.id).status == "in_review"


def test_unknown_active_owner_is_not_a_free_claim(context):
    tracker, task, _ = context
    tracker.update_status(task.id, "in_progress")
    with pytest.raises(ValueError, match="unknown ownership"):
        claim(tracker, task)


def test_checkpoint_cas_and_owner(context):
    tracker, task, alpha = context
    active = claim(tracker, task)
    cp = alpha.wl_checkpoint(task.id, checkpoint(), active.updated_at, product="worklane")
    assert tracker.get_task(task.id).status == "in_progress"
    assert tracker.list_comments(task.id)[-1].body.startswith(CHECKPOINT_PREFIX)
    with pytest.raises(ToolError, match="stale"):
        alpha.wl_checkpoint(task.id, checkpoint(), active.updated_at, product="worklane")
    with pytest.raises(ValueError, match="current owner"):
        tracker.checkpoint_work(task.id, "beta", checkpoint(), cp["updated_at"])


def test_handoff_preserves_lineage_gates_and_exclusive_receiver(context):
    tracker, task, alpha = context
    active = claim(tracker, task)
    cp = alpha.wl_checkpoint(task.id, checkpoint(), active.updated_at, product="worklane")
    # A human gate remains an embargo across a provider handoff.
    tracker.update_task(task.id, gate_type="human", gate_note="Read the review")
    version = tracker.get_task(task.id).updated_at
    args = dict(task_id=task.id, product="worklane", previous_owner="alpha",
                next_owner="beta", expected_version=version,
                checkpoint_id=cp["checkpoint_id"], stopped_evidence="run receipt: exited; lock released")
    with patch("worklane.api.tasks.helpers._workforce_workers_for_product", return_value=["beta"]):
        with pytest.raises(ToolError, match="stopped-writer"):
            alpha.wl_handoff(**dict(args, stopped_evidence=""))
        result = alpha.wl_handoff(**args)
        with pytest.raises(ToolError, match="stale"):
            alpha.wl_handoff(**args)
    assert result["task"]["status"] == "backlog"
    assert result["task"]["gate_type"] == "human"
    assert "worker:beta" in result["task"]["labels"]
    tracker.update_task(task.id, gate_type="")
    with pytest.raises(ValueError, match="assigned"):
        claim(tracker, task, "alpha")
    claim(tracker, task, "beta")
    assert "Work handoff v1:" in "\n".join(c.body for c in tracker.list_comments(task.id))


def test_unregistered_or_foreign_checkpoint_refused(context):
    tracker, task, alpha = context
    active = claim(tracker, task)
    with pytest.raises(ToolError, match="project differs"):
        alpha.wl_checkpoint(task.id, dict(checkpoint(), project="foreign"), active.updated_at,
                            product="worklane")
    cp = alpha.wl_checkpoint(task.id, checkpoint(), active.updated_at, product="worklane")
    with patch("worklane.api.tasks.helpers._workforce_workers_for_product", return_value=[]):
        with pytest.raises(ToolError, match="not registered"):
            alpha.wl_handoff(task.id, "alpha", "beta", cp["updated_at"], cp["checkpoint_id"],
                             "stopped receipt", product="worklane")
    with pytest.raises(ValueError, match="checkpoint does not belong"):
        tracker.handoff_work(task.id, "alpha", previous_owner="alpha", next_owner="beta",
            expected_version=cp["updated_at"], checkpoint_id="999999", stopped_evidence="stopped")


@pytest.mark.parametrize("field", ["project", "workspace_id", "source_revision", "instruction_revision"])
def test_resume_refuses_context_mismatch(field):
    cp = checkpoint()
    facts = {k: cp[k] for k in ("project", "workspace_id", "source_revision", "instruction_revision")}
    facts[field] = "wrong"
    with pytest.raises(ValueError, match="resume mismatch"):
        validate_resume(cp, artifact_hashes={"patch.diff": "b" * 64}, **facts)


def test_resume_requires_observed_artifact_hash():
    cp = checkpoint()
    facts = {k: cp[k] for k in ("project", "workspace_id", "source_revision", "instruction_revision")}
    with pytest.raises(ValueError, match="missing or changed"):
        validate_resume(cp, artifact_hashes={}, **facts)
    assert validate_resume(cp, artifact_hashes={"patch.diff": "b" * 64}, **facts) == cp


def test_http_checkpoint_requires_explicit_project_and_signed_owner(context):
    from fastapi.testclient import TestClient
    from worklane.task_server import create_app
    tracker, task, _ = context
    active = claim(tracker, task)
    with TestClient(create_app()) as client:
        url = "/api/admin/tasks/" + task.id + "/checkpoint"
        payload = {"author": "alpha", "checkpoint": checkpoint(), "expected_version": active.updated_at}
        assert client.post(url, json=payload).status_code == 409
        response = client.post(url, json=dict(payload, project="worklane"))
        assert response.status_code == 200, response.text


def test_installed_package_does_not_inherit_ancestor_workspace():
    from worklane.task_server import _city_root_path
    with patch.dict(os.environ, {"WL_CITY_ROOT": ""}), \
            patch("worklane.products._is_source_checkout", return_value=False):
        assert _city_root_path() is None


def test_http_detail_reports_verified_store_and_refuses_mismatch(context):
    from fastapi.testclient import TestClient
    from worklane.task_server import create_app
    tracker, task, _ = context
    with TestClient(create_app()) as client:
        url = "/api/admin/tasks/" + task.id
        response = client.get(url, params={"product": "worklane"})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["product"] == data["task"]["product"] == "worklane"
        assert data["task"]["id"] == task.id
        composite = "/api/admin/tasks/wl-" + task.id
        assert client.get(composite, params={"product": "worklane"}).json()["task"]["product"] == "worklane"
        assert client.get(composite, params={"product": "workforce"}).status_code == 409


def test_http_handoff_uses_real_registered_roster_names(context, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from worklane.task_server import create_app
    tracker, task, _ = context
    active = claim(tracker, task)
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"workers": {"beta": {"kind": "lane",
        "queue_url": "http://example.invalid/api/admin/tasks/ready?product=worklane"}}}))
    monkeypatch.setenv("WL_WORKFORCE_LOCAL_ONLY", "1")
    monkeypatch.setenv("WL_WORKFORCE_ROSTER", str(roster))
    with TestClient(create_app()) as client:
        url = "/api/admin/tasks/wl-" + task.id
        cp = client.post(url + "/checkpoint", json=dict(author="alpha", project="worklane",
            checkpoint=checkpoint(), expected_version=active.updated_at))
        assert cp.status_code == 200, cp.text
        data = cp.json()
        handed = client.post(url + "/handoff", json=dict(author="you", project="worklane",
            previous_owner="alpha", next_owner="beta", checkpoint_id=data["checkpoint_id"],
            expected_version=data["updated_at"], stopped_evidence="fixture process stopped"))
        assert handed.status_code == 200, handed.text
        assert [x for x in handed.json()["task"]["labels"] if x.startswith("worker:")] == ["worker:beta"]

@pytest.mark.parametrize("status", ["in_progress", "in_review"])
def test_legacy_owner_comment_cannot_replace_active_owner(context, status):
    tracker, task, _ = context
    claim(tracker, task, reserve=(status == "in_review"))
    before = tracker.get_task(task.id)
    comments = tracker.list_comments(task.id)
    with pytest.raises(ValueError, match="owned by alpha"):
        tracker.add_comment(task.id, "Owner: beta\nPlan:\n- Take over", author="beta")
    assert tracker.list_comments(task.id) == comments
    assert tracker.get_task(task.id).updated_at == before.updated_at
    assert tracker.get_task(task.id).status == status


def test_legacy_owner_marker_requires_matching_author(context):
    tracker, task, _ = context
    with pytest.raises(ValueError, match="matching signed Owner"):
        tracker.add_comment(task.id, "Owner: alpha\nPlan:\n- Verify", author="beta")
    assert tracker.get_task(task.id).status == "backlog"


def test_legacy_claim_checks_assignment_and_gate(context):
    tracker, task, _ = context
    tracker.update_labels(task.id, add=["worker:alpha"])
    with pytest.raises(ValueError, match="assigned"):
        tracker.add_comment(task.id, "Owner: beta\nPlan:\n- Verify", author="beta")
    tracker.update_task(task.id, gate_type="human", gate_note="Credential needed")
    with pytest.raises(ValueError, match="gated"):
        tracker.add_comment(task.id, "Owner: alpha\nPlan:\n- Verify", author="alpha")

@pytest.mark.parametrize("status", ["backlog", "done", "canceled"])
def test_other_actor_cannot_release_or_finish_owned_work(context, status):
    tracker, task, _ = context
    claim(tracker, task)
    with pytest.raises(ValueError, match="owned by alpha"):
        tracker.update_status(task.id, status, actor="beta")
    assert tracker.get_task(task.id).status == "in_progress"


@pytest.mark.parametrize("body", ["Blocked: stopped\nNext step: retry", "Completed: done\nVerification: test"])
def test_legacy_lifecycle_cannot_release_another_owner(context, body):
    tracker, task, _ = context
    claim(tracker, task)
    comments = tracker.list_comments(task.id)
    with pytest.raises(ValueError, match="owned by alpha"):
        tracker.add_comment(task.id, body, author="beta")
    assert tracker.get_task(task.id).status == "in_progress"
    assert tracker.list_comments(task.id) == comments
