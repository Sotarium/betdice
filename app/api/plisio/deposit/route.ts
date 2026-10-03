import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/plisio/deposit
 * Body: { discordId: string, currency?: "SOL" | "LTC" }
 * Default: both SOL and LTC addresses returned.
 *
 * Plisio: GET https://plisio.net/api/v1/shops/deposit/new
 * Requires White-label + wallets enabled on Plisio.
 */
export async function POST(req: NextRequest) {
  try {
    const apiKey = process.env.PLISIO_SECRET_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "PLISIO_SECRET_KEY not set on Vercel" },
        { status: 500 }
      );
    }

    const body = await req.json();
    const discordId = String(body.discordId || "");
    // Single currency or both
    const requested = body.currency
      ? String(body.currency).toUpperCase()
      : "SOL,LTC";

    if (!discordId) {
      return NextResponse.json({ error: "discordId required" }, { status: 400 });
    }

    const params = new URLSearchParams({
      api_key: apiKey,
      psys_cid: requested,
      uid: discordId,
    });

    const res = await fetch(
      `https://plisio.net/api/v1/shops/deposit/new?${params.toString()}`,
      { method: "GET" }
    );

    const data = await res.json();

    if (data.status !== "success" || !data.data) {
      console.error("[Plisio deposit error]", data);
      return NextResponse.json(
        {
          error:
            data.data?.message ||
            data.message ||
            JSON.stringify(data.data || data) ||
            "Plisio error",
          raw: data,
        },
        { status: 502 }
      );
    }

    // Single object or array
    const items = Array.isArray(data.data) ? data.data : [data.data];

    const addresses = items.map((d: Record<string, string>) => ({
      address: d.hash || d.wallet_hash || d.address || d.wallet,
      currency: d.psys_cid || d.currency,
    }));

    // Keep backward-compatible single fields (first address)
    const first = addresses[0] || {};

    return NextResponse.json({
      address: first.address,
      currency: first.currency,
      addresses,
      uid: discordId,
    });
  } catch (e) {
    console.error("[Plisio deposit]", e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: 'POST { discordId, currency?: "SOL" | "LTC" } — default both',
  });
}
