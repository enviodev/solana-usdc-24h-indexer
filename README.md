# Solana USDC, 24 hours

A HyperIndex indexer that counts every USDC transfer on Solana over one fixed 24-hour window,
from 12:00 UTC on 15 Nov 2026 to 12:00 UTC on 16 Nov 2026 (slots 469,721,604 to 470,123,644).

It reads `transfer` and `transferChecked` on the SPL Token program, top-level calls and inner
(CPI) calls alike. A plain `transfer` names no mint, so its mint comes from the token balances
the transaction recorded. Rather than a row per transfer it stores rollups:

- `UsdcTotals`: transfers, volume, top-level share, plain vs checked, distinct senders
- `HourlyStat`: transfers and volume per UTC hour
- `SizeBucket`: transfers by size
- `Sender`: one row per authority that signed a USDC transfer

## Run it

```bash
echo "ENVIO_API_TOKEN=<your token>" > .env   # https://envio.dev/app/api-tokens
pnpm install
pnpm codegen
pnpm test
pnpm dev
```

GraphQL is at http://localhost:8080 (local admin secret `testing`):

```graphql
{
  UsdcTotals { transfers volume topLevel topLevelSenders allSenders }
  HourlyStat(order_by: { hour: asc }) { hour transfers volume }
}
```

For a live indexer, set `start_slot: latest` and remove `end_slot` in `config.yaml`.

## Cross-checks

`verify/` holds the scripts we used to check the totals without HyperIndex:

- `hypersync_check.py`: the same count straight from HyperSync
- `hourly_hypersync.py`: hourly counts from HyperSync
- `rpc_spotcheck.py`: whole-slot counts from Solana RPC `getBlock`, compared with HyperSync

Docs: https://docs.envio.dev/docs/HyperIndex/solana
