# Recover reading

Read only this project's manifest, state, last report, notes and approved job status. Validate schema 2.0 before writing. If old fields exist, follow existing-project-continuity-retrofit.md. A paused project resumes only on user instruction. A completed project is reported as complete, never restarted by an automated tick.

Find the first pending ID in manifest order. Reconcile notes from interrupted writes: inspect the source and note, either finish that chunk or leave pending with reason. Persist note, state, index and log in that order. Verify updated artifacts before reporting recovered progress.

If no approved scheduler exists, continue in-session within scope. Do not create a new scheduler merely because a previous session stopped. If auto-continuation is explicitly approved, inspect the real host interface and create/reuse one bounded job only after a proof chunk. Stop at completed or paused; do not schedule recursively. Failed notifications do not roll back completed reading. Verify whether delivery already occurred before retrying external sends.
