import { NextRequest, NextResponse } from "next/server";
import { getUserByDiscordId, upsertUser, type UserStats, type Tx } from "@/lib/users";

/**
 * POST /api/users/sync
 * Called by the Discord bot when a user deposits / withdraws / plays.
 *
 * Body: {
 *   discordId: string,
 *   username: string,
 *   avatar: string | null,   // Discord avatar hash
 *   type: "Deposit" | "Withdraw" | "Play",
 *   amount: number,
 *   balance?: number,
 *   profit?: number,
 *   label?: string
 * }
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { discordId, username, avatar, type, amount, balance, profit, label } = body;

    if (!discordId || !username || !type || amount === undefined) {
      return NextResponse.json(
        { error: "discordId, username, type, amount required" },
        { status: 400 }
      );
    }

    let user = getUserByDiscordId(discordId);
    const now = new Date();
    const dateStr = now.toLocaleString("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });

    const tx: Tx = { type, date: dateStr, amount, label };

    if (!user) {
      user = {
        discordId,
        username,
        avatar: avatar ?? null,
        balance: balance ?? 0,
        profit: profit ?? 0,
        txs: [tx],
        chart: [{ t: dateStr, v: profit ?? 0 }],
      };
    } else {
      user.username = username;
      if (avatar !== undefined) user.avatar = avatar;
      if (balance !== undefined) user.balance = balance;
      if (profit !== undefined) user.profit = profit;
      user.txs.unshift(tx);
      user.chart.push({ t: dateStr, v: user.profit });
    }

    upsertUser(user);

    return NextResponse.json({ ok: true, user: { username: user.username, txs: user.txs.length } });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({ status: "POST discordId, username, avatar, type, amount" });
}
