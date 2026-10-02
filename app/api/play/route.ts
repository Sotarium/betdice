import { NextRequest, NextResponse } from "next/server";
import {
  generateServerSeed,
  hashServerSeed,
  getRollResult,
} from "@/lib/fairness";

// In-memory store for demo (replace with real DB later)
const sessions = new Map<
  string,
  { serverSeed: string; serverSeedHash: string; nonce: number }
>();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { bet, target, direction, clientSeed, balance } = body;

    if (!bet || bet <= 0) {
      return NextResponse.json({ error: "Invalid bet" }, { status: 400 });
    }
    if (bet > balance) {
      return NextResponse.json({ error: "Insufficient balance" }, { status: 400 });
    }
    if (target < 1 || target > 95) {
      return NextResponse.json({ error: "Invalid target" }, { status: 400 });
    }
    if (!clientSeed) {
      return NextResponse.json({ error: "Client seed required" }, { status: 400 });
    }

    // Demo session key – production: use Discord user id from auth
    const sessionKey = "demo-user";

    let session = sessions.get(sessionKey);
    if (!session) {
      const serverSeed = generateServerSeed();
      session = {
        serverSeed,
        serverSeedHash: hashServerSeed(serverSeed),
        nonce: 0,
      };
      sessions.set(sessionKey, session);
    }

    const result = getRollResult(
      session.serverSeed,
      clientSeed,
      session.nonce
    );

    const won =
      direction === "under" ? result < target : result > target;

    const winChance = direction === "under" ? target : 100 - target;
    const multiplier = 99 / winChance; // ~1% house edge
    const payout = won ? +(bet * multiplier).toFixed(2) : 0;

    // Reveal server seed for this roll (next roll gets a new one in production)
    const revealedSeed = session.serverSeed;

    // Rotate seed for next roll (more secure)
    const newServerSeed = generateServerSeed();
    sessions.set(sessionKey, {
      serverSeed: newServerSeed,
      serverSeedHash: hashServerSeed(newServerSeed),
      nonce: session.nonce + 1,
    });

    return NextResponse.json({
      result,
      won,
      payout,
      target,
      direction,
      serverSeedHash: session.serverSeedHash,
      clientSeed,
      nonce: session.nonce,
      serverSeed: revealedSeed, // revealed so user can verify
    });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}