# Author: Tom Sapletta · Part of the ifURI solution.
"""Parallelism = independent lanes with declared locks, not many agents in one place.
Non-conflicting tickets run together; same-repo/file/node serialize; humans wait."""
from urirun_work import locks, scheduler, workers


def _t(tid, name, status="open", priority="normal", **kw):
    return {"id": tid, "name": name, "status": status, "priority": priority, **kw}


# --- locks: what a ticket touches ---
def test_new_connectors_lock_only_their_own_repo():
    a = _t("A", "Generate youtube:// connector", labels=["connector-gen"])
    b = _t("B", "Generate calendar:// connector", labels=["connector-gen"])
    assert locks.locks_for(a) == {"repo:if-uri/urirun-connector-youtube"}
    assert not locks.conflicts(a, b)          # different repos → parallel


def test_same_file_serializes():
    a = _t("A", "fleet exec", repo="if-uri/urirun-fleet", locks=["module:urirun_fleet.executor"])
    b = _t("B", "fleet other", repo="if-uri/urirun-fleet", locks=["module:urirun_fleet.executor"])
    assert locks.conflicts(a, b)              # same module → serial


def test_node_maintenance_locks_the_node():
    a = _t("A", "Reinstall lenovo node", labels=["node-maintenance"], node="lenovo")
    assert "node:lenovo" in locks.locks_for(a)


def test_secret_ticket_needs_human():
    a = _t("A", "run email spam", status="waiting_input", labels=["email-test"])
    assert locks.needs_human(a)


# --- scheduler: parallel-ready selection ---
def test_parallel_ready_picks_nonconflicting_across_lanes():
    tickets = [
        _t("Y", "Generate youtube:// connector", labels=["connector-gen"], priority="high"),
        _t("C", "Generate calendar:// connector", labels=["connector-gen"]),
        _t("F", "fleet execute mode", repo="if-uri/urirun-fleet", labels=["fleet"]),
        _t("D", "dashboard /work panel", labels=["dashboard"]),
        _t("L", "Reinstall lenovo node", labels=["node-maintenance"], status="waiting_input"),
    ]
    r = scheduler.parallel_ready(tickets, max_workers=6)
    ids = {s["id"] for s in r["ready"]}
    assert {"Y", "C", "F", "D"} <= ids        # 4 independent lanes run together
    assert "L" not in ids                     # lenovo waits (human)
    assert any(h["id"] == "L" for h in r["waiting_human"])


def test_lane_capacity_caps_workers():
    # 6 connector-gen tickets, lane cap 4 → only 4 selected (distinct repos)
    tickets = [_t(f"C{i}", f"Generate scheme{i}:// connector", labels=["connector-gen"]) for i in range(6)]
    r = scheduler.parallel_ready(tickets, max_workers=10)
    assert len([s for s in r["ready"] if s["lane"] == "connector-gen"]) == 4


def test_running_locks_block_conflicting():
    running = [_t("R", "fleet exec", repo="if-uri/urirun-fleet")]
    tickets = [_t("F2", "fleet more", repo="if-uri/urirun-fleet")]
    r = scheduler.parallel_ready(tickets, running=running)
    assert r["ready"] == [] and r["blocked_by_lock"]   # same repo already held


def test_lanes_view_groups_by_lane():
    tickets = [_t("Y", "Generate youtube:// connector", labels=["connector-gen"]),
               _t("F", "fleet x", repo="if-uri/urirun-fleet", labels=["fleet"], status="in_progress")]
    lv = {d["lane"]: d for d in scheduler.lanes_view(tickets)}
    assert "connector-gen" in lv and "fleet" in lv
    assert lv["fleet"]["running"] == ["F"]


# --- workers: spawn a koru per ready ticket ---
def test_spawn_launches_one_koru_per_ready_with_distinct_worktree():
    ready = [{"id": "Y", "lane": "connector-gen"}, {"id": "C", "lane": "connector-gen"},
             {"id": "F", "lane": "fleet"}]
    launched = []
    out = workers.spawn(ready, project="/p", spawn_fn=launched.append)
    assert len(out) == 3 and all(w["spawned"] for w in out)
    assert {w["worker"] for w in out} == {"koru-worker-connector-gen-1",
                                          "koru-worker-connector-gen-2", "koru-worker-fleet-1"}
    # each argv targets the ticket + a distinct worker id
    assert all("--worker" in a and "--ticket" in a for a in launched)
