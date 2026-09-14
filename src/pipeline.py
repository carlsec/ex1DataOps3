"""Pipeline de vendas — mesma lógica do Ex1/Ex2.

O CI verde deste pipeline só prova que o código roda sem exceção. Ele não
prova que o resultado está correto: essa é a pergunta que o Ex3 endereça
com os checks de qualidade de dados e o Quality Gate.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "order_id",
    "customer_id",
    "product",
    "quantity",
    "unit_price",
    "region",
}


def load_orders(input_path: str | Path) -> pd.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {path}")
    return pd.read_csv(path)


def validate_orders(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(missing)}")

    required = df[list(REQUIRED_COLUMNS)]
    if required.isnull().any().any():
        raise ValueError("Valores nulos não são permitidos nas colunas obrigatórias")

    if (df["quantity"] <= 0).any():
        raise ValueError("quantity deve ser maior que zero")

    if (df["unit_price"] < 0).any():
        raise ValueError("unit_price não pode ser negativo")

    return df


def transform_orders(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["total_amount"] = result["quantity"] * result["unit_price"]
    return result


def write_orders(df: pd.DataFrame, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def run_pipeline(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    print(f"[pipeline] input={input_path}")
    print(f"[pipeline] output={output_path}")

    orders = load_orders(input_path)
    validate_orders(orders)
    transformed = transform_orders(orders)
    written = write_orders(transformed, output_path)

    total = float(transformed["total_amount"].sum())
    print(f"[pipeline] rows={len(transformed)}")
    print(f"[pipeline] total_amount={total:.2f}")
    print(f"[pipeline] wrote={written}")
    return transformed


def main() -> None:
    run_pipeline("data/input/sample_clean.csv", "data/output/sample_clean_transformed.csv")


if __name__ == "__main__":
    main()
