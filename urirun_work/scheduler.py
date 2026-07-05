# Author: Tom Sapletta · Part of the ifURI solution.
"""Scheduler — koru is the executor; THIS decides what runs in parallel.

koru itself is one queue loop (FIFO). Parallelism comes from spawning several koru workers
against tickets whose locks DO NOT intersect, respecting per-lane worker caps. This module
computes the parallel-ready set (the answer to "can koru do parallel work?") — a ticket is
ready iff its dependencies are done, it needs no human, and its locks don't collide with a
running or already-selected ticket.
"""
from __future__ import annotations

from typing import Any

from . import locks as _locks

_PRIORITY = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def _held(running: list[dict]) -> set[str]:
    held: set[str] = set()
    for t in running:
        held |= _locks.locks_for(t)
    return held


def _deps_done(ticket: dict, done_ids: set[str]) -> bool:
    for req in ticket.get("requires") or []:
        s = str(req)
        if s.startswith("ticket:") and s[7:] not in done_ids:
            return False
    return True


def parallel_ready(tickets: list[dict], running: list[dict] | None = None,
                   *, max_workers: int = 6, done_ids: set[str] | None = None) -> dict[str, Any]:
    """Select tickets that can start NOW in parallel — non-conflicting locks, deps done,
    no human needed, under the global + per-lane worker caps."""
    running = running or []
    done_ids = done_ids or {t.get("id") for t in tickets if t.get("status") == "done"}
    held = _held(running)
    lane_running: dict[str, int] = {}
    for t in running:
        lane_running[_locks.lane_of(t)] = lane_running.get(_locks.lane_of(t), 0) + 1

    candidates = [t for t in tickets if t.get("status") in ("open", None)
                  and not _locks.needs_human(t) and _deps_done(t, done_ids)]
    candidates.sort(key=lambda t: _PRIORITY.get(t.get("priority"), 2))

    selected: list[dict] = []
    sel_locks = set(held)
    lane_count = dict(lane_running)
    for t in candidates:
        if len(selected) >= max_workers:
            break
        lane = _locks.lane_of(t)
        cap = _locks.LANE_MAX_WORKERS.get(lane, 2)
        if lane_count.get(lane, 0) >= cap:
            continue
        tl = _locks.locks_for(t)
        if tl & sel_locks:
            continue
        selected.append({"id": t.get("id"), "name": t.get("name"), "lane": lane,
                         "priority": t.get("priority"), "locks": sorted(tl)})
        sel_locks |= tl
        lane_count[lane] = lane_count.get(lane, 0) + 1

    blocked = []
    for t in candidates:
        if any(s["id"] == t.get("id") for s in selected):
            continue
        reason = "lock conflict" if (_locks.locks_for(t) & sel_locks) else "lane at capacity"
        blocked.append({"id": t.get("id"), "lane": _locks.lane_of(t), "reason": reason})
    human = [{"id": t.get("id"), "reason": "needs human/secret"} for t in tickets
             if t.get("status") in ("open", "waiting_input") and _locks.needs_human(t)]

    return {"ready": selected, "blocked_by_lock": blocked, "waiting_human": human,
            "max_workers": max_workers, "running": len(running)}


def lanes_view(tickets: list[dict], running: list[dict] | None = None) -> list[dict]:
    """The /work lanes table: per-lane workers/running/queue — many lanes, not one FIFO."""
    running = running or []
    by_lane: dict[str, dict] = {}
    for t in tickets:
        lane = _locks.lane_of(t)
        d = by_lane.setdefault(lane, {"lane": lane, "cap": _locks.LANE_MAX_WORKERS.get(lane, 2),
                                      "running": [], "queue": []})
        (d["running"] if t.get("status") in ("in_progress", "claimed") else d["queue"]).append(t.get("id"))
    for t in running:
        by_lane.setdefault(_locks.lane_of(t), {"lane": _locks.lane_of(t), "running": [], "queue": []})
    return sorted(by_lane.values(), key=lambda d: d["lane"])
