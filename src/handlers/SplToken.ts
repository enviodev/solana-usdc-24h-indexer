import { indexer, type SvmInstruction } from "envio";

/** USD Coin on Solana (Circle's published mint). */
const MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const DOLLAR = 1_000_000n;

/** Only the listed fields are fetched, so keep it to what the handlers read. */
const fields = {
  instruction: ["accounts", "args", "path"],
  transaction: ["success"],
  accountActivity: ["token.mint"],
  block: ["time"],
} as const;

type TokenTransfer =
  | SvmInstruction<typeof fields, "SplToken", "transfer">
  | SvmInstruction<typeof fields, "SplToken", "transferChecked">;

const bucketOf = (a: bigint) =>
  a < DOLLAR ? "a: under $1"
  : a < 100n * DOLLAR ? "b: $1 to $100"
  : a < 10_000n * DOLLAR ? "c: $100 to $10K"
  : a < 1_000_000n * DOLLAR ? "d: $10K to $1M"
  : "e: $1M and over";

async function record(instruction: TokenTransfer, context: any, checked: boolean) {
  const totals = await context.UsdcTotals.getOrCreate({
    id: "USDC", transfers: 0n, volume: 0n, topLevel: 0n, topLevelVolume: 0n,
    plainTransfers: 0n, checkedTransfers: 0n, failedSkipped: 0n,
    topLevelSenders: 0n, allSenders: 0n,
    firstSlot: instruction.block.slot, lastSlot: instruction.block.slot,
    firstTime: instruction.block.time, lastTime: instruction.block.time,
  });
  if (instruction.transaction.success === false) {
    context.UsdcTotals.set({ ...totals, failedSkipped: totals.failedSkipped + 1n });
    return;
  }
  const amount = instruction.args.amount;
  const top = instruction.path.length === 1;
  const authority = instruction.accounts.authority.address;
  const hour = Math.floor(instruction.block.time / 3600);
  const bucket = bucketOf(amount);

  const [sender, hourly, size] = await Promise.all([
    context.Sender.get(authority),
    context.HourlyStat.getOrCreate({ id: String(hour), hour, transfers: 0, topLevel: 0, volume: 0n }),
    context.SizeBucket.getOrCreate({ id: bucket, transfers: 0n, topLevel: 0n, volume: 0n }),
  ]);
  const newSender = sender === undefined;
  const newTopSender = top && (newSender || sender.topLevel === 0);
  context.Sender.set({
    id: authority,
    transfers: (sender?.transfers ?? 0) + 1,
    topLevel: (sender?.topLevel ?? 0) + (top ? 1 : 0),
  });
  context.HourlyStat.set({
    ...hourly, transfers: hourly.transfers + 1, topLevel: hourly.topLevel + (top ? 1 : 0), volume: hourly.volume + amount,
  });
  context.SizeBucket.set({
    ...size, transfers: size.transfers + 1n, topLevel: size.topLevel + (top ? 1n : 0n), volume: size.volume + amount,
  });
  context.UsdcTotals.set({
    ...totals,
    transfers: totals.transfers + 1n,
    volume: totals.volume + amount,
    topLevel: totals.topLevel + (top ? 1n : 0n),
    topLevelVolume: totals.topLevelVolume + (top ? amount : 0n),
    plainTransfers: totals.plainTransfers + (checked ? 0n : 1n),
    checkedTransfers: totals.checkedTransfers + (checked ? 1n : 0n),
    allSenders: totals.allSenders + (newSender ? 1n : 0n),
    topLevelSenders: totals.topLevelSenders + (newTopSender ? 1n : 0n),
    firstSlot: Math.min(totals.firstSlot, instruction.block.slot),
    lastSlot: Math.max(totals.lastSlot, instruction.block.slot),
    firstTime: Math.min(totals.firstTime, instruction.block.time),
    lastTime: Math.max(totals.lastTime, instruction.block.time),
  });
}

// `transferChecked` names its mint, so `where` filters server-side.
indexer.onInstruction(
  { program: "SplToken", instruction: "transferChecked", fields, where: { accounts: { mint: MINT } } },
  async ({ instruction, context }) => {
    await record(instruction, context, true);
  },
);

// Plain `transfer` names no mint, so it comes from the token balances that
// `fields.accountActivity` joins onto the accounts.
indexer.onInstruction(
  { program: "SplToken", instruction: "transfer", fields },
  async ({ instruction, context }) => {
    const { source, destination } = instruction.accounts;
    if (source.activity?.token?.mint !== MINT && destination.activity?.token?.mint !== MINT) return;
    await record(instruction, context, false);
  },
);
