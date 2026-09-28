# Retrofit existing projects

Only inspect the selected project and its known source. Record current files and active writer/scheduler before changes. Preserve originals and do not start another job.

For legacy state (complete/completed, completed_units/completed_chunks/completed, next_unit/next_chunk/next_section_id), read the actual shape. Build an explicit ID-to-source-to-note map; never blindly rename keys. Preserve the old state as a backup. Translate to schema 2.0 only after validating unique ordered IDs, coverage and existing notes. Ambiguous units or missing source mappings require user clarification, not invented completion.

If the user requests relocation, copy before moving, verify hashes and keep the old project. Do not replace an existing destination without explicit approval. Update source references without exposing paths in public outputs.

Validate the canonical state, rebuild its derived index and inspect artifacts. Completed projects need no reading schedule. Incomplete projects resume only within the current contract; scheduling remains separately authorized. See durable-continuity-protocol.md for canonical schema.
