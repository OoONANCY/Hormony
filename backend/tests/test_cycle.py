from datetime import date
from hormony.ledger.cycle import cycle_day, phase, predict_next_start

def test_cycle():
    starts = [date(2026,6,14), date(2026,7,12), date(2026,8,9), date(2026,9,6)]
    assert cycle_day(date(2026,9,29), starts) == 24
    assert phase(24) == "Late luteal"
    assert cycle_day(date(2026,8,19), starts) == 11
    assert predict_next_start(starts) == date(2026,10,4)
    assert cycle_day(date(2026,6,1), starts) is None
