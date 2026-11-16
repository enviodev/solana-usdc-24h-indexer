"""Third check: count USDC transfer instructions in a few whole slots straight from Solana RPC
(getBlock, jsonParsed), and compare with the HyperSync count for the same slots.
A plain `transfer` is USDC when its source or destination token account holds USDC in the
transaction's pre/post token balances; `transferChecked` names the mint.
Usage: python3 rpc_spotcheck.py SLOT [SLOT...]
"""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from hypersync_check import scan
RPC = "https://api.mainnet.solana.com"
SPL = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

def rpc(m, p):
    for a in range(10):
        try:
            r = urllib.request.Request(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), {"content-type": "application/json"})
            d = json.load(urllib.request.urlopen(r, timeout=60))
            if "error" in d and d["error"].get("code") == 429: raise Exception("429")
            return d
        except Exception:
            time.sleep(4 * (a + 1))

for s in map(int, sys.argv[1:]):
    d = rpc("getBlock", [s, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "transactionDetails": "full", "rewards": False}])
    blk = d.get("result")
    n = vol = 0
    for tx in (blk or {}).get("transactions", []):
        meta = tx["meta"]
        if meta.get("err") is not None: continue
        keys = [k["pubkey"] for k in tx["transaction"]["message"]["accountKeys"]]
        keys += (meta.get("loadedAddresses") or {}).get("writable", []) + (meta.get("loadedAddresses") or {}).get("readonly", [])
        usdc = {keys[b["accountIndex"]] for b in (meta.get("preTokenBalances") or []) + (meta.get("postTokenBalances") or []) if b["mint"] == USDC}
        ixs = list(tx["transaction"]["message"]["instructions"])
        for inner in meta.get("innerInstructions") or []: ixs += inner["instructions"]
        for ix in ixs:
            if ix.get("programId") != SPL or not isinstance(ix.get("parsed"), dict): continue
            t, info = ix["parsed"]["type"], ix["parsed"]["info"]
            if t == "transferChecked" and info.get("mint") == USDC:
                n += 1; vol += int(info["tokenAmount"]["amount"])
            elif t == "transfer" and (info["source"] in usdc or info["destination"] in usdc):
                n += 1; vol += int(info["amount"])
    hs = scan((s, s + 1))
    print(f"slot {s}: RPC {n} transfers ${vol/1e6:,.2f} | HyperSync {hs['transfers']} transfers ${hs['volume']/1e6:,.2f} | {'MATCH' if n == hs['transfers'] and vol == hs['volume'] else 'DIFF'}")
