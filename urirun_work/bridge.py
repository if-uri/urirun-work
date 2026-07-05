# Author: Tom Sapletta · Part of the ifURI solution.
"""Headless koru↔Claude bridge — the PROPER integration that GUI injection is not.

koru's autopilot drives an IDE by clicking/typing into its window (vdisplay GUI injection):
fragile, needs a focused calibrated window, and it escalates to a human when the drive
fails. But Claude Code has a robust non-interactive mode — ``claude -p "<prompt>"``. This
bridge runs a queue ticket THROUGH that headless mode and marks it done/failed from the
result, so continuous work does not depend on a screen being driven. Runners are injectable
so the loop is testable without spending real agent calls.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Callable

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def _run(argv: list[str], timeout: float = 900.0) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)  # noqa: S603


def _claude_bin() -> str | None:
    return shutil.which("claude") or (os.path.expanduser("~/.local/bin/claude")
                                      if os.path.isfile(os.path.expanduser("~/.local/bin/claude")) else None)


def _planfile_bin() -> str | None:
    b = shutil.which("planfile")
    if b:
        return b
    for c in ("~/github/if-uri/venv/bin/planfile",):
        p = os.path.expanduser(c)
        if os.path.isfile(p):
            return p
    return None


def ticket_prompt(ticket: dict) -> str:
    """Turn a ticket into a self-contained Claude Code instruction (headless, agentic)."""
    return (f"You are koru's autonomous worker. Complete this ticket end-to-end, then stop.\n"
            f"Ticket {ticket.get('id')}: {ticket.get('name')}\n"
            f"{ticket.get('description', '')}\n\n"
            f"Do the actual work (write code/files, run tests). When done, reply with a one-line "
            f"summary starting with DONE: or, if you are blocked on human input, BLOCKED: <what>.")


def run_ticket(ticket: dict, *, project: str, runner: Runner = _run,
               claude_bin: str | None = None) -> dict[str, Any]:
    """Execute one ticket via headless ``claude -p`` in the project dir. Robust: no GUI, no
    window, no vdisplay. Returns {ok, status, summary} parsed from the reply."""
    binp = claude_bin or _claude_bin()
    if not binp:
        return {"ok": False, "error": "claude CLI not found"}
    try:
        cp = runner([binp, "-p", ticket_prompt(ticket)])
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "ticket": ticket.get("id")}
    out = (cp.stdout or "").strip()
    last = out.splitlines()[-1] if out else ""
    if cp.returncode == 0 and "DONE:" in out:
        status = "done"
    elif "BLOCKED:" in out:
        status = "waiting_input"
    else:
        status = "failed"
    return {"ok": status == "done", "ticket": ticket.get("id"), "status": status,
            "summary": last[:300], "returncode": cp.returncode}


def mark_ticket(ticket_id: str, status: str, note: str, *, project: str,
                runner: Runner = _run) -> bool:
    """Reflect the headless result back into the planfile queue (done | input | fail)."""
    pf = _planfile_bin()
    if not pf:
        return False
    verb = {"done": "done", "waiting_input": "input", "failed": "fail"}.get(status, "input")
    args = [pf, "ticket", verb, ticket_id]
    if verb == "input":
        args += ["--prompt", note[:200]]
    elif verb == "fail":
        args += ["--error", note[:200]]
    try:
        return runner(args).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def process_ticket(ticket: dict, *, project: str, runner: Runner = _run) -> dict[str, Any]:
    """Run a ticket headless AND record the outcome in the queue — the full unit of work."""
    res = run_ticket(ticket, project=project, runner=runner)
    if res.get("status"):
        mark_ticket(str(ticket.get("id")), res["status"],
                    res.get("summary") or res.get("error", ""), project=project, runner=runner)
    return res
