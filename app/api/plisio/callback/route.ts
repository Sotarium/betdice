import { NextRequest, NextResponse } from "next/server";

/**
 * Plisio webhook – set Status URL in Plisio dashboard to:
 * https://betdice.vercel.app/api/plisio/callback?json=true
 */
export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") || "";
    let data: Record<string, any>;

    if (contentType.includes("application/json")) {
      data = await req.json();
    } else {
      const form = await req.formData();
      data = Object.fromEntries(form.entries());
    }

    console.log("[Plisio callback]", JSON.stringify(data));

    // TODO: verify data.verify_hash with PLISIO_SECRET_KEY
    // TODO: credit Discord user (data.deposit_uid) in your real DB / notify the bot

    if (data.status === "completed" && (data.ipn_type === "pay_in" || data.ipn_type === "invoice")) {
      const uid = data.deposit_uid || data.order_number;
      const amount = parseFloat(data.source_amount || data.amount || "0");
      console.log(`→ Credit user ${uid} with ${amount}`);
    }

    return NextResponse.json({ status: "ok" });
  } catch (e) {
    console.error("[Plisio callback error]", e);
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }
}

export async function GET() {
  return NextResponse.json({ status: "Plisio callback endpoint ready" });
}