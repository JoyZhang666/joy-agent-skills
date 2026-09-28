"""Generate a project index or audit a workspace. Python 3.10+, standard library only."""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path, PureWindowsPath

MARKER = "<!-- generated-by: project-file-management/workspace_admin.py v1 -->"
STATES = {"active": "进行中", "paused": "暂停 / 待继续", "completed": "已完成", "archived": "已归档"}
REQUIRED = {"id", "title", "lifecycle", "stage_paths", "latest_release", "artifacts", "updated"}


def inside(root, value):
    """Resolve a portable workspace-relative path, rejecting traversal and symlink escapes."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("路径必须为非空字符串，使用 / 分隔")
    if Path(value).is_absolute() or PureWindowsPath(value).drive or ".." in value.split("/"):
        raise ValueError("禁止绝对路径、盘符及 ..")
    target = (root / value).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError("路径越出工作区或指向根目录")
    return target


def cell(value):
    # Titles are text, never Markdown supplied by a registry.
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("[", "&#91;").replace("]", "&#93;").replace("\n", " ").replace("\r", " ").replace("*", "&#42;").replace("`", "&#96;")


def render(records):
    from urllib.parse import quote
    lines = ["# 项目总索引", "", MARKER, "", "由项目登记生成；请修改 project.json 后重新生成，不手工维护本表。", "",
             "| 项目 | 状态 | 最新正式版 |", "|---|---|---|"]
    for item in sorted(records, key=lambda p: p["id"]):
        entry = quote(item["stage_paths"]["01_projects"].rstrip("/") + "/README.md", safe="/")
        release = item["latest_release"]
        output = f"[读取版本]({quote(release.rstrip('/') + '/', safe='/')})" if release else "尚无已确认正式版；见项目入口"
        lines.append(f"| {cell(item['title'])} · [进入项目]({entry}) | {STATES[item['lifecycle']]} | {output} |")
    return "\n".join(lines) + "\n"


def inspect(root):
    errors, records, seen = [], [], set()
    for name in ("AGENTS.md", "README.md"):
        if not (root / name).is_file():
            errors.append(f"缺少工作区入口：{name}")
    registry = root / "01_projects"
    if not registry.is_dir():
        errors.append("缺少登记目录：01_projects")
    elif not registry.resolve().is_relative_to(root):
        errors.append("登记目录越出工作区")
        return records, errors
    for source in sorted(registry.glob("*/project.json")):
        label = source.relative_to(root).as_posix()
        before = len(errors)
        try:
            inside(root, label)
            item = json.loads(source.read_text(encoding="utf-8-sig"))
            if not isinstance(item, dict) or not REQUIRED <= item.keys():
                raise ValueError("登记必须为对象，且包含全部必填字段")
            pid = item["id"]
            if not isinstance(pid, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", pid):
                raise ValueError("id 只允许小写英文、数字和单个连接短横线")
            if pid in seen:
                errors.append(f"{label}: 重复编号 {pid}")
            seen.add(pid)
            if source.parent.name != pid:
                errors.append(f"{label}: 登记目录名与 id 不一致")
            if not isinstance(item["title"], str) or not item["title"].strip():
                raise ValueError("title 必须为非空字符串")
            if not isinstance(item["lifecycle"], str) or item["lifecycle"] not in STATES:
                raise ValueError("lifecycle 无效")
            if not isinstance(item["updated"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["updated"]):
                raise ValueError("updated 必须为 YYYY-MM-DD")
            date.fromisoformat(item["updated"])
            stages = item["stage_paths"]
            if not isinstance(stages, dict) or "01_projects" not in stages:
                raise ValueError("stage_paths 必须包含 01_projects")
            if stages["01_projects"] != source.parent.relative_to(root).as_posix():
                raise ValueError("01_projects 必须指向当前登记所在目录")
            for stage, relative in stages.items():
                if not inside(root, relative).is_dir():
                    errors.append(f"{label}: 登记目录不存在：{stage}")
            for name in ("README.md", "STATUS.md", "CHANGELOG.md"):
                relative = source.parent.relative_to(root).as_posix() + "/" + name
                if not inside(root, relative).is_file():
                    errors.append(f"{label}: 缺少项目文件 {name}")
            release = item["latest_release"]
            if release is not None:
                if not inside(root, release).is_dir():
                    errors.append(f"{label}: 正式版入口不存在")
            if not isinstance(item["artifacts"], list):
                raise ValueError("artifacts 必须为相对路径字符串数组")
            for artifact in item["artifacts"]:
                if not inside(root, artifact).is_file():
                    errors.append(f"{label}: 成果文件不存在")
            if len(errors) == before:
                records.append(item)
        except (ValueError, TypeError, OSError) as exc:
            errors.append(f"{label}: {exc}")
    # Catch an incomplete project hub which would otherwise silently disappear from the index.
    if registry.is_dir():
        for hub in sorted(registry.iterdir()):
            if hub.is_dir() and not (hub / "project.json").is_file():
                errors.append(f"01_projects/{hub.name}: 缺少 project.json")
    return records, errors


def run(action, root):
    if not root.is_dir():
        return {"passed": False, "projects": 0, "errors": ["工作区根目录不存在"]}
    records, errors = inspect(root)
    target = root / "PROJECTS.md"
    expected = render(records) if not errors else None
    existing = None
    try:
        inside(root, "PROJECTS.md")
        if target.is_symlink():
            raise ValueError("PROJECTS.md 不允许为符号链接")
        if target.exists():
            existing = target.read_text(encoding="utf-8-sig")
        if existing is not None and not existing.startswith("# 项目总索引\n\n" + MARKER + "\n"):
            errors.append("既有 PROJECTS.md 不是本工具生成：保留原件，先评估并确认接入方案")
        if action == "audit":
            if existing is None:
                errors.append("缺少 PROJECTS.md")
            elif expected is not None and existing != expected:
                errors.append("PROJECTS.md 与当前登记不一致，请重新生成")
        elif not errors and existing != expected:
            # All registries and output ownership are validated before any write.
            target.write_text(expected, encoding="utf-8", newline="\n")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    return {"passed": not errors, "projects": len(records), "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("index", "audit"))
    parser.add_argument("--root", required=True, type=Path, help="明确指定工作区根目录")
    args = parser.parse_args()
    try:
        result = run(args.action, args.root.resolve())
    except (OSError, ValueError) as exc:
        result = {"passed": False, "projects": 0, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
