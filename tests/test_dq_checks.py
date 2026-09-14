from datetime import datetime, timedelta

import pandas as pd

from src.dq_checks import (
    check_consistency,
    check_duplicates,
    check_freshness,
    check_nulls,
    check_schema,
    check_volume,
)


def _valid_df(n: int = 4) -> pd.DataFrame:
    now = datetime(2026, 1, 10, 12, 0, 0)
    return pd.DataFrame(
        {
            "order_id": list(range(1, n + 1)),
            "customer_id": [f"C{i:03d}" for i in range(1, n + 1)],
            "product": ["Notebook"] * n,
            "quantity": [2] * n,
            "unit_price": [100.0] * n,
            "region": ["Sudeste"] * n,
            "total_amount": [200.0] * n,
            "event_date": [(now - timedelta(hours=i)).isoformat() for i in range(n)],
        }
    )


# --- check_schema -----------------------------------------------------


def test_check_schema_passes_with_all_columns_and_types() -> None:
    result = check_schema(_valid_df())

    assert result["passed"] is True
    assert result["check"] == "schema"


def test_check_schema_fails_when_column_is_missing() -> None:
    df = _valid_df().drop(columns=["unit_price"])

    result = check_schema(df)

    assert result["passed"] is False
    assert "unit_price" in result["details"]


def test_check_schema_fails_when_numeric_column_has_wrong_type() -> None:
    df = _valid_df()
    df["quantity"] = df["quantity"].astype(str) + "un"

    result = check_schema(df)

    assert result["passed"] is False
    assert "quantity" in result["details"]


# --- check_nulls --------------------------------------------------------


def test_check_nulls_passes_below_threshold() -> None:
    df = _valid_df(n=10)

    result = check_nulls(df, ["customer_id"], limite_percentual=5.0)

    assert result["passed"] is True


def test_check_nulls_fails_above_threshold() -> None:
    df = _valid_df(n=10)
    df.loc[0:1, "customer_id"] = None  # 20% nulo

    result = check_nulls(df, ["customer_id"], limite_percentual=5.0)

    assert result["passed"] is False
    assert "customer_id" in result["details"]


# --- check_duplicates -----------------------------------------------------


def test_check_duplicates_passes_with_unique_keys() -> None:
    df = _valid_df()

    result = check_duplicates(df, chave=["order_id"])

    assert result["passed"] is True


def test_check_duplicates_fails_with_repeated_order_id() -> None:
    df = _valid_df()
    df.loc[1, "order_id"] = df.loc[0, "order_id"]

    result = check_duplicates(df, chave=["order_id"])

    assert result["passed"] is False


# --- check_volume -----------------------------------------------------


def test_check_volume_passes_within_window() -> None:
    df = _valid_df(n=10)

    result = check_volume(df, volume_esperado_min=5, volume_esperado_max=20)

    assert result["passed"] is True


def test_check_volume_fails_below_minimum() -> None:
    df = _valid_df(n=2)

    result = check_volume(df, volume_esperado_min=10, volume_esperado_max=20)

    assert result["passed"] is False


# --- check_freshness -----------------------------------------------------


def test_check_freshness_passes_within_sla() -> None:
    df = _valid_df(n=3)
    reference = datetime(2026, 1, 10, 12, 0, 0)

    result = check_freshness(df, "event_date", sla_horas=48, reference_time=reference)

    assert result["passed"] is True


def test_check_freshness_fails_when_data_is_stale() -> None:
    df = _valid_df(n=3)
    reference = datetime(2026, 1, 20, 12, 0, 0)  # 10 dias depois das datas do df

    result = check_freshness(df, "event_date", sla_horas=48, reference_time=reference)

    assert result["passed"] is False


# --- check_consistency -----------------------------------------------------


def test_check_consistency_passes_when_totals_match() -> None:
    df = _valid_df()

    result = check_consistency(df)

    assert result["passed"] is True


def test_check_consistency_fails_when_total_amount_is_wrong() -> None:
    df = _valid_df()
    df.loc[0, "total_amount"] = 999.0  # quantity(2) * unit_price(100) = 200

    result = check_consistency(df)

    assert result["passed"] is False
    assert "order_id" in result["details"] or "1" in result["details"]
