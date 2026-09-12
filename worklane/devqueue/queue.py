"""Shared read-only eligibility policy for HTTP, MCP, and dev queues.

Explicit prose declarations and structured blocks relations both apply.
Done or canceled prerequisites are resolved; unknown references fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

from worklane.trackers.protocol import ProjectTracker, Task, TaskStatus, task_is_gated


def parse_blockers(description: str) -> List[str]:
    """Use the tracker's explicit declaration grammar on every ready surface."""
    from worklane.trackers.sqlite import _parse_blockers
    return _parse_blockers(description)


# ── public datatypes ─────────────────────────────────────────────────────

@dataclass
class BlockerInfo:
    """Details about a single blocker for a blocked task."""

    ticket_id: str
    title: str  # empty string if unknown
    status: str  # empty string if unknown

    def to_dict(self) -> Dict[str, str]:
        return {"ticket_id": self.ticket_id, "title": self.title, "status": self.status}


@dataclass
class BlockedTask:
    """A backlog task that can't be dispatched because of unresolved blockers."""

    task: Task
    blockers: List[BlockerInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            **self.task.to_dict(),
            "blockers": [b.to_dict() for b in self.blockers],
        }


@dataclass
class Batch:
    """A group of tickets the dev can dispatch to one terminal at once."""

    tickets: List[Task]
    shared_files: List[str] = field(default_factory=list)

    @property
    def ids(self) -> List[str]:
        return [t.ext_id or t.id for t in self.tickets]

    def to_dict(self) -> Dict[str, object]:
        return {
            "ids": self.ids,
            "titles": [t.title for t in self.tickets],
            "shared_files": list(self.shared_files),
        }


# ── work queue ───────────────────────────────────────────────────────────

# Lower number = higher urgency (matches Linear's priority field, where
# 1 = Urgent and 4 = Low). Tasks with priority 0 ("None") sort last.
def _priority_key(task: Task) -> tuple[int, str]:
    p = int(task.priority or 0)
    bucket = p if 1 <= p <= 4 else 99
    return (bucket, task.updated_at or "")


_READY_STATUSES = (TaskStatus.BACKLOG,)


