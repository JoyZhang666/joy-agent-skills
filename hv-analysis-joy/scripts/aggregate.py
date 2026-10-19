"""Aggregate research files; preserve inputs and never assert factual verification.

SPDX-License-Identifier: MIT
Copyright (c) 2026 JoyZhang666
"""
import argparse
import csv
import json
from pathlib import Path
import re


def text(value):
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def csv_cell(value):
    if isinstance(value, str) and re.match(r"^\s*[=+@-]", value):
        return "'" + value
    return text(value)


def normalize_sq(data, stem):
    if not isinstance(data, dict) or not isinstance(data.get("data_points"), list):
        raise ValueError(f"{stem}: expected object with data_points array")
    summary = text(data.get("summary"))
    dps, seen = [], set()
    for index, raw in enumerate(data["data_points"], 1):
        if isinstance(raw, str):
            item = {"id": f"legacy-{index}", "field": "legacy_text", "value": raw,
                    "evidence_status": "unreviewed"}
        elif isinstance(raw, dict):
            item = dict(raw)
            if not isinstance(item.get("id"), str) or not item["id"].strip():
                raise ValueError(f"{stem}: data point {index} needs a string id")
            item.setdefault("field", item.get("fact") or item.get("category", ""))
            item.setdefault("evidence_status", "unreviewed")
            if "confidence" in item:
                item.setdefault("reported_confidence", item["confidence"])
        else:
            raise ValueError(f"{stem}: invalid data point type at {index}")
        if item["id"] in seen:
            raise ValueError(f"{stem}: duplicate data point id")
        seen.add(item["id"])
        dps.append(item)
    sq_id = data.get("sq_id")
    if sq_id is None:
        inferred = {m.group(1) for item in dps
                    if (m := re.match(r"^(SQ\d+)-D\d+\.\d+$", item["id"]))}
        sq_id = inferred.pop() if len(inferred) == 1 else stem.upper()
    if not isinstance(sq_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", sq_id):
        raise ValueError(f"{stem}: invalid sq_id")
    sources = data.get("sources", [])
    if not isinstance(sources, list) or any(not isinstance(s, (str, dict)) for s in sources):
        raise ValueError(f"{stem}: sources must contain strings or objects")
    return {"sq_id": sq_id, "topic": data.get("topic", data.get("research_subject", "")),
            "summary": summary, "data_points": dps, "sources": sources}


def aggregate(input_dir, output_dir, expected_sq):
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError("Output directory exists; choose a new run directory")
    if not expected_sq or len(expected_sq) != len(set(expected_sq)):
        raise ValueError("Expected SQ IDs must be a nonempty unique list")
    files = sorted(input_dir.glob("sq*.json"))
    if not files:
        raise ValueError("No sq*.json input files found")
    raw_sq, normalized = {}, {}
    for path in files:
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Input links/reparse points are not supported")
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("SQ file exceeds 2 MiB limit")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        sq = normalize_sq(data, path.stem)
        if sq["sq_id"] in normalized:
            raise ValueError("Duplicate SQ ID across input files")
        raw_sq[path.name], normalized[sq["sq_id"]] = data, sq
    missing = sorted(set(expected_sq) - {k for k, v in normalized.items() if v["data_points"]})
    unexpected = sorted(set(normalized) - set(expected_sq))
    urls, origins = set(), set()
    for sq in normalized.values():
        for source in sq["sources"]:
            url = source.get("url", "") if isinstance(source, dict) else source
            origin = source.get("origin_id", "") if isinstance(source, dict) else ""
            if isinstance(url, str) and url:
                urls.add(url)
            if isinstance(origin, str) and origin:
                origins.add(origin)
    status = "partial" if missing else "complete"
    result = {"technical_status": status, "fact_verification": "not_performed",
              "expected_sq": expected_sq, "missing_sq": missing, "unplanned_sq": unexpected,
              "distinct_source_urls": len(urls), "declared_origin_count": len(origins),
              "source_independence": "not_verified", "raw_sq_data": raw_sq, "sq_files": normalized}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "aggregation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["SQ", "DP_ID", "Entity", "As_of", "Field", "Value", "Period", "Unit", "Scope",
               "Relationship", "Source_URL", "Source_locator", "Evidence_status", "Reported_confidence"]
    keys = ["id", "entity", "as_of", "field", "value", "period", "unit", "scope", "relationship",
            "source_url", "source_locator", "evidence_status", "reported_confidence"]
    with (output_dir / "data.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for sq_id, sq in normalized.items():
            for dp in sq["data_points"]:
                writer.writerow([csv_cell(sq_id)] + [csv_cell(dp.get(k)) for k in keys])
    (output_dir / "status.md").write_text(
        "# 数据汇总技术检查\n\n"
        f"- technical_status: {status}\n- fact_verification: not_performed\n"
        f"- missing_sq: {', '.join(missing) or 'none'}\n"
        f"- unplanned_sq: {', '.join(unexpected) or 'none'}\n"
        f"- distinct_source_urls: {len(urls)}\n- declared_origin_count: {len(origins)}\n\n"
        "URL 和 origin 数量来自输入声明，未验证来源独立性；原始数据完整保存在 aggregation.json。\n",
        encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-sq", required=True, nargs="+")
    args = parser.parse_args()
    try:
        result = aggregate(args.input_dir, args.output_dir, args.expected_sq)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Aggregation failed: {type(exc).__name__}; check inputs and choose a new output directory.\n")
    print(json.dumps({k: result[k] for k in ("technical_status", "fact_verification", "missing_sq")}, ensure_ascii=False))
    return 2 if result["missing_sq"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
