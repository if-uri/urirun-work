# Author: Tom Sapletta · Part of the ifURI solution.
"""urirun-work CLI: ready / lanes / run (spawn koru workers) over the planfile queue."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess
from pathlib import Path
from . import scheduler, workers


def _planfile():
    b = shutil.which("planfile")
    if b: return b
    for c in ("~/github/if-uri/venv/bin/planfile", "~/github/semcod/koru/.venv/bin/planfile"):
        p = Path(c).expanduser()
        if p.is_file(): return str(p)
    return None


def _tickets(project):
    pf = _planfile()
    if not pf: return []
    cp = subprocess.run([pf, "ticket", "list", "--format", "json"], capture_output=True, text=True, cwd=project, timeout=15)
    raw = cp.stdout
    try:
        return json.loads(raw[raw.index("["):raw.rindex("]")+1]) if "[" in raw else json.loads(raw).get("tickets", [])
    except Exception:
        return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="urirun-work")
    ap.add_argument("cmd", choices=["ready", "lanes", "run"])
    ap.add_argument("--project", default=os.path.expanduser("~/github/if-uri"))
    ap.add_argument("--max-workers", type=int, default=6)
    a = ap.parse_args(argv)
    tickets = _tickets(a.project)
    if a.cmd == "lanes":
        print(json.dumps(scheduler.lanes_view(tickets), indent=1)); return 0
    r = scheduler.parallel_ready(tickets, max_workers=a.max_workers)
    if a.cmd == "ready":
        print(json.dumps(r, indent=1)); return 0
    if a.cmd == "run":
        spawned = workers.spawn(r["ready"], project=a.project)
        print(json.dumps({"spawned": spawned, "waiting_human": r["waiting_human"]}, indent=1, default=str)); return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
