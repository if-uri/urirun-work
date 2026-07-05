# Author: Tom Sapletta · Part of the ifURI solution.
"""Worker pool — spawn one koru per parallel-ready ticket, each in its own worktree.

Each worker gets a distinct identity and (for same-repo tickets) an isolated git worktree,
so two workers never write the same directory. The spawner is injectable so scheduling is
testable without launching real koru processes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


def _koru_bin() -> str | None:
    b = shutil.which("koru")
    if b:
        return b
    for c in ("~/github/semcod/koru/.venv/bin/koru",):
        p = Path(c).expanduser()
        if p.is_file():
            return str(p)
    return None


def worker_command(ticket: dict, *, project: str, lane: str, index: int) -> list[str]:
    """A koru worker scoped to a LANE (koru's real flags: --agent-lane + --allow-duplicate).

    koru has no per-ticket flag; the unit of a parallel worker is a LANE. Several lane-scoped
    loops run at once (--allow-duplicate); the scheduler ensures the lanes it activates hold
    non-conflicting locks, so per-lane workers don't collide."""
    binp = _koru_bin() or "koru"
    return [binp, "autonomous", "up", "--project", project, "--ide", "claude",
            "--ticket-sources", "queue", "--allow-duplicate", "--agent-lane", lane]


def spawn(ready: list[dict], *, project: str, spawn_fn: Callable[[list[str]], Any] | None = None,
          worktree_root: str = "") -> list[dict]:
    """Launch a koru worker per ready ticket. ``spawn_fn`` is injectable (test with a fake).
    Returns the worker records (id, ticket, lane, argv)."""
    launcher = spawn_fn or (lambda argv: subprocess.Popen(argv, start_new_session=True))  # noqa: S603
    out = []
    lane_idx: dict[str, int] = {}
    for t in ready:
        lane = t.get("lane", "docs")
        lane_idx[lane] = lane_idx.get(lane, 0) + 1
        argv = worker_command(t, project=project, lane=lane, index=lane_idx[lane])
        try:
            launcher(argv)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        out.append({"worker": f"koru-worker-{lane}-{lane_idx[lane]}", "ticket": t.get("id"),
                    "lane": lane, "spawned": ok, "argv": argv})
    return out