class WorkQueue:
    """Read-only view over the tracker's ready queue.

    Construct once per request — instances cache the loaded task list so
    repeated lookups (priority filter, dependency check) don't re-hit
    the tracker. Mutating tracker state should still go through
    ``ProjectTracker`` directly.
    """

    def __init__(self, tracker: ProjectTracker, *, limit: Optional[int] = None) -> None:
        self._tracker = tracker
        self._limit = limit
        # Eligibility must include old open work and completed prerequisites.
        # Apply presentation limits only after ready filtering and sorting.
        self._all: List[Task] = list(tracker.list_tasks(limit=limit))
        self._by_ext: Dict[str, Task] = {}
        for t in self._all:
            if t.ext_id:
                self._by_ext[t.ext_id] = t
            self._by_ext[t.id] = t

        self._relations: Dict[str, List[str]] = {}
        from worklane.trackers.sqlite import SQLiteTracker
        if isinstance(tracker, SQLiteTracker):
            # The tracker has initialized its schema above. Read only; relation
            # failures propagate rather than silently making blocked work ready.
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(tracker._db_path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
                for source, target in conn.execute(
                    "SELECT from_id, to_id FROM task_relations WHERE relation_type = 'blocks'"
                ):
                    self._relations.setdefault(str(target), []).append(str(source))

    # ── accessors ────────────────────────────────────────────────────

    @property
    def all_tasks(self) -> List[Task]:
        return list(self._all)

    def by_status(self, status: str) -> List[Task]:
        return [t for t in self._all if t.status == status]

    def in_progress(self) -> List[Task]:
        return self.by_status(TaskStatus.IN_PROGRESS)

    # ── filtering ────────────────────────────────────────────────────

    def _is_done(self, ticket_id: str) -> bool:
        t = self._by_ext.get(ticket_id)
        return t is not None and t.status in (TaskStatus.DONE, TaskStatus.CANCELED)

    def blockers_for(self, task: Task) -> List[str]:
        return list(dict.fromkeys(parse_blockers(task.description) + self._relations.get(str(task.id), [])))

    def is_ready(self, task: Task) -> bool:
        """True if every declared or structured blocker is done or canceled.

        Unknown blockers (referenced ticket isn't in the local tracker)
        count as still blocking — safer than dispatching work whose
        prerequisites we can't verify.
        """
        for bid in self.blockers_for(task):
            if not self._is_done(bid):
                return False
        return True

    def ready(
        self,
        *,
        statuses: Sequence[str] = _READY_STATUSES,
        labels: Optional[Sequence[str]] = None,
    ) -> List[Task]:
        """Return tasks eligible for dispatch, sorted by priority.

        ``statuses`` — which statuses count as "ready to start". Defaults
        to backlog only; pass ``(BACKLOG, IN_PROGRESS)`` to include
        already-claimed work in the surface.
        ``labels`` — optional whitelist; only tickets whose label set
        intersects the filter survive.
        """
        wanted_statuses = set(statuses)
        wanted_labels = set(labels) if labels else None

        candidates = [t for t in self._all if t.status in wanted_statuses]
        if wanted_labels is not None:
            candidates = [
                t for t in candidates if wanted_labels.intersection(t.labels)
            ]
        candidates = [t for t in candidates if self.is_ready(t)]
        candidates = [t for t in candidates if not task_is_gated(t)]
        # wl-297: defense-in-depth — umbrella coordination wrappers never dispatch
        candidates = [t for t in candidates if "umbrella" not in t.labels]
        candidates.sort(key=_priority_key)
        return candidates

    # ── blocked ──────────────────────────────────────────────────────

    def blocked(self) -> List[BlockedTask]:
        """Backlog tasks that fail is_ready() — blockers not yet done.

        Returns each task paired with details about its unresolved
        blockers so the dashboard can show *why* it's stuck.
        """
        out: List[BlockedTask] = []
        for t in self._all:
            if t.status != TaskStatus.BACKLOG:
                continue
            blocker_ids = self.blockers_for(t)
            if not blocker_ids:
                continue  # no blockers declared — it's ready, not blocked
            unresolved: List[BlockerInfo] = []
            for bid in blocker_ids:
                dep = self._by_ext.get(bid)
                if dep is None:
                    unresolved.append(BlockerInfo(ticket_id=bid, title="", status=""))
                elif dep.status != TaskStatus.DONE:
                    unresolved.append(BlockerInfo(
                        ticket_id=dep.ext_id or dep.id,
                        title=dep.title,
                        status=dep.status,
                    ))
            if unresolved:
                out.append(BlockedTask(task=t, blockers=unresolved))
        out.sort(key=lambda bt: _priority_key(bt.task))
        return out

    # ── orphans ──────────────────────────────────────────────────────

    def orphans(self) -> List[Task]:
        """Tickets stuck in ``in_progress`` from a previous session.

        The dashboard surfaces these on startup so the developer can
        resume, comment, or hand them off rather than letting them rot.
        """
        return self.by_status(TaskStatus.IN_PROGRESS)


# ── dispatch prompt ──────────────────────────────────────────────────────

def build_dispatch_prompt(tickets: Iterable[Task]) -> str:
    """Render the Claude Code prompt for an approved batch.

    Output is the literal text the developer pastes into a fresh Claude
    Code session — e.g. ``"work SEO-164, SEO-180"``. The session
    instructions in :doc:`AGENTS.md` already define the per-ticket
    protocol, so the prompt only needs to name the tickets.
    """
    ids = [t.ext_id or t.id for t in tickets if (t.ext_id or t.id)]
    if not ids:
        return ""
    if len(ids) == 1:
        return f"work {ids[0]}"
    return "work " + ", ".join(ids)


__all__ = [
    "Batch",
    "BlockedTask",
    "BlockerInfo",
    "WorkQueue",
    "build_dispatch_prompt",
    "find_orphans",
    "parse_blockers",
]
