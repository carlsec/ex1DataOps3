from pathlib import Path

import pandas as pd
import pytest

from src.pipeline import run_pipeline, transform_orders, validate_orders


def _write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_transform_orders_calculates_total_amount() -> None:
    orders = pd.DataFrame(
        {
            "order_id": [1, 2],
            "customer_id": ["C001", "C002"],
            "product": ["Notebook", "Mouse"],
            "quantity": [2, 10],
            "unit_price": [3500.0, 45.5],
            "region": ["Sudeste", "Sul"],
        }
    )

    result = transform_orders(orders)

    assert result.loc[0, "total_amount"] == 7000.0
    assert result.loc[1, "total_amount"] == 455.0


def test_pipeline_writes_valid_output(tmp_path: Path) -> None:
    input_file = _write_csv(
        tmp_path / "orders.csv",
        "order_id,customer_id,product,quantity,unit_price,region\n"
        "1,C001,Notebook,2,3500.0,Sudeste\n"
        "2,C002,Mouse,10,45.5,Sul\n",
    )
    output_file = tmp_path / "out" / "orders_transformed.csv"

    result = run_pipeline(input_file, output_file)

    written = pd.read_csv(output_file)
    assert output_file.exists()
    assert list(written.columns)[-1] == "total_amount"
    assert result["total_amount"].sum() == 7455.0
    assert written["total_amount"].sum() == 7455.0


def test_validate_orders_rejects_negative_unit_price() -> None:
    orders = pd.DataFrame(
        {
            "order_id": [1],
            "customer_id": ["C001"],
            "product": ["Notebook"],
            "quantity": [1],
            "unit_price": [-10.0],
            "region": ["Sudeste"],
        }
    )

    with pytest.raises(ValueError, match="unit_price"):
        validate_orders(orders)


def test_pipeline_raises_for_non_positive_quantity(tmp_path: Path) -> None:
    input_file = _write_csv(
        tmp_path / "invalid.csv",
        "order_id,customer_id,product,quantity,unit_price,region\n"
        "1,C001,Notebook,0,3500.0,Sudeste\n",
    )

    with pytest.raises(ValueError, match="quantity"):
        run_pipeline(input_file, tmp_path / "out.csv")


def test_pipeline_raises_for_missing_columns(tmp_path: Path) -> None:
    input_file = _write_csv(
        tmp_path / "incomplete.csv",
        "order_id,customer,amount\n1,Ana,100.0\n",
    )

    with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
        run_pipeline(input_file, tmp_path / "out.csv")


def test_pipeline_raises_for_null_values(tmp_path: Path) -> None:
    input_file = _write_csv(
        tmp_path / "nulls.csv",
        "order_id,customer_id,product,quantity,unit_price,region\n"
        "1,C001,,2,3500.0,Sudeste\n",
    )

    with pytest.raises(ValueError, match="nulos"):
        run_pipeline(input_file, tmp_path / "out.csv")


def test_pipeline_silently_overwrites_inconsistent_total_amount(tmp_path: Path) -> None:
    """Documenta um comportamento perigoso: se o CSV de origem já trouxer um
    total_amount incorreto, o pipeline recalcula e SOBRESCREVE em silêncio —
    sem checar se o valor de origem estava certo. É exatamente esse tipo de
    lacuna que os checks de qualidade de dados do Ex3 vão cobrir.
    """
    input_file = _write_csv(
        tmp_path / "inconsistent.csv",
        "order_id,customer_id,product,quantity,unit_price,region,total_amount\n"
        "1,C001,Notebook,2,3500.0,Sudeste,999999.0\n",
    )

    result = run_pipeline(input_file, tmp_path / "out.csv")

    assert result.loc[0, "total_amount"] == 7000.0
