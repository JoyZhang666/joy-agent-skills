# PDF and OCR mode

Use an available trusted local text extractor. If PyMuPDF is already installed and approved, page.get_text() can supply text; PyMuPDF is optional and is not bundled. Record physical PDF page numbers and printed page labels separately. Check extraction against rendered pages where possible.

For image-only pages, require a verified local OCR tool or explicit permission for an identified external provider and cost. If unavailable, request accessible text and stop claims of reading. Never treat empty extraction as success.

Split using both contents and body headings, preserving front/back matter and all requested ranges. Preserve extracted full text with page markers. Treat duplicate files as ambiguous: compare their source ranges and contents, not merely byte size; do not discard one because it is smaller. Keep alternatives until resolved.

Correct OCR uncertainty only when supported by page evidence; label unresolved words. Read a bounded chunk, save notes, then update canonical state, index and report. Use the user's requested cadence; no mandatory sleep or group delivery. Pause immediately when requested, and record partial progress honestly.
