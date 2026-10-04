import { NextRequest, NextResponse } from "next/server";
import { getUserByUsername, getUserByDiscordId, avatarUrl } from "@/lib/users";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const userParam = searchParams.get("user") || "sotarium";

  // Try to find user by username or discordId
  let user = getUserByUsername(userParam) || getUserByDiscordId(userParam);

  if (!user) {
    return NextResponse.json({
      username: userParam,
      avatar: "https://rollbux.com/icons/token.png",
      total_earnings_bux: 0,
      total_earnings_usd: 0,
      earnings_24h_bux: 0,
      earnings_24h_usd: 0,
      current_balance_bux: 0,
      history: [],
      chart_points: [0, 0],
      chart_labels: ["7:00 PM", "8:00 PM"],
    });
  }

  const avatar = avatarUrl(user.discordId, user.avatar, 256);
  const totalBux = user.profit / 0.002;
  const balanceBux = user.balance / 0.002;

  // Prefer raw history from bot profit_refresh sync if available
  let history;
  if (user.history && user.history.length > 0) {
    history = user.history.map((t) => ({
      amount_usd: t.amount,
      amount_bux: t.amount / 0.002,
      when: t.when,
      time: String(t.when).split(",")[1]?.trim() || t.when,
      timestamp_ms: t.timestamp_ms,
      type: t.type,
      balance_after: t.balance_after,
    }));
  } else {
    history = (user.txs || []).map((t, idx) => ({
      amount_usd: t.amount,
      amount_bux: t.amount / 0.002,
      when: t.date,
      time: t.date.split(",")[1]?.trim() || t.date,
      timestamp_ms: Date.now() - idx * 60000,
      type: t.type,
      label: t.label,
    }));
  }

  // Prefer explicit chart_points/chart_labels from bot sync
  const chartLabels = user.chart_labels && user.chart_labels.length
    ? user.chart_labels
    : (user.chart && user.chart.length ? user.chart.map((c) => c.t) : ["7:00 PM", "8:00 PM"]);
  const chartPoints = user.chart_points && user.chart_points.length
    ? user.chart_points
    : (user.chart && user.chart.length ? user.chart.map((c) => Number(c.v.toFixed(2))) : [0, 0]);

  return NextResponse.json({
    username: user.username,
    avatar: avatar,
    total_earnings_bux: totalBux,
    total_earnings_usd: user.profit,
    earnings_24h_bux: totalBux,
    earnings_24h_usd: user.profit,
    current_balance_bux: balanceBux,
    history: history,
    chart_points: chartPoints,
    chart_labels: chartLabels,
  });
}

