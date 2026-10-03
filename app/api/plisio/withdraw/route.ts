import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/plisio/withdraw
 * Body: {
 *   secret: string,
 *   currency: "SOL" | "LTC",
 *   to: string,
 *   amount: number // in USD or currency depending on plisio config, or dice amount
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

    const params = new URLSearchParams({
      api_key: apiKey,
      currency: currency.toUpperCase(),
      to: to.trim(),
      amount: String(amount),
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
      data: data.data,
    });
  } catch (error: any) {
    console.error("[Withdraw route error]", error);
    return NextResponse.json({ error: error.message || "Internal error" }, { status: 500 });
  }
}
