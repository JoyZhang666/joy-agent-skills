# EPUB ingestion

Read only the user-selected EPUB. It is a ZIP container: enumerate first and bound member count, total size and compression ratio. Reject encrypted items, absolute/traversal paths and links; do not blindly extractall. Read container.xml, OPF and spine with standard-library XML parsing. Resolve hrefs relative to the OPF within the archive, allowing safe parent normalization only when the resulting member remains inside the archive. Ignore external URLs, never fetch them automatically. Reject XML DOCTYPE/entity declarations for this ingestion path.

Use XML attributes rather than position-dependent regex. Preserve spine order and an HTMLParser-based text extraction including paragraph and heading boundaries. Preserve meaningful front matter; mark decorative/empty sections explicitly rather than silently discarding them. Keep extracted full text and source mapping in the project. Check start, middle, end and total coverage; missing members or unreadable markup block completeness claims.

Extraction code is host-generated project tooling, not supplied here; keep it in project tools/ and inspect before running. If no extraction tool is available, request user-provided plain text. Do not claim standard-library ingestion is already implemented by the six bundled helpers.

For repeated running headers, optional retake_spine_titles.py accepts a pre-reading legacy manifest with book and sections ({section_id,title,file,char_count}); only chapters/ regular files are allowed. Run once before notes/state exist. It preserves all file text, preflights the complete rename plan, refuses target collisions and records manifest backup. Afterward create the canonical chunks manifest as specified in durable-continuity-protocol.md. For fragmented spine pages, define logical chunks with explicit ordered member ranges and verify every meaningful source range appears exactly once.

Approval refusals, missing permissions and inaccessible sources must use the host's authorization flow. Never change command form to evade an approval gate. Complete one verified chunk before any separately authorized schedule.
