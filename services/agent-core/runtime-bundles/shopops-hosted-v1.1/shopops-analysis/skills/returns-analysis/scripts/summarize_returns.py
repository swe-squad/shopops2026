"""Standard-library report builder; input evidence is validated by the root first."""

import argparse
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

MAX_INPUT_BYTES = 32768
COUNT_KEYS = {"start_date", "end_date", "orders", "returns", "return_rate"}
METRIC_KEYS = COUNT_KEYS | {"sku", "timezone", "baseline", "change_percentage_points"}


def closed(value: object, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("invalid object")
    return value


def text(value: object, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip() or (maximum and len(value) > maximum):
        raise ValueError("invalid text")
    return value


def numeric(value: object, expected: float | None) -> None:
    if expected is None:
        if value is not None:
            raise ValueError("undefined rate")
    elif type(value) not in (int, float) or not math.isfinite(value) or value != expected:
        raise ValueError("inconsistent rate")


def counts(value: dict) -> dict:
    for key in ("orders", "returns"):
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError("invalid count")
    if value["returns"] > value["orders"]:
        raise ValueError("inconsistent counts")
    start, end = (date.fromisoformat(text(value[key])) for key in ("start_date", "end_date"))
    if str(start) != value["start_date"] or str(end) != value["end_date"]:
        raise ValueError("invalid date format")
    if not 0 <= (end - start).days < 90:
        raise ValueError("invalid interval")
    rate = round(value["returns"] / value["orders"] * 100, 6) if value["orders"] else None
    numeric(value["return_rate"], rate)
    return {key: rate if key == "return_rate" else value[key] for key in sorted(COUNT_KEYS)}


def build_report(value: dict) -> dict:
    closed(value, {"metrics", "knowledge_findings", "sources"})
    original = closed(value["metrics"], METRIC_KEYS)
    baseline = counts(closed(original["baseline"], COUNT_KEYS))
    current = counts(original)
    start, end = date.fromisoformat(current["start_date"]), date.fromisoformat(current["end_date"])
    if baseline["end_date"] != str(start - timedelta(days=1)) or baseline["start_date"] != str(
        start - timedelta(days=(end - start).days + 1)
    ):
        raise ValueError("inconsistent baseline")
    text(original["sku"], 64)
    if original["timezone"] != "Asia/Ho_Chi_Minh":
        raise ValueError("invalid timezone")
    change = (
        round(current["return_rate"] - baseline["return_rate"], 6)
        if current["return_rate"] is not None and baseline["return_rate"] is not None
        else None
    )
    numeric(original["change_percentage_points"], change)
    metrics = {
        **current,
        "sku": original["sku"],
        "timezone": original["timezone"],
        "baseline": baseline,
        "change_percentage_points": change,
    }
    sources = value["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 40:
        raise ValueError("invalid sources")
    source_pairs = set()
    for source in sources:
        closed(source, {"type", "reference"})
        if source["type"] not in {"data", "knowledge", "history"}:
            raise ValueError("invalid source type")
        source_pairs.add((source["type"], text(source["reference"], 2000)))
    if not {"data", "knowledge"} <= {kind for kind, _ in source_pairs}:
        raise ValueError("missing evidence")
    findings = value["knowledge_findings"]
    if not isinstance(findings, list) or len(findings) > 10:
        raise ValueError("invalid findings")
    for finding in findings:
        closed(finding, {"reference", "finding"})
        text(finding["finding"], 2000)
        if ("knowledge", text(finding["reference"], 2000)) not in source_pairs:
            raise ValueError("unknown finding reference")
    report = {
        "schema_version": "1",
        "metrics": metrics,
        "knowledge_findings": [dict(f) for f in findings],
        "sources": [dict(s) for s in sources],
    }
    if (
        len(json.dumps(report, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        > MAX_INPUT_BYTES
    ):
        raise ValueError("report too large")
    return report


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a grounded ShopOps report")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        with args.input.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("oversize input")
        value = json.loads(raw, object_pairs_hook=unique_object)
        report = build_report(value)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
    except (ValueError, TypeError, OSError, OverflowError, RecursionError) as _error:
        print("invalid report input", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
