import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/plisio/deposit
 * Body: { discordId: string, currency?: string }
 * Returns unique permanent deposit address for that user.
 *
 * Plisio docs: GET https://plisio.net/api/v1/shops/deposit/new
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
    const currency = String(body.currency || "USDT_TRX");

    if (!discordId) {
      return NextResponse.json({ error: "discordId required" }, { status: 400 });
    }

    const params = new URLSearchParams({
      api_key: apiKey,
      psys_cid: currency,
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
        { error: data.data?.message || data.message || "Plisio error", raw: data },
        { status: 502 }
      );
    }

    const d = data.data;
    return NextResponse.json({
      address: d.wallet_hash || d.address || d.wallet,
      currency: d.currency || currency,
      qr_code: d.qr_code || null,
      uid: discordId,
      raw: d,
    });
  } catch (e) {
    console.error("[Plisio deposit]", e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "POST { discordId, currency? } — default currency USDT_TRX",
  });
}
