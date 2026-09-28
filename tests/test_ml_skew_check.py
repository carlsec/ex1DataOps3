import pandas as pd

from src.ml_skew_check import compare_train_serving, train_high_value_model

TRAIN_PATH = "data/input/sample_clean.csv"
SERVING_PATH = "data/input/sample_serving.csv"


def _skew_by_feature() -> dict[str, dict]:
    train = pd.read_csv(TRAIN_PATH)
    serving = pd.read_csv(SERVING_PATH)
    return {r["feature"]: r for r in compare_train_serving(train, serving)}


def test_price_shift_is_flagged_as_skew() -> None:
    skew = _skew_by_feature()

    assert skew["unit_price"]["skewed"] is True
    assert skew["total_amount"]["skewed"] is True
    assert skew["unit_price"]["mean_change_pct"] > 20


def test_unchanged_quantity_is_not_flagged() -> None:
    skew = _skew_by_feature()

    assert skew["quantity"]["skewed"] is False


def test_identical_distributions_have_no_skew() -> None:
    train = pd.read_csv(TRAIN_PATH)

    results = compare_train_serving(train, train.copy())

    assert not any(r["skewed"] for r in results)


def test_model_trains_on_clean_sample() -> None:
    model = train_high_value_model(pd.read_csv(TRAIN_PATH))

    assert list(model.classes_) == [0, 1]
