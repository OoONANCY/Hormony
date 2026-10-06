from datetime import date, timedelta
from statistics import median
from .models import LedgerRow, CycleProjection

MIN_LEN, MAX_LEN = 15, 60


def _cycle_starts(rows):
    starts = [
        r.date for r in rows
        if r.kind == "cycle" and r.name.strip().lower() == "period started"
    ]
    return sorted(set(starts))


def _observed_lengths(starts):
    return [
        (b - a).days
        for a, b in zip(starts, starts[1:])
        if MIN_LEN <= (b - a).days <= MAX_LEN
    ]


def project_next_cycle(rows):
    starts = _cycle_starts(rows)
    if len(starts) < 1:
        return None

    obs = _observed_lengths(starts)
    if not obs:
        expected, sigma, n = 28.0, 7.0, 0
    else:
        expected = float(median(obs))
        mad = median([abs(x - expected) for x in obs])
        sigma = max(1.0, 1.4826 * mad)
        n = len(obs)

    next_start = starts[-1] + timedelta(days=round(expected))
    low  = next_start - timedelta(days=round(sigma))
    high = next_start + timedelta(days=round(sigma))

    conf = min(1.0, n / 6.0)
    if sigma > 5:
        conf *= 0.7

    return CycleProjection(
        next_start=next_start,
        expected_length_days=expected,
        low=low, high=high,
        confidence=round(conf, 2),
        based_on_cycles=n,
    )

if __name__ == "__main__":
    from datetime import date, timedelta
    base = date(2025, 1, 1)
    rows = [
        LedgerRow(id=str(i), date=base + timedelta(days=28 * i),
                  kind="cycle", name="Period started", value=None)
        for i in range(5)
    ]
    print(project_next_cycle(rows))