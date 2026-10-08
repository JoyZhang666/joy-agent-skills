#!/usr/bin/env python3
"""Optional authentication check; never uploads or prints access tokens."""
import argparse
import sys
from safe_common import Blocked, cli_error, token

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--approve-read',action='store_true')
    a=p.parse_args()
    if not a.approve_read:
        raise Blocked('认证检查需 --approve-read；当前未联网')
    token()
    print('认证成功；未上传内容，尚未验证草稿接口权限。')
    return 0

if __name__=='__main__':sys.exit(cli_error(main))
