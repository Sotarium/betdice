import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/plisio/withdraw
 * Body: {
 *   secret: string,
 *   currency: "SOL" | "LTC",
 *   to: string,
 *   amount: number // in USD (dices)
 * }
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
    const { secret, currency, to, amount } = body;

    const expectedSecret = process.env.BOT_INTERNAL_SECRET || "betdice_secret";
    if (secret !== expectedSecret) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    if (!currency || !to || !amount || amount <= 0) {
      return NextResponse.json(
        { error: "currency, to, and valid amount are required" },
        { status: 400 }
      );
    }

    const cur = currency.toUpperCase();

    // 1. Fetch current exchange rate to convert USD (dices) -> crypto amount
    let cryptoAmount = amount;
    try {
      const rateRes = await fetch(
        `https://api.plisio.net/api/v1/currencies/USD?api_key=${apiKey}`,
        { method: "GET" }
      );
      const rateData = await rateRes.json();
      if (rateData.status === "success" && Array.isArray(rateData.data)) {
        const coin = rateData.data.find(
          (c: any) => c.currency === cur || c.psys_cid === cur
        );
        if (coin && coin.price_usd && parseFloat(coin.price_usd) > 0) {
          const price = parseFloat(coin.price_usd);
          // e.g. 0.80 USD / 140 USD per SOL = 0.005714 SOL
          cryptoAmount = amount / price;
          // Trim to appropriate decimals (8 decimals standard)
          cryptoAmount = parseFloat(cryptoAmount.toFixed(8));
          console.log(`[Withdraw] ${amount} USD converted to ${cryptoAmount} ${cur} (Rate: $${price})`);
        }
      }
    } catch (e) {
      console.warn("[Withdraw] Rate fetch failed, using original amount:", e);
    }

    const params = new URLSearchParams({
      api_key: apiKey,
      currency: cur,
      to: to.trim(),
      amount: String(cryptoAmount),
      type: "cash_out",
    });

    const res = await fetch(
      `https://plisio.net/api/v1/operations/withdraw?${params.toString()}`,
      { method: "GET" }
    );

    const data = await res.json();

    if (data.status !== "success") {
      console.error("[Plisio withdraw error]", data);
      const errMsg =
        data.data?.message ||
        data.message ||
        JSON.stringify(data.data || data) ||
        "Plisio withdrawal failed";
      return NextResponse.json({ error: errMsg, raw: data }, { status: 502 });
    }

    return NextResponse.json({
      status: "success",
      txn_id: data.data?.txn_id,
      cryptoAmount,
      data: data.data,
    });
  } catch (error: any) {
    console.error("[Withdraw route error]", error);
    return NextResponse.json({ error: error.message || "Internal error" }, { status: 500 });
  }
}
