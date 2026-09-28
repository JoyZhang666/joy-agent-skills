#!/usr/bin/env python3
"""Package a fixed allowlist to a NEW ZIP outside the source tree; not a privacy scan."""
import argparse
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

RELEASE_FILES = ('LICENSE', 'README.md', 'SKILL.md', 'references/auto-continuation-recovery.md', 'references/book-intake-and-library-layout.md', 'references/completion-and-one-pager.md', 'references/concurrent-session-conflicts.md', 'references/copyright-privacy-policy.md', 'references/durable-continuity-protocol.md', 'references/epub-stdlib-ingestion-and-continuation.md', 'references/example-project-structure.md', 'references/existing-project-continuity-retrofit.md', 'references/legacy-fiction-project-v12-retrofit.md', 'references/ocr-pdf-execution-mode.md', 'references/offline-document-tooling.md', 'references/skill-routing.md', 'references/verification-checklist.md', 'references/workflow-overview.md', 'scripts/build_reading_index.py', 'scripts/create_reading_project.py', 'scripts/package_skill.py', 'scripts/retake_spine_titles.py', 'scripts/split_markdown_chapters.py', 'scripts/validate_reading_project.py', 'templates/chapter-note.md', 'templates/character-profile.md', 'templates/concept-map.md', 'templates/discussion-questions.md', 'templates/full-book-synthesis.md', 'templates/project-readme.md', 'templates/reading-contract.md', 'templates/reading-progress-report.md', 'templates/section-note.md', 'templates/theme-map.md')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('skill_dir');ap.add_argument('output_zip');args=ap.parse_args()
    raw=Path(args.skill_dir).expanduser();out=Path(args.output_zip).expanduser()
    for p in (raw,out):
        if any(x.is_symlink() or getattr(x,'is_junction',lambda:False)() for x in [p,*p.parents]):
            raise ValueError('Links/junctions are not allowed')
    root=raw.resolve()
    if out.resolve().is_relative_to(root): raise ValueError('ZIP must be outside the source tree')
    if out.exists(): raise ValueError('Output exists; choose a new path')
    payloads=[]
    for rel in RELEASE_FILES:
        p=root/rel
        if any(x.is_symlink() or getattr(x,'is_junction',lambda:False)() for x in [p,*p.parents]):
            raise ValueError('Links/junctions are not allowed')
        if not p.is_file(): raise ValueError('Missing allowlisted release file')
        payloads.append((root.name+'/'+rel,p.read_bytes()))
    owned=False
    try:
        with out.open('xb') as stream:
            owned=True
            with ZipFile(stream,'w',ZIP_DEFLATED) as z:
                for name,data in payloads: z.writestr(name,data)
    except Exception:
        if owned: out.unlink()
        raise
    print(out)
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError) as exc: raise SystemExit(str(exc))
