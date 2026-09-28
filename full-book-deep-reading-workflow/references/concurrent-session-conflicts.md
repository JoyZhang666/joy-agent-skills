# Concurrent sessions

Unexpected changes to manifest/state/index, differing runner IDs or duplicate notes indicate a possible second writer. Stop mutations and inspect project-local evidence. Do not assume a text RUNNER-CLAIM file locks the project.

Use the host's actual exclusive-lock facility or atomic exclusive file creation. Record a unique owner, timestamp and process/session identity; release only the lock you own. Do not remove a lock based solely on age or PID on a different host. If ownership cannot be verified, ask the user to select a writer and stay read-only.

Preserve conflicting notes. Offer a merged note derived from both with source verification, keeping originals outside the canonical active-note list. Do not automatically move/overwrite another session's work or claim remaining chapters when the user is unreachable. Once a single writer is confirmed, update canonical state and regenerate the index. Read timestamps from the host clock.
