#!/usr/bin/env python3
"""Deprecated entry: use scripts/draft_sync_guarded.py with explicit consent."""
import sys
def main():
    print('旧入口已停用。请使用 scripts/draft_sync_guarded.py：pull/snapshot 需 --approve-read；update 默认仅本地检查，上传需 --approve-upload。')
    return 2
if __name__=='__main__':sys.exit(main())
