"""Hermetic isolation fixtures for the test suite."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_ntfy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent any test from pushing to ntfy (wl-302). No network in CI."""
    monkeypatch.setenv("WL_NTFY_DISABLE", "1")


@pytest.fixture(autouse=True)
def _disable_wake_nudge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent any test from POSTing WorkForce /api/wake (wl-359)."""
    monkeypatch.setenv("WL_WAKE_DISABLE", "1")


@pytest.fixture(autouse=True)
def _isolate_workforce(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block the WorkForce lookup and roster fallback for all tests (wl-282, wl-287, wl-306).

    _workforce_workers_for_product has three sources: the HTTP API (blocked by
    pointing WL_WORKFORCE_URL at a refused port), the local roster file (blocked
    by clearing WL_WORKFORCE_ROSTER and WORKFORCE_PREDIRTY), and the city-root
    auto-discovered roster (blocked by WL_WORKFORCE_NO_CITY_ROSTER=1 — wl-306).
    Clearing all three keeps every test hermetic against the machine's live roster
    regardless of what env vars the launch environment exports.

    Tests that need a specific roster (test_create_task_routing_warning.py)
    set WL_WORKFORCE_ROSTER explicitly in setUp and clean it up in tearDown;
    those overrides take precedence and are restored before this fixture runs.
    Tests that exercise city-root auto-discovery pop WL_WORKFORCE_NO_CITY_ROSTER
    in the test body and restore CWD when done.
    """
    monkeypatch.setenv("WL_WORKFORCE_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("WL_WORKFORCE_ROSTER", raising=False)
    monkeypatch.delenv("WORKFORCE_PREDIRTY", raising=False)
    monkeypatch.setenv("WL_WORKFORCE_NO_CITY_ROSTER", "1")


@pytest.fixture(autouse=True)
def _refuse_host_databases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail before SQLite can touch a host store, even if a fixture loses its env."""
    import sqlite3
    import tempfile
    from pathlib import Path
    from urllib.parse import unquote, urlsplit
    connect = sqlite3.connect
    temporary_root = Path(tempfile.gettempdir()).resolve()

    def guarded(database, *args, **kwargs):
        value = str(database)
        if value not in ("", ":memory:") and not value.startswith("file::memory:"):
            path = unquote(urlsplit(value).path) if value.startswith("file:") else value
            resolved = Path(path).resolve()
            if temporary_root not in resolved.parents:
                raise RuntimeError("Test attempted to open a non-temporary SQLite database: " + str(resolved))
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)
