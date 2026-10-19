"""Report only the dependencies required by the selected optional capability."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability", choices=["aggregate", "pdf"], default="aggregate")
    parser.add_argument("--browser-path", type=Path)
    args = parser.parse_args()
    checks = {"python_3_10_or_later": sys.version_info >= (3, 10)}
    if args.capability == "pdf":
        checks.update({name: importlib.util.find_spec(name) is not None for name in ("markdown", "playwright")})
        edge = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe"
        checks["browser_file"] = (args.browser_path or edge).is_file()
    print(json.dumps({"capability": args.capability, "checks": checks,
                      "status": "ready" if all(checks.values()) else "missing_dependency",
                      "scope": "availability_only_not_render_or_research_acceptance"}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
