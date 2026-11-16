"""Hourly USDC transfer counts over the same window, straight from HyperSync (uses hypersync_check.scan).
Hour boundaries are the first slot whose block_time is at or after each UTC hour."""
import json, os, sys, datetime, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from hypersync_check import scan, q

def first_slot_at(ts, lo=469600000, hi=470200000):
    def bt(s):
        d = q({"from_slot": s, "to_slot": s + 50, "include_all_blocks": True, "field_selection": {"block": ["slot", "block_time"]}})
        rows = sorted((b for bb in d.get("blocks", []) for b in bb if b.get("block_time")), key=lambda b: b["slot"])
        return rows[0]["slot"], rows[0]["block_time"]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if bt(mid)[1] >= ts: hi = mid
        else: lo = mid
    return bt(hi)[0]

t0 = 1794744000
with ThreadPoolExecutor(8) as ex:
    bounds = list(ex.map(lambda h: first_slot_at(t0 + 3600 * h), range(25)))
def hour(i):
    lo, hi = bounds[i], bounds[i + 1]
    step = (hi - lo + 3) // 4
    parts = [scan((s, min(hi, s + step))) for s in range(lo, hi, step)]
    return {"hour_utc": datetime.datetime.fromtimestamp(t0 + 3600 * i, datetime.timezone.utc).strftime("%d %b %H:00"),
            "from_slot": lo, "to_slot": hi, "transfers": sum(p["transfers"] for p in parts), "volume": sum(p["volume"] for p in parts)}
with ThreadPoolExecutor(8) as ex:
    rows = list(ex.map(hour, range(24)))
json.dump({"bounds": bounds, "hours": rows}, open("hourly_hypersync.json", "w"), indent=1)
for r in rows: print(r["hour_utc"], r["transfers"], round(r["volume"] / 1e6))
print("total", sum(r["transfers"] for r in rows))
