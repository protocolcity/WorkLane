"""Scoped checkpoint and handoff adapters; persistence remains in the tracker."""
from worklane.mcp.handlers.errors import ToolError


class ContinuityHandlers:
    def wl_checkpoint(self, task_id, checkpoint, expected_version, product=None):
        slug, raw_id, tracker, task = self._resolve_task(task_id, product, write=True)
        if not isinstance(checkpoint, dict) or checkpoint.get("project") != slug:
            raise ToolError("checkpoint project differs from selected store")
        try:
            result = tracker.checkpoint_work(raw_id, self.author, checkpoint, expected_version)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        return dict(result, ok=True, task_id=self._public_id(slug, raw_id), product=slug)

    def wl_handoff(self, task_id, previous_owner, next_owner, expected_version,
                   checkpoint_id, stopped_evidence, product=None):
        slug, raw_id, tracker, task = self._resolve_task(task_id, product, write=True)
        from worklane.api.tasks.helpers import _workforce_workers_for_product
        workers = {name.removeprefix("worker:") for name in _workforce_workers_for_product(slug)}
        if next_owner not in workers:
            raise ToolError("receiving worker is not registered for the selected project")
        try:
            fresh = tracker.handoff_work(raw_id, self.author, previous_owner=previous_owner,
                next_owner=next_owner, expected_version=expected_version,
                checkpoint_id=checkpoint_id, stopped_evidence=stopped_evidence)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        return {"ok": True, "task": self._task_dict(slug, fresh)}
