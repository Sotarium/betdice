import { NextRequest, NextResponse } from "next/server";
import { getPendingDeposits, removePendingDeposit } from "@/lib/depositQueue";

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

  const queue = getPendingDeposits();
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
    if (id) {
      removePendingDeposit(id);
    }
    return NextResponse.json({ status: "acknowledged" });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
}
