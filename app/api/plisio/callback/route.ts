import { NextRequest, NextResponse } from "next/server";

/**
 * Plisio webhook endpoint
 * Set in Plisio dashboard as Status URL:
 * https://your-domain.vercel.app/api/plisio/callback?json=true
 *
 * For deposits (pay_in) Plisio sends:
 * - deposit_uid  (your user id)
 * - amount / source_amount
 * - status = completed
 * - verify_hash
 */
export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") || "";
    let data: any;

    if (contentType.includes("application/json")) {
      data = await req.json();
    } else {
      // form-data fallback
      const form = await req.formData();
      data = Object.fromEntries(form.entries());
    }

    console.log("[Plisio callback]", data);

    // TODO: verify verify_hash with your PLISIO_SECRET_KEY
    // TODO: map deposit_uid → Discord user id and credit balance in DB

    if (data.status === "completed" && data.ipn_type === "pay_in") {
      const uid = data.deposit_uid;
      const amount = parseFloat(data.source_amount || data.amount || "0");
      console.log(`Credit user ${uid} with ${amount}`);
      // add_balance(uid, amount)  ← connect to your real DB here
    }

    return NextResponse.json({ status: "ok" });
  } catch (e) {
    console.error("[Plisio callback error]", e);
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }
}

// Plisio sometimes does GET for testing
export async function GET() {
  return NextResponse.json({ status: "Plisio callback endpoint ready" });
}