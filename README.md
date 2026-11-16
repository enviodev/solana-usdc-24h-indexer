# Every USDC transfer on Solana, 24 hours

A [HyperIndex](https://docs.envio.dev/docs/HyperIndex/solana) indexer that counts every USDC transfer on Solana over one day, inner transfers included.

In the 24 hours from 12:00 UTC on 15 Nov 2026 to 12:00 UTC on 16 Nov 2026 (Solana Breakpoint day 1), USDC moved **11.3M times** on Solana. **78% of those transfers (8.78M) happened inside another program**, such as a swap, a lending market or a router, rather than as a top-level instruction someone signed directly.

| | Count |
| --- | --- |
| USDC transfers | 11,258,884 |
| Top-level transfers | 2,475,147 |
| Inner (CPI) transfers | 8,783,737 (78%) |
| Slots covered | 469,721,604 to 470,123,644 |

## Why inner transfers matter

Most USDC on Solana moves as a side effect of another program. A Jupiter swap, a lending deposit or a payment router calls the SPL Token program for you, and that transfer only shows up as an inner instruction. Read only top-level instructions and you see about 1 in 5 USDC transfers.

This indexer reads `transfer` and `transferChecked` on the [SPL Token program](https://spl.solana.com/token) (`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`) at every depth. `transferChecked` names its mint. A plain `transfer` doesn't, so the handler works out the mint from the token balances the transaction recorded and keeps it only when it's [USDC](https://developers.circle.com/stablecoins/usdc-contract-addresses) (`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`).

## What it stores

Rollups rather than a row per transfer, so the whole day fits in a small database:

- `UsdcTotals`: transfers, volume, top-level share, plain vs checked, distinct senders
- `HourlyStat`: transfers and volume per UTC hour
- `SizeBucket`: transfers by size
- `Sender`: one row per authority that signed a USDC transfer

Volume adds up every transfer, so a swap routed through several pools counts each leg.

## Run it

You need Node 22+, pnpm and Docker, plus a free Envio API token from [envio.dev/app/api-tokens](https://envio.dev/app/api-tokens).

```bash
cp .env.example .env   # then paste your token into ENVIO_API_TOKEN
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

### Make it live

To follow Solana in real time instead of one fixed day, set `start_slot: latest` and remove `end_slot` in `config.yaml`.

### Deploy it

Push your fork to GitHub and deploy it on [Envio Cloud](https://docs.envio.dev/docs/HyperIndex/hosted-service) to get a hosted GraphQL endpoint.

## Check the numbers yourself

`verify/` has the scripts we used to check the totals without HyperIndex:

- `hypersync_check.py`: the same count straight from HyperSync's [Solana endpoint](https://docs.envio.dev/docs/HyperSync/solana-client) (needs `ENVIO_API_TOKEN`)
- `hourly_hypersync.py`: hourly counts from HyperSync, which add up to the same total
- `rpc_spotcheck.py`: whole-slot counts from public Solana RPC [`getBlock`](https://solana.com/docs/rpc/http/getblock), compared slot by slot with HyperSync

HyperSync counts 11,258,900 transfers for the window, 16 more than the indexer. All 16 are top-level, and they don't change the totals above at the precision we publish.

## Build your own with an AI agent

This repo ships with Envio's agent skills in `.claude/skills/`, so Claude Code, Cursor or any coding agent can work on it with the docs in context. Paste a prompt like this into your agent from the repo root:

```text
This is an Envio HyperIndex indexer for Solana (ecosystem: svm). Read README.md,
config.yaml, schema.graphql, src/handlers/SplToken.ts and the skills in .claude/skills,
then the Solana docs at https://docs.envio.dev/docs/HyperIndex/solana.

Change it to track <STABLECOIN> (mint <MINT ADDRESS>) instead of USDC, live from
the latest slot. Keep inner (CPI) transfers. Add a daily rollup next to the hourly
one. Update the tests in src/indexer.test.ts, run `pnpm codegen` and `pnpm test`
until they pass, then run `pnpm dev` and show me the GraphQL query for today's totals.
```

Swap in PYUSD, USDG, USDT or any SPL token. For tokens on the newer Token-2022 program, ask the agent to add that program as well.

## Links

- [Indexing Solana with HyperIndex](https://docs.envio.dev/docs/HyperIndex/solana)
- [Getting started on Solana](https://docs.envio.dev/docs/HyperIndex/solana/getting-started)
- [Instruction handlers](https://docs.envio.dev/docs/HyperIndex/solana/instruction-handlers)
- [HyperSync Solana client](https://docs.envio.dev/docs/HyperSync/solana-client)
- [Circle USDC addresses](https://developers.circle.com/stablecoins/usdc-contract-addresses)
- [SPL Token program](https://spl.solana.com/token)
- [Envio Discord](https://discord.gg/envio)
