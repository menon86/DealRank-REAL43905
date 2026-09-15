"""See docs/build-plan.md 2.4 — assert no float appears in any returned
money field, so a stray `/ 12` cannot silently reintroduce binary
rounding. IRR fields are the one documented exception (metrics.py's
module docstring): numpy-financial requires float, converted straight
back to Decimal at that boundary.
"""

import dataclasses
from decimal import Decimal

from app.engine.metrics import compute
from tests.engine.fixtures import ALL_SEED_DEALS

IRR_FIELDS = {"unlevered_irr", "levered_irr"}


def _assert_no_float(obj, path: str = "root"):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            if f.name in IRR_FIELDS:
                continue
            _assert_no_float(value, f"{path}.{f.name}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_float(item, f"{path}[{i}]")
    elif isinstance(obj, float):
        raise AssertionError(f"found float at {path}: {obj!r}")


def test_no_float_in_metrics_output():
    for deal in ALL_SEED_DEALS:
        metrics = compute(deal)
        _assert_no_float(metrics)


def test_irr_fields_are_decimal_not_float():
    """The one documented float boundary converts back to Decimal before
    returning — DealMetrics never actually holds a float, even for IRR.
    """
    for deal in ALL_SEED_DEALS:
        metrics = compute(deal)
        assert isinstance(metrics.unlevered_irr, Decimal)
        assert isinstance(metrics.levered_irr, Decimal)
