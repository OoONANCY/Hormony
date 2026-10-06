import math
from datetime import timedelta
from .models import LedgerRow, HormoneProjection

HORIZON_DAYS = 60
STEP_DAYS = 7


def _linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs) or 1e-9
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    resid = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    sigma = math.sqrt(sum(r * r for r in resid) / max(1, n - 2))
    ss_tot = sum((y - my) ** 2 for y in ys) or 1e-9
    r2 = 1 - sum(r * r for r in resid) / ss_tot
    return slope, intercept, sigma, r2, n


def project_hormone(rows, name):
    pts = [
        (r.date, r.value, r.unit or "")
        for r in rows
        if r.kind == "lab"
        and r.name.strip().upper() == name.upper()
        and r.value is not None
    ]
    pts.sort()
    if len(pts) < 3:
        return None

    t0 = pts[0][0]
    xs = [(d - t0).days for d, _, _ in pts]
    ys = [v for _, v, _ in pts]
    unit = pts[-1][2] or ""

    slope, intercept, sigma, r2, n = _linfit(xs, ys)

    last_day = xs[-1]
    out, lo, hi = [], [], []
    for h in range(STEP_DAYS, HORIZON_DAYS + 1, STEP_DAYS):
        x = last_day + h
        yhat = slope * x + intercept
        band = sigma * math.sqrt(1 + h / n)
        d = t0 + timedelta(days=x)
        out.append((d, round(yhat, 2)))
        lo.append((d, round(yhat - band, 2)))
        hi.append((d, round(yhat + band, 2)))

    conf = min(1.0, n / 8.0)
    if r2 < 0.1:
        conf *= 0.6

    return HormoneProjection(
        name=name, unit=unit,
        points=out, band_low=lo, band_high=hi,
        confidence=round(conf, 2),
        method=f"linear_fit r2={r2:.2f} n={n}",
    )


def project_all(rows, names=("E2", "P4", "TSH")):
    return [p for n in names if (p := project_hormone(rows, n))]