from datetime import date, timedelta
from features.forecasting.models import LedgerRow
from features.forecasting.api import forecast


def test_forecast_keys():
    base = date(2025, 1, 1)
    rows = [
        LedgerRow(id=f"c{i}", date=base + timedelta(days=28 * i),
                  kind="cycle", name="Period started", value=None)
        for i in range(3)
    ] + [
        LedgerRow(id=f"e{i}", date=base + timedelta(days=7 * i),
                  kind="lab", name="E2", value=100 + 10 * i, unit="pg/mL")
        for i in range(4)
    ]
    r = forecast(rows)
    assert set(r) == {"as_of", "cycle", "hormones"}
    assert r["cycle"] is not None
    assert any(h.name == "E2" for h in r["hormones"])
