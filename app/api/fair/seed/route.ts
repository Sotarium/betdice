import { NextResponse } from "next/server";
import { generateServerSeed, hashServerSeed } from "@/lib/fairness";

/**
 * GET /api/fair/seed
 * Returns a new server seed hash (for the bot to show the user before they play).
 * The raw serverSeed is NOT returned — it is only revealed after the roll via /api/fair/roll
 *
 * Optional query: ?client_seed=xxx  (bot can pass the user's client seed)
 */
export async function GET() {
  const serverSeed = generateServerSeed();
  const serverSeedHash = hashServerSeed(serverSeed);

  // In production store serverSeed in DB keyed by a session/roll id
  // For now we return both so the bot can hold it (or store it itself)
  // Better: store in Redis/DB and only return the hash + roll_id

  return NextResponse.json({
    roll_id: serverSeedHash.slice(0, 16), // temporary id
    server_seed_hash: serverSeedHash,
    // TEMP: return seed so bot can use it immediately.
    // Remove this in production and store serverSeed server-side.
    server_seed: serverSeed,
  });
}