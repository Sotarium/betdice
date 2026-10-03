import { NextRequest, NextResponse } from "next/server";

// In-memory queue of pending deposits waiting for the bot to fetch & credit
interface PendingDeposit {
  id: string;
  discordId: string;
  amount: number;
  currency: string;
  txid: string;
  createdAt: number;
}

declare global {
  var _pendingDeposits: PendingDeposit[] | undefined;
}

if (!global._pendingDeposits) {
  global._pendingDeposits = [];
}

/**
 * GET /api/plisio/pending-deposits
 * Called by the Discord bot to fetch and claim uncredited deposits.
 */
export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization") || "";
  const expectedSecret = process.env.BOT_INTERNAL_SECRET || "betdice_secret";
  if (authHeader !== `Bearer ${expectedSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const queue = global._pendingDeposits || [];
  return NextResponse.json({ deposits: queue });
}

/**
 * POST /api/plisio/pending-deposits
 * Called by the Discord bot to mark a deposit as credited / remove from queue.
 * Body: { id: string }
 */
export async function POST(req: NextRequest) {
  const authHeader = req.headers.get("authorization") || "";
  const expectedSecret = process.env.BOT_INTERNAL_SECRET || "betdice_secret";
  if (authHeader !== `Bearer ${expectedSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const { id } = await req.json();
    if (global._pendingDeposits && id) {
      global._pendingDeposits = global._pendingDeposits.filter((d) => d.id !== id);
    }
    return NextResponse.json({ status: "acknowledged" });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
}

/**
 * Helper used by callback route to enqueue a deposit
 */
export function queueDeposit(deposit: Omit<PendingDeposit, "id" | "createdAt">) {
  if (!global._pendingDeposits) {
    global._pendingDeposits = [];
  }
  const id = `${deposit.discordId}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
  global._pendingDeposits.push({
    ...deposit,
    id,
    createdAt: Date.now(),
  });
  console.log(`[Pending Deposits] Queued deposit ${id} for user ${deposit.discordId}: ${deposit.amount}`);
  return id;
}
