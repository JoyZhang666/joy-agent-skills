#!/usr/bin/env python3
"""Generate a deterministic first-pass feedback analysis from normalized metrics.

The LLM/agent may enrich the output, but this script ensures every article gets a
baseline analysis artifact without inventing unavailable data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional


def rate(num: Optional[int], den: Optional[int]) -> Optional[float]:
    if type(num) not in (int, float) or type(den) not in (int, float) or num < 0 or den <= 0:
        return None
    return round(num / den, 4)


def fmt(v: Any) -> str:
    return "未知" if v is None else str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article-dir", required=True)
    args = ap.parse_args()
    d = Path(args.article_dir)
    metrics_file = d / "feedback" / "metrics-normalized.json"
    if not metrics_file.exists():
        print(json.dumps({"status": "blocked", "blocker": "metrics_missing"}, ensure_ascii=False))
        return 2
    m: Dict[str, Any] = json.loads(metrics_file.read_text(encoding="utf-8"))
    read = m.get("read_count")
    share = m.get("share_count")
    fav = m.get("favorite_count")
    like = m.get("like_count")
    share_rate = rate(share, read)
    fav_rate = rate(fav, read)
    like_rate = rate(like, read)
    md = f"""# Feedback Analysis — {m.get('title') or m.get('article_id') or 'Untitled'}

## 数据来源

- Source: {m.get('raw_source')}
- Collected at: {m.get('collected_at')}
- Public URL: {m.get('public_url') or '未知'}

## 核心指标

| Metric | Value |
|---|---:|
| Read count | {fmt(read)} |
| Like count | {fmt(like)} |
| Share count | {fmt(share)} |
| Favorite count | {fmt(fav)} |
| Comment count | {fmt(m.get('comment_count'))} |
| Completion rate | {fmt(m.get('completion_rate'))} |
| Share rate | {fmt(share_rate)} |
| Favorite rate | {fmt(fav_rate)} |
| Like rate | {fmt(like_rate)} |

## 初步判断

- 选题表现：等待与历史均值/同主题均值对比；若样本不足，禁止过度归因。
- 标题与封面：优先观察 T+1h 阅读与分享；若阅读弱，下一轮优先调整外层包装。
- 内容价值：优先观察收藏率、完读率、评论质量；缺失字段保留未知，不猜测。
- 传播能力：优先观察分享率；若分享率低但收藏率高，适合二次分发或改标题再推。

## 下一步动作建议

1. 将本指标写入 `_system/content-ledger.json`。
2. 与 `topic-scoreboard.json` 中同类型文章对比。
3. 将有效标题模式写入 `headline-patterns.md`。
4. 将封面表现与用户反馈写入 `cover-memory.md`。
5. 将可复用经验写入 `feedback-memory.md`。
"""
    out = d / "feedback" / "analysis.md"
    if out.exists():
        print(json.dumps({"status": "blocked", "blocker": "analysis_exists_preserve_user_edits"}))
        return 2
    with out.open('x', encoding='utf-8') as f:
        f.write(md)
    print(json.dumps({"status": "ok", "analysis": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
