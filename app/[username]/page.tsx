import { notFound } from "next/navigation";
import Link from "next/link";
import { getUser } from "@/lib/users";

export default function UserProfilePage({
  params,
}: {
  params: { username: string };
}) {
  const user = getUser(params.username);
  if (!user) notFound();

  // Simple SVG sparkline from chart data
  const points = user.chart;
  const maxV = Math.max(...points.map((p) => p.v), 0.01);
  const minV = Math.min(...points.map((p) => p.v), 0);
  const range = maxV - minV || 1;
  const w = 320;
  const h = 120;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1 || 1)) * w;
      const y = h - ((p.v - minV) / range) * (h - 8) - 4;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#0d0e12",
        color: "#e4e4e7",
        fontFamily: "system-ui, -apple-system, sans-serif",
        padding: "32px 24px",
      }}
    >
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        <Link
          href="/users"
          style={{ color: "#71717a", fontSize: 13, textDecoration: "none" }}
        >
          ← users
        </Link>

        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            marginTop: 20,
            marginBottom: 28,
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              background: "#1f2028",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22,
            }}
          >
            👁
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 16 }}>{user.username}</div>
            <div style={{ color: "#71717a", fontSize: 13 }}>{user.username}</div>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 20,
          }}
        >
          {/* Left: balance + chart */}
          <div
            style={{
              background: "#16171d",
              borderRadius: 12,
              padding: 20,
              border: "1px solid #1f2028",
            }}
          >
            <div style={{ fontSize: 28, fontWeight: 700 }}>
              ${user.balance.toFixed(2)}
            </div>
            <div style={{ color: "#22c55e", fontSize: 13, marginBottom: 16 }}>
              +${user.profit.toFixed(2)} · 5:00 PM
            </div>

            {/* Time range pills */}
            <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
              {["24H", "7D", "30D", "ALL"].map((r, i) => (
                <span
                  key={r}
                  style={{
                    fontSize: 11,
                    padding: "4px 8px",
                    borderRadius: 6,
                    background: i === 0 ? "#1f2028" : "transparent",
                    color: i === 0 ? "#e4e4e7" : "#71717a",
                  }}
                >
                  {r}
                </span>
              ))}
            </div>

            <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{ display: "block" }}>
              <path
                d={path}
                fill="none"
                stroke="#22c55e"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>

            <div
              style={{
                marginTop: 16,
                display: "flex",
                alignItems: "center",
                gap: 8,
                color: "#a1a1aa",
                fontSize: 13,
              }}
            >
              <span
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: "#1f2028",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                }}
              >
                $
              </span>
              Profit +${user.profit.toFixed(2)}
            </div>
          </div>

          {/* Right: rain / tx log */}
          <div
            style={{
              background: "#16171d",
              borderRadius: 12,
              padding: 20,
              border: "1px solid #1f2028",
            }}
          >
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              {["All rain", "1D Rain", "1 Week Rains"].map((t, i) => (
                <span
                  key={t}
                  style={{
                    fontSize: 12,
                    padding: "6px 10px",
                    borderRadius: 8,
                    background: i === 2 ? "#1f2028" : "transparent",
                    color: i === 2 ? "#e4e4e7" : "#71717a",
                  }}
                >
                  {t}
                </span>
              ))}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                fontSize: 11,
                color: "#71717a",
                marginBottom: 10,
                padding: "0 4px",
              }}
            >
              <span>TYPE</span>
              <span>DATE</span>
              <span style={{ textAlign: "right" }}>AMOUNT</span>
            </div>

            {user.txs.map((tx, i) => (
              <div
                key={i}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  alignItems: "center",
                  padding: "10px 8px",
                  borderRadius: 8,
                  background: i % 2 === 0 ? "#12131a" : "transparent",
                  fontSize: 13,
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 6,
                      background: "#1f2028",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12,
                    }}
                  >
                    {tx.type === "Deposit" ? "↓" : tx.type === "Withdraw" ? "↑" : "🎲"}
                  </span>
                  {tx.type}
                </span>
                <span style={{ color: "#a1a1aa" }}>{tx.date}</span>
                <span style={{ textAlign: "right", fontWeight: 500 }}>
                  ${Math.abs(tx.amount).toFixed(2)}
                </span>
              </div>
            ))}

            {user.txs.length === 0 && (
              <p style={{ color: "#71717a", fontSize: 13, marginTop: 12 }}>
                No transactions yet.
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
