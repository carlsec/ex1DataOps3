"""Testes de integração: rodam o quality_gate.py como processo real,
exatamente como o CI faz, e conferem o exit code.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_REFERENCE_DATETIME = "2026-09-13T12:00:00"


def _run_quality_gate(input_file: str, tmp_path: Path) -> subprocess.CompletedProcess:
    report_path = tmp_path / "quality_report.json"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src.quality_gate",
            "--input",
            input_file,
            "--report",
            str(report_path),
            "--reference-datetime",
            SAMPLE_REFERENCE_DATETIME,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_quality_gate_approves_clean_sample(tmp_path: Path) -> None:
    result = _run_quality_gate("data/input/sample_clean.csv", tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "APROVADO" in result.stdout


def test_quality_gate_rejects_dirty_sample(tmp_path: Path) -> None:
    result = _run_quality_gate("data/input/sample_dirty.csv", tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "REPROVADO" in result.stdout


def test_quality_gate_writes_report_with_blocking_failures_of_dirty_sample(
    tmp_path: Path,
) -> None:
    _run_quality_gate("data/input/sample_dirty.csv", tmp_path)

    report = json.loads((tmp_path / "quality_report.json").read_text(encoding="utf-8"))

    assert report["passed"] is False
    assert {"nulls", "duplicates", "consistency"} <= set(report["blocking_failures"])
    assert report["warning_failures"] == ["volume"]
    assert {r["check"] for r in report["results"]} == {
        "schema", "nulls", "duplicates", "volume", "freshness", "consistency",
    }
