# Author: Tom Sapletta · Part of the ifURI solution.
"""Locks — what a ticket touches, so the scheduler knows what can run in parallel.

Parallelism is not many agents writing the same place — it is many independent lanes with
EXPLICITLY declared locks. A ticket's locks come from its explicit ``locks`` field, else
are derived: a repo lock (different repos → parallel), a lane/path scope, a node lock
(mutating the same node → serial), a human/secret lock (needs a person). Two tickets
conflict iff their lock sets intersect.
"""
from __future__ import annotations

from typing import Any

# lane → default lock scope. 'repo' = whole repo serialized; 'path' = per-file; 'node' = per-node
LANE_SCOPE = {
    "connector-gen": "repo", "urirun-core": "repo", "fleet": "path", "mind": "path",
    "dashboard": "frontend", "node-maintenance": "node", "docs": "path", "inquiry": "path",
}
LANE_MAX_WORKERS = {
    "connector-gen": 4, "urirun-core": 1, "fleet": 2, "mind": 2,
    "dashboard": 1, "node-maintenance": 1, "docs": 4, "inquiry": 2,
}


def _labels(ticket: dict) -> list[str]:
    lb = ticket.get("labels") or ticket.get("label") or []
    return lb if isinstance(lb, list) else [lb]


def lane_of(ticket: dict) -> str:
    for lb in _labels(ticket):
        s = str(lb)
        if s in LANE_SCOPE:
            return s
        if s.startswith("lane:") and s[5:] in LANE_SCOPE:
            return s[5:]
    # heuristic from the id/name
    name = (str(ticket.get("name", "")) + " " + str(ticket.get("id", ""))).lower()
    for lane in LANE_SCOPE:
        if lane.replace("-", "") in name.replace("-", "").replace(" ", ""):
            return lane
    if "connector" in name or "generate" in name:
        return "connector-gen"
    if "dashboard" in name or "/work" in name:
        return "dashboard"
    if "fleet" in name:
        return "fleet"
    return "docs"


def locks_for(ticket: dict) -> set[str]:
    """The lock set a ticket holds. Explicit ``locks`` win; otherwise derive from lane/repo/node."""
    explicit = ticket.get("locks")
    if explicit:
        return set(explicit if isinstance(explicit, list) else [explicit])
    locks: set[str] = set()
    lane = lane_of(ticket)
    repo = ticket.get("repo")
    if repo:
        locks.add(f"repo:{repo}")
    else:
        # a connector-gen ticket for a NEW connector locks only its own future repo (parallel-safe)
        name = str(ticket.get("name", "")).lower()
        scheme = _scheme_from(name)
        if lane == "connector-gen" and scheme:
            locks.add(f"repo:if-uri/urirun-connector-{scheme}")
        else:
            locks.add(f"lane:{lane}")   # fall back to serializing the whole lane
    if LANE_SCOPE.get(lane) == "node":
        locks.add("node:" + str(ticket.get("node") or "lenovo"))
    if ticket.get("status") == "waiting_input" or any("secret" in str(l) or "human" in str(l)
                                                      for l in _labels(ticket)):
        locks.add("human:input")
    return locks


def _scheme_from(name: str) -> str | None:
    import re
    m = re.search(r"generate\s+([a-z0-9-]+)://", name) or re.search(r"([a-z0-9-]+)://", name) \
        or re.search(r"generate\s+([a-z0-9-]+)\s+connector", name)
    return m.group(1) if m else None


def conflicts(a: dict, b: dict) -> bool:
    return bool(locks_for(a) & locks_for(b))


_HUMAN_HINTS = ("secret://", "imap", "app-password", "approval", "human:", "enrollment token",
                "credentials", "requires human", "human approval")


def needs_human(ticket: dict) -> bool:
    if "human:input" in locks_for(ticket) or ticket.get("status") == "waiting_input":
        return True
    hay = (str(ticket.get("name", "")) + " " + str(ticket.get("description", "")) + " "
           + " ".join(str(l) for l in _labels(ticket))).lower()
    return any(h in hay for h in _HUMAN_HINTS)
