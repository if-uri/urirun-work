# urirun-work

Parallel work scheduler for koru. **koru is the executor; this decides what runs in
parallel.** koru's own loop is one FIFO — this fixes that by spawning several koru workers
on tickets whose **resource hierarchies don't overlap**, respecting per-lane caps.

Rule: parallelism = independent lanes with declared locks, not many agents in one place.
Different repos → parallel. Same repo/file/node → serial. Secret/approval → waits for a human.

| module | role |
|---|---|
| `locks` | shared hierarchical lock contract (repo/path/lane/node/human); repo locks shadow descendant paths, siblings run in parallel |
| `scheduler` | `parallel_ready(tickets)` → the set that can start NOW; `lanes_view` for the panel |
| `workers` | spawn one koru worker per ready ticket, distinct id + worktree |

The lock contract is also consumed by `urirun-connector-work`; the connector adds durable
leases and the `work://` URI control plane without maintaining a second conflict algorithm.

`urirun-work ready|lanes|run --project . --max-workers 6`. Part of the ifURI solution · Apache-2.0
