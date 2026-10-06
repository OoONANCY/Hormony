from datetime import date
from .cycle import project_next_cycle
from .hormones import project_all


def forecast(rows, today=None):
    today = today or date.today()
    return {
        "as_of": today.isoformat(),
        "cycle": project_next_cycle(rows),
        "hormones": project_all(rows),
    }