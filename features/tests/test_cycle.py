from datetime import date, timedelta
from features.forecasting.models import LedgerRow
from features.forecasting.cycle import project_next_cycle


def _cycle_rows(days):
    base = date(2025, 1, 1)
    d = base
    rows = [LedgerRow(id="c0", date=d, kind="cycle", name="Period started", value=None)]
    for i, gap in enumerate(days):
        d = d + timedelta(days=gap)
        rows.append(LedgerRow(id=f"c{i+1}", date=d, kind="cycle",
                              name="Period started", value=None))
    return rows


def test_regular_28_day_cycles():
    rows = _cycle_rows([28, 28, 28, 28])
    p = project_next_cycle(rows)
    assert p.expected_length_days == 28.0
    assert p.based_on_cycles == 4


def test_outlier_is_filtered():
    rows = _cycle_rows([28, 28, 75, 28])
    p = project_next_cycle(rows)
    assert p.expected_length_days == 28.0
    assert p.based_on_cycles == 3


def test_single_period_fallback():
    rows = [LedgerRow(id="c0", date=date(2025, 1, 1),
                      kind="cycle", name="Period started", value=None)]
    p = project_next_cycle(rows)
    assert p.expected_length_days == 28.0
    assert p.based_on_cycles == 0


def test_empty_returns_none():
    assert project_next_cycle([]) is None