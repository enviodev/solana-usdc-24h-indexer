import { describe, it } from "vitest";
import { createTestIndexer } from "envio";

// `start_slot` from config.yaml. Simulated instructions only run inside the configured range.
const START_SLOT = 469_721_604;
const SOLANA = 7565164;

const USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const WSOL = "So11111111111111111111111111111111111111112";
const SOURCE = "3emsAVdmGKERbHjmGfQ6oZ1e35dkf5z6TmFZBrwMiWmC";
const DESTINATION = "7VHUFJHWu2CuExkJcJrzhQPJ2oygupTWkL2A2For4BmE";
const WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM";
const POOL = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1";
const TIME = 1_794_744_000; // 15 Nov 2026 12:00 UTC

describe("USDC on Solana, rolled up", () => {
  it("counts top-level and inner transfers, senders and size buckets, and drops other mints", async (t) => {
    const indexer = createTestIndexer();
    const checked = (authority: string, amount: bigint, path: number[], transactionIndex: number) => ({
      program: "SplToken" as const,
      instruction: "transferChecked" as const,
      slot: START_SLOT,
      path,
      args: { amount, decimals: 6 },
      accounts: {
        source: { address: SOURCE },
        mint: { address: USDC },
        destination: { address: DESTINATION },
        authority: { address: authority },
      },
      block: { time: TIME },
      transaction: { transactionIndex, success: true },
    });
    const plain = (mint: string, transactionIndex: number) => ({
      program: "SplToken" as const,
      instruction: "transfer" as const,
      slot: START_SLOT,
      path: [0],
      args: { amount: 50_000_000n },
      accounts: {
        source: { address: SOURCE },
        destination: { address: DESTINATION },
        authority: { address: WALLET },
      },
      block: { time: TIME },
      transaction: { transactionIndex, success: true, accountActivities: [{ address: DESTINATION, token: { mint } }] },
    });

    await indexer.process({
      chains: {
        [SOLANA]: {
          simulate: [
            checked(WALLET, 250_000n, [0], 0), // $0.25 sent by a wallet
            checked(POOL, 2_000_000_000n, [1, 0], 1), // $2,000 inside a swap
            plain(USDC, 2), // $50 plain transfer, mint from balances
            plain(WSOL, 3), // not USDC, dropped
          ],
        },
      },
    });

    const totals = await indexer.UsdcTotals.get("USDC");
    t.expect(totals?.transfers).toBe(3n);
    t.expect(totals?.topLevel).toBe(2n);
    t.expect(totals?.volume).toBe(2_050_250_000n);
    t.expect(totals?.plainTransfers).toBe(1n);
    t.expect(totals?.topLevelSenders).toBe(1n);
    t.expect(totals?.allSenders).toBe(2n);
    const buckets = await indexer.SizeBucket.getAll();
    t.expect(buckets.map((b) => [b.id, b.transfers]).sort()).toEqual([
      ["a: under $1", 1n],
      ["b: $1 to $100", 1n],
      ["c: $100 to $10K", 1n],
    ]);
  });
});
