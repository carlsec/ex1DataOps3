"""Desafio opcional de MLOps: training-serving skew.

Treina um classificador simples para prever se uma venda é "de alto valor"
(total_amount acima da mediana do treino) e compara a distribuição das
features entre o conjunto de treino (Champion) e um conjunto de "produção"
(Challenger) — sinalizando quando uma feature se deslocou demais.

Uso:

    python -m src.ml_skew_check \
        --train data/input/sample_clean.csv \
        --serving data/input/sample_serving.csv
"""

from __future__ import annotations

import argparse

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

NUMERIC_FEATURES = ["quantity", "unit_price", "total_amount"]
SKEW_THRESHOLD_PERCENT = 20.0


def add_high_value_label(df: pd.DataFrame) -> pd.DataFrame:
    """Rotula cada linha como alto valor (1) se total_amount > mediana."""
    result = df.copy()
    median = result["total_amount"].median()
    result["high_value"] = (result["total_amount"] > median).astype(int)
    return result


def train_high_value_model(
    train_df: pd.DataFrame,
    features: list[str] | None = None,
) -> LogisticRegression:
    """Treina uma regressão logística para prever `high_value`."""
    features = features or ["quantity", "unit_price"]
    labeled = add_high_value_label(train_df)

    X = labeled[features]
    y = labeled["high_value"]

    if y.nunique() < 2:
        raise ValueError("Não é possível treinar: apenas uma classe presente em high_value")

    X_train, _, y_train, _ = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = LogisticRegression()
    model.fit(X_train, y_train)
    return model


def compare_train_serving(
    train_df: pd.DataFrame,
    serving_df: pd.DataFrame,
    colunas: list[str] | None = None,
    limite_percentual: float = SKEW_THRESHOLD_PERCENT,
) -> list[dict]:
    """Compara média/desvio padrão de cada feature entre treino e serving.

    Devolve uma lista de dicts, um por coluna, com o percentual de variação
    de média e desvio padrão, e se a coluna estourou `limite_percentual`.
    """
    colunas = colunas or NUMERIC_FEATURES
    resultados = []

    for coluna in colunas:
        train_mean = float(train_df[coluna].mean())
        serving_mean = float(serving_df[coluna].mean())
        train_std = float(train_df[coluna].std())
        serving_std = float(serving_df[coluna].std())

        mean_change_pct = _percent_change(train_mean, serving_mean)
        std_change_pct = _percent_change(train_std, serving_std)

        skewed = abs(mean_change_pct) > limite_percentual or abs(std_change_pct) > limite_percentual

        resultados.append(
            {
                "feature": coluna,
                "train_mean": train_mean,
                "serving_mean": serving_mean,
                "mean_change_pct": mean_change_pct,
                "train_std": train_std,
                "serving_std": serving_std,
                "std_change_pct": std_change_pct,
                "skewed": skewed,
            }
        )

    return resultados


def _percent_change(baseline: float, current: float) -> float:
    if baseline == 0:
        return 0.0 if current == 0 else float("inf")
    return ((current - baseline) / baseline) * 100


def print_champion_challenger_report(resultados: list[dict]) -> None:
    print("=" * 78)
    print("CHAMPION (treino) vs CHALLENGER (serving) — training-serving skew")
    print("=" * 78)
    header = f"{'feature':<15}{'train_mean':>14}{'serving_mean':>14}{'Δmean %':>12}{'skew?':>10}"
    print(header)
    print("-" * 78)
    for r in resultados:
        flag = "SIM" if r["skewed"] else "não"
        print(
            f"{r['feature']:<15}{r['train_mean']:>14.2f}{r['serving_mean']:>14.2f}"
            f"{r['mean_change_pct']:>11.1f}%{flag:>10}"
        )
    print("-" * 78)
    estouradas = [r["feature"] for r in resultados if r["skewed"]]
    if estouradas:
        print(f"ALERTA: features com skew acima de {SKEW_THRESHOLD_PERCENT}%: {estouradas}")
    else:
        print("Nenhuma feature estourou o limite de skew.")
    print("=" * 78)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Training-serving skew check")
    parser.add_argument("--train", default="data/input/sample_clean.csv")
    parser.add_argument("--serving", default="data/input/sample_serving.csv")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    train_df = pd.read_csv(args.train)
    serving_df = pd.read_csv(args.serving)

    model = train_high_value_model(train_df)
    print(f"[ml_skew_check] modelo treinado: {model.__class__.__name__}")

    resultados = compare_train_serving(train_df, serving_df)
    print_champion_challenger_report(resultados)


if __name__ == "__main__":
    main()
