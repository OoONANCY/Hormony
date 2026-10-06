from datetime import date, timedelta
from features.forecasting.models import LedgerRow
from features.forecasting.hormones import project_hormone


def _lab_rows(values, name="E2"):
    base = date(2025, 1, 1)
    return [
        LedgerRow(id=f"l{i}", date=base + timedelta(days=7 * i),
                  kind="lab", name=name, value=v, unit="pg/mL")
        for i, v in enumerate(values)
    ]


def test_flat_series_projects_flat():
    p = project_hormone(_lab_rows([100, 100, 100, 100]), "E2")
    vs = [v for _, v in p.points]
    assert all(abs(v - 100) < 1e-6 for v in vs)


def test_upward_trend():
    p = project_hormone(_lab_rows([100, 110, 120, 130, 140]), "E2")
    vs = [v for _, v in p.points]
    assert vs[-1] > vs[0]


def test_too_few_points_returns_none():
    assert project_hormone(_lab_rows([100, 110]), "E2") is None


def test_other_hormone_ignored():
    assert project_hormone(_lab_rows([100, 110, 120], name="P4"), "E2") is None