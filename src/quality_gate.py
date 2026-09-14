"""Quality Gate — decide, com evidência, se um arquivo pode ser promovido.

Uso:

    python -m src.quality_gate --input data/input/sample_clean.csv

Executa todos os checks de `src.dq_checks`, imprime um relatório legível,
grava `quality_report.json` e retorna:

    exit code 0  -> nenhum check BLOQUEANTE falhou (pode promover)
    exit code 1  -> pelo menos um check BLOQUEANTE falhou (barra o CI)

Checks marcados como ALERTA nunca mudam o exit code: eles aparecem no
relatório para dar visibilidade, mas não travam a esteira.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.dq_checks import SEVERITY, run_all_checks

DEFAULT_REPORT_PATH = "quality_report.json"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quality Gate de dados de vendas")
    parser.add_argument("--input", required=True, help="Caminho do CSV a ser avaliado")
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT_PATH,
        help=f"Caminho do relatório JSON de saída (default: {DEFAULT_REPORT_PATH})",
    )
    parser.add_argument(
        "--reference-datetime",
        default=None,
        help=(
            "Instante ISO 8601 usado como 'agora' para o check de freshness "
            "(default: horário real de execução). Útil para tornar o gate "
            "determinístico em CI ou testes."
        ),
    )
    return parser.parse_args(argv)


def _print_report(results: list[dict]) -> None:
    print("=" * 72)
    print("QUALITY GATE — relatório de qualidade de dados")
    print("=" * 72)
    for result in results:
        status = "PASSOU" if result["passed"] else "FALHOU"
        severidade = result["severity"]
        print(f"[{status}] ({severidade}) {result['check']}")
        print(f"        {result['details']}")
    print("-" * 72)


def build_report(input_path: str, reference_datetime: str | None = None) -> dict:
    path = Path(input_path)
    df = pd.read_csv(path)

    reference_time = (
        datetime.fromisoformat(reference_datetime) if reference_datetime else None
    )

    raw_results = run_all_checks(df, reference_time=reference_time)
    results = [
        {**result, "severity": SEVERITY[result["check"]]}
        for result in raw_results
    ]

    blocking_failures = [
        r["check"] for r in results if not r["passed"] and r["severity"] == "BLOQUEANTE"
    ]
    warning_failures = [
        r["check"] for r in results if not r["passed"] and r["severity"] == "ALERTA"
    ]

    return {
        "input_file": str(path),
        "generated_at": datetime.now().isoformat(),
        "row_count": len(df),
        "results": results,
        "blocking_failures": blocking_failures,
        "warning_failures": warning_failures,
        "passed": len(blocking_failures) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    report = build_report(args.input, args.reference_datetime)

    _print_report(report["results"])

    if report["passed"]:
        print("RESULTADO: APROVADO — nenhum check bloqueante falhou.")
    else:
        print(f"RESULTADO: REPROVADO — checks bloqueantes falharam: {report['blocking_failures']}")
    if report["warning_failures"]:
        print(f"ALERTAS (não bloqueiam): {report['warning_failures']}")
    print("=" * 72)

    report_path = Path(args.report)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Relatório gravado em: {report_path}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
