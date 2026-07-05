# Author: Tom Sapletta · Part of the ifURI solution.
"""urirun-work — koru is the executor; this decides parallelism. Independent lanes with
declared locks run together; same repo/file/node serialize; humans wait. Fixes koru's
single-FIFO-loop limit by spawning multiple workers on non-conflicting tickets."""
from . import bridge, locks, scheduler, workers
__all__ = ["bridge", "locks", "scheduler", "workers"]
