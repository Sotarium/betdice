import { NextRequest, NextResponse } from "next/server";
import { queueDeposit } from "@/lib/depositQueue";

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

    if (data.status === "completed" && (data.ipn_type === "pay_in" || data.ipn_type === "invoice")) {
      const rawUid = String(data.deposit_uid || data.order_number || "");
      const uid = rawUid.replace(/^v\d+_/, "");
      const amount = parseFloat(data.source_amount || data.amount || "0");
      console.log(`→ Credit user ${uid} with ${amount}`);

      const depositPayload = {
        discordId: String(uid),
        amount: amount,
        currency: data.currency || data.psys_cid || "CRYPTO",
        txid: data.txn_id || data.tx_url || "",
      };

      // 1. Always queue deposit in site memory for bot polling
      queueDeposit(depositPayload);

      // 2. Also try direct POST in case bot URL is set & reachable
      const botUrl = process.env.BOT_INTERNAL_URL || process.env.BOT_URL;
      const botSecret = process.env.BOT_INTERNAL_SECRET || "betdice_secret";

      if (botUrl && uid) {
        try {
          const forwardRes = await fetch(`${botUrl.replace(/\/$/, "")}/deposit-credit`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${botSecret}`,
            },
            body: JSON.stringify(depositPayload),
          });
          const resData = await forwardRes.json().catch(() => ({}));
          console.log("[Bot forward response]", forwardRes.status, resData);
        } catch (botErr) {
          console.error("[Bot forward error] Failed to reach direct bot listener:", botErr);
        }
      }
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