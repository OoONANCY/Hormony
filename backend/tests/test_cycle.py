from datetime import date
from hormony.ledger.cycle import cycle_day, phase, predict_next_start

def test_cycle():
    starts = [date(2026,6,14), date(2026,7,12), date(2026,8,9), date(2026,9,6)]
    assert cycle_day(date(2026,9,29), starts) == 24
    assert phase(24) == "Late luteal"
    assert cycle_day(date(2026,8,19), starts) == 11
    assert predict_next_start(starts) == date(2026,10,4)
    assert cycle_day(date(2026,6,1), starts) is None


def test_phases_scale_with_cycle_length():
    from hormony.ledger.cycle import is_late, late_window
    assert late_window(28) == (20, 28) and late_window(35) == (27, 35)
    assert [phase(c, 35) for c in (5, 20, 21, 23, 26, 27, 35)] == [
        "Period", "Follicular", "Ovulation", "Ovulation", "Early luteal", "Late luteal", "Late luteal"]
    assert is_late(27, 35) and not is_late(26, 35) and not is_late(36, 35)
    assert [phase(c) for c in (13, 14, 17, 20)] == ["Follicular", "Ovulation", "Early luteal", "Late luteal"]
