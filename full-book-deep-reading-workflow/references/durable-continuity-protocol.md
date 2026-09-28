# Durable state (schema 2.0)

Use exactly one canonical state at state/progress.json. All paths below are project-relative POSIX paths; only regular files inside the project are allowed. Never evaluate path content as code.

manifest.json:
```json
{"schema_version":"2.0","chunks":[{"id":"001","file":"chapters/001.md","title":"Example chapter"}]}
```
state/progress.json:
```json
{"schema_version":"2.0","status":"running","completed_chunks":[],"next_chunk":"001","failed_chunks":[],"synthesis":null}
```
A completed entry is `{"id":"001","note":"notes/chapters/001_notes.md"}`. Status is only `running`, `paused`, or `completed`. The manifest is ordered, IDs unique and non-empty. next_chunk is the first ID not in completed_chunks, or null when none remain. Completed IDs must be a prefix of manifest order; missing or unreadable notes invalidate completion. A completed state requires all entries, no failed_chunks, and synthesis pointing to a nonempty local synthesis file. A paused state may retain next_chunk for manual recovery; it must not trigger autonomous work.

Save notes first. Replace state atomically using a temporary file in state/ and os.replace; clean up only your own temporary file. Rebuild the index from that state, append run-log.jsonl (chunk ID, timestamp, outcome), then save last-report.md. No multi-file operation is globally atomic: after interruption reconcile disk artifacts before continuing. A leftover note is not proof of completed reading by itself.

Use an exclusive lock with a unique owner when automation exists; check ownership before removing it. A text claim alone does not provide mutual exclusion. Stop on another active writer. Keep retry-queue.jsonl for failures, with at most two retries per chunk unless the user requests otherwise.

Scheduling is an optional host adapter: inspect the available tool schema and current official documentation. Require explicit scheduling approval, one verified chunk, one bounded next chunk per run, no recursive schedule creation, and a verified stop condition. Do not assume a cron dialect, repeat parameter or silent-response token transfers across hosts. At entry, exit for paused/completed; do not create another job. Do not promise continuation while the host is offline.
