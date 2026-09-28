# Example Reading Project Structure

Use a safe child folder inside the original folder containing the source book document.

If the source document is:

```text
/path/to/book-folder/book.epub
```

create:

```text
/path/to/book-folder/reading-project/
├── PROJECT.md
├── source/
│   ├── original.<ext>
│   └── extracted.md
├── chapters/
│   ├── 001.md
│   ├── 002.md
│   └── ...
├── notes/
│   ├── chapters/
│   │   ├── 001_notes.md
│   │   └── ...
│   ├── characters/
│   ├── concepts/
│   ├── themes/
│   └── full_book_synthesis.md
├── discussions/
│   └── YYYY-MM-DD_topic.md
├── state/
│   └── progress.json
└── MASTER_INDEX.md
```

## Naming Rules

- Use zero-padded numbers for chapter files when possible.
- Keep source text or extracted text under `source/`.
- Keep generated notes under `notes/`.
- Keep later user discussion insights under `discussions/`.
- Keep local progress/database/state under `state/`.
- Do not overwrite source files.
