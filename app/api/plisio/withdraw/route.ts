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

    // 1. Check actual Plisio wallet balance
    let actualWalletBalance = 0;
    try {
      const balRes = await fetch(
        `https://api.plisio.net/api/v1/balances/${cur}?api_key=${apiKey}`,
        { method: "GET" }
      );
      const balData = await balRes.json();
      if (balData.status === "success" && balData.data?.balance) {
        actualWalletBalance = parseFloat(balData.data.balance);
      }
    } catch (e) {
      console.warn("[Withdraw] Balance check error:", e);
    }

    // 2. Fetch current exchange rate to convert USD (dices) -> crypto amount
    let cryptoAmount = amount;
    let coinPrice = 1;
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
          coinPrice = parseFloat(coin.price_usd);
          cryptoAmount = amount / coinPrice;
          // Trim to 6 decimal places for blockchain safety
          cryptoAmount = parseFloat(cryptoAmount.toFixed(6));
        }
      }
    } catch (e) {
      console.warn("[Withdraw] Rate fetch failed:", e);
    }

    // If requested crypto amount exceeds available balance (including network fee buffer)
    if (actualWalletBalance > 0 && cryptoAmount > actualWalletBalance) {
      const availableUsd = (actualWalletBalance * coinPrice).toFixed(2);
      return NextResponse.json(
        {
          error: `Insufficient hot-wallet balance on Plisio. Available: ${actualWalletBalance.toFixed(6)} ${cur} (~$${availableUsd} USD). Requested: ${cryptoAmount.toFixed(6)} ${cur} ($${amount.toFixed(2)} USD).`,
        },
        { status: 400 }
      );
    }

    const params = new URLSearchParams({
      api_key: apiKey,
      currency: cur,
      to: to.trim(),
      amount: String(cryptoAmount),
      feePlan: "normal",
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
