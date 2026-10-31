import copy
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from app.contracts.report import RuntimeReport

SCRIPT = (
    Path(__file__).resolve().parents[2] / "runtime-bundles/shopops-hosted-v1/"
    "shopops-analysis/skills/returns-analysis/scripts/summarize_returns.py"
)


@pytest.fixture
def evidence():
    return {
        "metrics": {
            "sku": "SKU-001",
            "start_date": "2026-10-08",
            "end_date": "2026-10-14",
            "timezone": "Asia/Ho_Chi_Minh",
            "orders": 100,
            "returns": 15,
            "return_rate": 15.0,
            "baseline": {
                "start_date": "2026-10-01",
                "end_date": "2026-10-07",
                "orders": 100,
                "returns": 5,
                "return_rate": 5.0,
            },
            "change_percentage_points": 10.0,
        },
        "knowledge_findings": [
            {
                "reference": "knowledge:policy:1:returns#rule",
                "finding": "Kiểm tra chính sách hoàn trả phiên bản 1.",
            }
        ],
        "sources": [
            {"type": "data", "reference": "data:returns:fixture"},
            {"type": "knowledge", "reference": "knowledge:policy:1:returns#rule"},
        ],
    }


def helper():
    return runpy.run_path(str(SCRIPT))["build_report"]


def test_report_recomputes_fixture_and_matches_frozen_contract(evidence):
    original = copy.deepcopy(evidence)
    result = helper()(evidence)
    assert evidence == original
    report = RuntimeReport.model_validate(result)
    assert set(result) == {"schema_version", "metrics", "knowledge_findings", "sources"}
    assert report.metrics.return_rate == 15
    assert report.metrics.baseline.return_rate == 5
    assert report.metrics.change_percentage_points == 10
    assert report.model_dump(mode="json") == result


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "negative",
        "bool",
        "float_count",
        "rate",
        "change",
        "nan",
        "infinity",
        "missing_data",
        "missing_knowledge",
        "unknown_source",
        "forged_reference",
        "empty_reference",
        "extra_top",
        "extra_metrics",
        "extra_count",
        "extra_finding",
        "extra_source",
        "too_many_findings",
        "long_finding",
        "blank_finding",
        "timezone",
        "bad_date",
        "unknown_key_missing",
    ],
)
def test_report_rejects_invalid_or_ungrounded_input(evidence, mutation):
    metrics = evidence["metrics"]
    if mutation == "count":
        metrics["returns"] = 101
    elif mutation == "negative":
        metrics["orders"] = -1
    elif mutation == "bool":
        metrics["returns"] = True
    elif mutation == "float_count":
        metrics["returns"] = 15.0
    elif mutation in {"rate", "change", "nan", "infinity"}:
        key = "change_percentage_points" if mutation == "change" else "return_rate"
        metrics[key] = {"rate": 0, "change": 9, "nan": float("nan"), "infinity": float("inf")}[
            mutation
        ]
    elif mutation == "missing_data":
        evidence["sources"] = evidence["sources"][1:]
    elif mutation == "missing_knowledge":
        evidence["sources"] = evidence["sources"][:1]
    elif mutation == "unknown_source":
        evidence["sources"][0]["type"] = "invented"
    elif mutation == "forged_reference":
        evidence["knowledge_findings"][0]["reference"] = "fabricated"
    elif mutation == "empty_reference":
        evidence["sources"][0]["reference"] = ""
    elif mutation.startswith("extra_"):
        target = {
            "extra_top": evidence,
            "extra_metrics": metrics,
            "extra_count": metrics["baseline"],
            "extra_finding": evidence["knowledge_findings"][0],
            "extra_source": evidence["sources"][0],
        }[mutation]
        target["unapproved"] = 1
    elif mutation == "too_many_findings":
        evidence["knowledge_findings"] *= 11
    elif mutation in {"long_finding", "blank_finding"}:
        evidence["knowledge_findings"][0]["finding"] = (
            "x" * 2001 if mutation == "long_finding" else " "
        )
    elif mutation == "timezone":
        metrics["timezone"] = "UTC"
    elif mutation == "bad_date":
        metrics["start_date"] = "not-a-date"
    else:
        del metrics["sku"]
    with pytest.raises(ValueError):
        helper()(evidence)


def test_zero_orders_preserves_unknown_rate(evidence):
    evidence["metrics"].update(orders=0, returns=0, return_rate=None, change_percentage_points=None)
    result = helper()(evidence)
    assert RuntimeReport.model_validate(result).metrics.return_rate is None


def test_cli_generates_report_and_sanitizes_failures(tmp_path, evidence):
    source, output = tmp_path / "input.json", tmp_path / "report.json"
    source.write_text(json.dumps(evidence))
    command = [
        sys.executable,
        "-I",
        "-B",
        str(SCRIPT),
        "--input",
        str(source),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""
    assert RuntimeReport.model_validate_json(output.read_bytes()).schema_version == "1"
    original = output.read_bytes()
    source.write_text('{"sensitive-untrusted-value": 1}')
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0
    assert result.stderr.strip() == "invalid report input"
    assert result.stdout == ""
    assert output.read_bytes() == original


def test_cli_rejects_duplicate_json_keys(tmp_path, evidence):
    source, output = tmp_path / "input.json", tmp_path / "report.json"
    raw = json.dumps(evidence)
    source.write_text('{"sources": [],' + raw[1:])
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(SCRIPT), "--input", str(source), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not output.exists()


def test_helper_syntax_supports_existing_sandbox_python():
    # The hosted image's interpreter version is not controlled by the backend image.
    import ast

    ast.parse(SCRIPT.read_text(), feature_version=(3, 10))
