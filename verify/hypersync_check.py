"""Second method: count the same USDC transfers straight from HyperSync, without HyperIndex.

transferChecked (0x0c) is matched server-side on a1 = the USDC mint.
Plain transfer (0x03) is matched in transactions that have USDC token activity, then kept
only when its source (a0) or destination (a1) is a USDC token account in that transaction.
Only successful transactions (tx_success: true). Top level = is_inner false.
Usage: python3 hypersync_check.py START_SLOT END_SLOT_EXCLUSIVE [workers]
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

TOKEN = os.environ.get("ENVIO_API_TOKEN") or sys.exit("Set ENVIO_API_TOKEN")
URL = "https://solana.hypersync.xyz/query"
SPL = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def q(body):
    for attempt in range(20):
        try:
            req = urllib.request.Request(URL, json.dumps(body).encode(),
                                         {"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
            return json.load(urllib.request.urlopen(req, timeout=300))
        except Exception as e:
            time.sleep(min(60, 3 * (attempt + 1)))
    raise SystemExit("HyperSync failed")


def scan(rng):
    lo, hi = rng
    out = {"transfers": 0, "volume": 0, "top": 0, "top_volume": 0, "plain": 0, "checked": 0,
           "top_senders": set(), "senders": set()}
    # transferChecked: mint at a1
    slot = lo
    while slot < hi:
        d = q({"from_slot": slot, "to_slot": hi,
               "instruction_calls": [{"executing_account": [SPL], "d1": ["0c"], "a1": [USDC], "tx_success": True}],
               "field_selection": {"instruction_call": ["slot", "data", "a3", "is_inner", "executing_account", "d1", "a1"]}})
        for b in d.get("instruction_calls", []):
            for c in b:
                if c["executing_account"] != SPL or c["d1"] != "0c" or c["a1"] != USDC:
                    continue
                amt = int.from_bytes(bytes.fromhex(c["data"])[1:9], "little")
                out["transfers"] += 1; out["checked"] += 1; out["volume"] += amt
                out["senders"].add(c["a3"])
                if not c["is_inner"]:
                    out["top"] += 1; out["top_volume"] += amt; out["top_senders"].add(c["a3"])
        if d["next_slot"] <= slot: break
        slot = d["next_slot"]
    # plain transfer in transactions with USDC activity
    slot = lo
    while slot < hi:
        d = q({"from_slot": slot, "to_slot": hi,
               "instruction_calls": [{"executing_account": [SPL], "d1": ["03"], "tx_success": True}],
               "account_activity": [{"mint": [USDC]}],
               "field_selection": {"instruction_call": ["slot", "transaction_index", "data", "a0", "a1", "a2", "is_inner", "executing_account", "d1"],
                                   "account_activity": ["slot", "transaction_index", "account", "mint"]}})
        usdc_accts = set()
        for b in d.get("account_activity", []):
            for r in b:
                if r.get("mint") == USDC:
                    usdc_accts.add((r["slot"], r["transaction_index"], r["account"]))
        for b in d.get("instruction_calls", []):
            for c in b:
                if c["executing_account"] != SPL or c["d1"] != "03":
                    continue
                k = (c["slot"], c["transaction_index"])
                if (k + (c["a0"],)) not in usdc_accts and (k + (c["a1"],)) not in usdc_accts:
                    continue
                amt = int.from_bytes(bytes.fromhex(c["data"])[1:9], "little")
                out["transfers"] += 1; out["plain"] += 1; out["volume"] += amt
                out["senders"].add(c["a2"])
                if not c["is_inner"]:
                    out["top"] += 1; out["top_volume"] += amt; out["top_senders"].add(c["a2"])
        if d["next_slot"] <= slot: break
        slot = d["next_slot"]
    return out


if __name__ == "__main__":
    start, end = int(sys.argv[1]), int(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    step = (end - start + workers * 4 - 1) // (workers * 4)
    ranges = [(s, min(end, s + step)) for s in range(start, end, step)]
    tot = {"transfers": 0, "volume": 0, "top": 0, "top_volume": 0, "plain": 0, "checked": 0}
    ts, als = set(), set()
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(scan, ranges):
            for k in tot: tot[k] += r[k]
            ts |= r["top_senders"]; als |= r["senders"]
    tot["top_senders"] = len(ts); tot["senders"] = len(als)
    tot["volume_usd"] = tot["volume"] / 1e6; tot["top_volume_usd"] = tot["top_volume"] / 1e6
    print(json.dumps({"start": start, "end_exclusive": end, **{k: v for k, v in tot.items()}}, indent=1))
