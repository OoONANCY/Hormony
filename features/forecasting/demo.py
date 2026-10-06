from datetime import date, timedelta
from .models import LedgerRow
from .api import forecast
import json
import pathlib


def main():
    today = date.today()
    base = today - timedelta(days=28 * 5 -14)  # 4.5 cycles ago

    rows = []
    for i in range(5):
        rows.append(LedgerRow(id=f"c{i}", date=base + timedelta(days=28 * i),
                              kind="cycle", name="Period started", value=None))
    for i in range(6):
        rows.append(LedgerRow(id=f"e{i}", date=base + timedelta(days=7 * i),
                              kind="lab", name="E2", value=100.0 + 12 * i,
                              unit="pg/mL"))

    result = forecast(rows)
    cycle = result["cycle"]
    print(f"As of: {result['as_of']}")
    print(f"Next period: {cycle.next_start}  "
          f"(window {cycle.low} .. {cycle.high})  "
          f"conf {cycle.confidence}  n={cycle.based_on_cycles}")
    for h in result["hormones"]:
        print(f"\n{h.name} ({h.unit})  conf {h.confidence}  {h.method}")
        for (d, v), (_, lo), (_, hi) in zip(h.points, h.band_low, h.band_high):
            print(f"  {d}  {v}  ({lo} .. {hi})")

               
               
    # emit JSON for the web preview
    web_dir = pathlib.Path(__file__).parent / "web"
    web_dir.mkdir(exist_ok=True)
    out = web_dir / "data.json"

    payload = {
        "as_of": result["as_of"],
        "cycle": {
            "next_start": str(cycle.next_start),
            "low": str(cycle.low),
            "high": str(cycle.high),
            "expected_length_days": cycle.expected_length_days,
            "confidence": cycle.confidence,
            "based_on_cycles": cycle.based_on_cycles,
        },
        "hormones": [
            {
                "name": h.name,
                "unit": h.unit,
                "confidence": h.confidence,
                "method": h.method,
                "points": [[str(d), v] for d, v in h.points],
                "band_low": [[str(d), v] for d, v in h.band_low],
                "band_high": [[str(d), v] for d, v in h.band_high],
            }
            for h in result["hormones"]
        ],
    }

    out.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()