import { NextRequest, NextResponse } from "next/server";
import { getRollResult, verifyRoll } from "@/lib/fairness";

/**
 * POST /api/fair/verify
 * Anyone can call this to check a past roll was fair.
 * Body: { server_seed, client_seed, nonce, claimed_result }
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { server_seed, client_seed, nonce, claimed_result } = body;

    if (!server_seed || !client_seed || nonce === undefined || claimed_result === undefined) {
      return NextResponse.json(
        { error: "server_seed, client_seed, nonce, claimed_result required" },
        { status: 400 }
      );
    }

    const actual = getRollResult(server_seed, client_seed, Number(nonce));
    const valid = verifyRoll(server_seed, client_seed, Number(nonce), Number(claimed_result));

    return NextResponse.json({
      valid,
      actual_result: actual,
      claimed_result: Number(claimed_result),
    });
  } catch (e) {
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}