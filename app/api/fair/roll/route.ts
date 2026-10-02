import { NextRequest, NextResponse } from "next/server";
import { getRollResult, verifyRoll, hashServerSeed } from "@/lib/fairness";

/**
 * POST /api/fair/roll
 * Body: {
 *   server_seed: string,
 *   client_seed: string,
 *   nonce: number,
 *   target?: number,       // optional for under/over logic
 *   direction?: "under" | "over"
 * }
 *
 * Returns the roll result (0–100) so the Discord bot can resolve the game.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { server_seed, client_seed, nonce, target, direction } = body;

    if (!server_seed || !client_seed || nonce === undefined) {
      return NextResponse.json(
        { error: "server_seed, client_seed and nonce are required" },
        { status: 400 }
      );
    }

    const result = getRollResult(server_seed, client_seed, Number(nonce));
    const server_seed_hash = hashServerSeed(server_seed);

    let won: boolean | null = null;
    let multiplier: number | null = null;

    if (typeof target === "number" && (direction === "under" || direction === "over")) {
      won = direction === "under" ? result < target : result > target;
      const winChance = direction === "under" ? target : 100 - target;
      multiplier = winChance > 0 ? +(99 / winChance).toFixed(6) : 0;
    }

    return NextResponse.json({
      result,
      server_seed_hash,
      client_seed,
      nonce: Number(nonce),
      server_seed, // revealed so anyone can verify
      won,
      multiplier,
      verify: verifyRoll(server_seed, client_seed, Number(nonce), result),
    });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}