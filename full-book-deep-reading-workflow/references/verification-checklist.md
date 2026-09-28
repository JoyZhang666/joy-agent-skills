# Verification

- Source and requested scope are explicit, accessible and unchanged.
- Extraction covers every requested range in order; front matter is retained.
- Manifest IDs are unique and stable; source mappings are inspectable.
- Schema 2.0 completed entries form an ordered prefix, with nonempty notes.
- Note claims and quotations have source evidence; facts and inference are separated.
- next_chunk points at the first pending ID; paused/completed states do not schedule reading.
- Full completion includes every requested chunk, no failures, and scope-labelled synthesis.
- Index is regenerated from state, with prior index preserved.
- Source, notes, logs and any private applications stay in the authorized project.
- External processing, delivery and scheduling have explicit current authorization.
- Stop and failure states are recorded; no unverified background promises.

Use validate_reading_project.py for structure, then manually inspect semantic coverage. Report actual checks and limitations; a successful exit code is not end-user acceptance.
