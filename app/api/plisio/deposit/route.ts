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

    const siteUrl =
      process.env.NEXT_PUBLIC_SITE_URL ||
      (process.env.VERCEL_URL
        ? `https://${process.env.VERCEL_URL}`
        : "https://betdice-frouxzys-projects-fcc3f71b.vercel.app");

    const params = new URLSearchParams({
      api_key: apiKey,
      psys_cid: requested,
      uid: discordId,
      callback_url: `${siteUrl}/api/plisio/callback?json=true`,
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

    // Known Plisio minimums (USD) — fallback if API fetch fails
    const KNOWN_MINIMUMS: Record<string, number> = { SOL: 1, LTC: 1 };

    // Try to fetch live min deposit amounts from Plisio
    let minSums: Record<string, number> = {};
    try {
      const currencies = requested.split(",");
      const minFetches = currencies.map((cid) =>
        fetch(
          `https://plisio.net/api/v1/currencies/USD?api_key=${apiKey}&psys_cid=${cid}`
        ).then((r) => r.json())
      );
      const minResults = await Promise.allSettled(minFetches);
      minResults.forEach((result, i) => {
        if (result.status === "fulfilled" && result.value?.data) {
          const cid = currencies[i];
          const d = result.value.data;
          const fetched = parseFloat(d.min_sum_in || d.min_sum || "0");
          minSums[cid] = fetched > 0 ? fetched : (KNOWN_MINIMUMS[cid] ?? 1);
        }
      });
    } catch (_) {
      // Non-fatal: fall back to known minimums
    }

    const addresses = items.map((d: Record<string, string>) => {
      const cid = (d.psys_cid || d.currency || "").toUpperCase();
      return {
        address: d.hash || d.wallet_hash || d.address || d.wallet,
        currency: cid,
        min_sum: minSums[cid] ?? KNOWN_MINIMUMS[cid] ?? 1,
      };
    });

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
