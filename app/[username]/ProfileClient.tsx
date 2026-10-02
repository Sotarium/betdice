"use client";

import { useEffect, useRef, useState } from "react";
import type { UserStats } from "@/lib/users";

export default function ProfileClient({
  user,
  avatar,
}: {
  user: UserStats;
  avatar: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [timeframe, setTimeframe] = useState("1D");
  const [rainTab, setRainTab] = useState("1d");

  const main = Math.floor(user.balance);
  const sub = (user.balance % 1).toFixed(2).slice(1); // ".xx"

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    const points = user.chart.length
      ? user.chart
      : [
          { t: "", v: 0 },
          { t: "", v: user.profit || 0 },
        ];
    const maxV = Math.max(...points.map((p) => p.v), 0.01);
    const minV = Math.min(...points.map((p) => p.v), 0);
    const range = maxV - minV || 1;

    ctx.clearRect(0, 0, w, h);
    ctx.beginPath();
    ctx.strokeStyle = "rgb(33, 201, 94)";
    ctx.lineWidth = 2.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    points.forEach((p, i) => {
      const x = (i / (points.length - 1 || 1)) * w;
      const y = h - ((p.v - minV) / range) * (h - 16) - 8;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }, [user.chart, user.profit]);

  return (
    <div className="fomo-page">
      {/* Banner */}
      <div className="fomo-banner">
        <div className="currency-toggle-wrapper">
          <div className="fomo-currency-segmented">
            <div className="currency-slider-pill" />
            <button className="curr-pill-btn active" type="button">
              <span className="curr-label">USD</span>
            </button>
            <button className="curr-pill-btn" type="button">
              <span className="curr-label">BUX</span>
            </button>
          </div>
        </div>
      </div>

      {/* Profile */}
      <div className="fomo-profile-row">
        <div className="fomo-avatar-circle">
          <img className="fomo-avatar-img" src={avatar} alt={user.username} />
        </div>
        <div className="fomo-user-meta">
          <div className="fomo-user-name">{user.username}</div>
          <div className="fomo-user-handle">@{user.username}</div>
        </div>
      </div>

      {/* Grid */}
      <div className="fomo-grid">
        <div className="fomo-left-col">
          <div className="fomo-chart-header">
            <div className="fomo-balance-box">
              <div className="fomo-balance-val">
                <span className="val-main">${main}</span>
                <span className="val-sub">{sub}</span>
              </div>
              <div className="fomo-balance-sub">
                <span className="pnl-green">
                  {user.profit >= 0 ? "+" : ""}${user.profit.toFixed(2)}
                </span>
                <span className="pnl-period">{timeframe === "1D" ? "24h" : timeframe}</span>
              </div>
            </div>
            <div className="time-seg">
              <div className="time-seg-slider" />
              {["1D", "1W", "1M", "ALL"].map((t) => (
                <button
                  key={t}
                  className={`time-seg-btn${timeframe === t ? " active" : ""}`}
                  type="button"
                  onClick={() => setTimeframe(t)}
                >
                  {t === "ALL" ? "All" : t}
                </button>
              ))}
            </div>
          </div>

          <div className="fomo-chart-wrap">
            <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} />
          </div>

          <div className="fomo-cash-card">
            <div className="glass-round">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 5 10" fill="none">
                <path
                  d="M4.86208 6.6257C4.86208 5.65202 4.20146 4.80474 3.25354 4.56412L1.84576 4.21508C1.5925 4.15091 1.37472 4.00893 1.21333 3.80136C1.05826 3.60546 0.972704 3.35514 0.972704 3.09653C0.972704 2.46118 1.48945 1.94444 2.12479 1.94444H2.73729C3.32451 1.94444 3.81694 2.38586 3.88257 2.97114C3.91271 3.23802 4.15382 3.43098 4.41972 3.39987C4.68659 3.36973 4.87861 3.12912 4.84847 2.86273C4.73375 1.83946 3.90687 1.06409 2.89722 0.987769V0.486111C2.89722 0.21875 2.67847 0 2.41111 0C2.14375 0 1.925 0.21875 1.925 0.486111V0.992635C0.84826 1.09472 0 1.99353 0 3.097C0 3.5729 0.15993 4.03762 0.447221 4.40123C0.735485 4.7731 1.14723 5.04149 1.60854 5.15864L3.01632 5.50762C3.53014 5.6379 3.88889 6.09777 3.88889 6.62617C3.88889 6.93194 3.76833 7.22067 3.54958 7.43942C3.33132 7.65817 3.04257 7.77825 2.73681 7.77825H2.1243C1.53708 7.77825 1.04465 7.33689 0.979024 6.75162C0.948885 6.48474 0.706318 6.29269 0.441873 6.32283C0.174998 6.35297 -0.0170137 6.59364 0.0131252 6.86003C0.126389 7.87017 0.933819 8.63773 1.92549 8.73155V9.23611C1.92549 9.50347 2.14424 9.72222 2.4116 9.72222C2.67896 9.72222 2.89771 9.50347 2.89771 9.23611V8.73445C3.40278 8.69605 3.87479 8.48994 4.23792 8.12681C4.64042 7.72432 4.86208 7.19153 4.86208 6.6257Z"
                  fill="currentColor"
                />
              </svg>
            </div>
            <div className="fomo-cash-info">
              <div className="fomo-cash-title">Total cash</div>
              <div className="fomo-cash-val">${user.balance.toFixed(2)}</div>
            </div>
          </div>

          <div className="fomo-box fomo-payout-box">
            <div className="fomo-box-header">
              <span className="box-title">Biggest Payout</span>
              <div className="filter-pills-row">
                {["Recent", "Today", "Week", "Month", "All time"].map((f, i) => (
                  <button
                    key={f}
                    className={`pill-btn filter-opt${i === 4 ? " active" : ""}`}
                    type="button"
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <div className="fomo-table-cols modern-cols">
              <span className="mcol-player">Rain</span>
              <span className="mcol-date">Date</span>
              <span className="mcol-payout">Payout</span>
            </div>
            <div className="fomo-table-body">
              {user.txs.filter((t) => t.type === "Play" && t.amount > 0).length === 0 ? (
                <div className="fomo-empty-state">No closed positions</div>
              ) : (
                user.txs
                  .filter((t) => t.type === "Play" && t.amount > 0)
                  .slice(0, 5)
                  .map((tx, i) => (
                    <div key={i} className="modern-board-row">
                      <div className="board-col-player">
                        <span className="board-player-name">{tx.label || "Win"}</span>
                      </div>
                      <div className="board-col-date">
                        <span className="board-date-main">{tx.date}</span>
                      </div>
                      <div className="board-col-payout">
                        <span className="board-num-val">${tx.amount.toFixed(2)}</span>
                      </div>
                    </div>
                  ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Rain / Deposit-Withdraw log */}
        <div className="fomo-right-col">
          <div className="fomo-box fomo-rain-box">
            <div className="fomo-rain-tabs">
              {[
                { id: "all", label: "All rain" },
                { id: "1d", label: "1D Rain" },
                { id: "1w", label: "1 Week Rains" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  className={`tab-link${rainTab === tab.id ? " active" : ""}`}
                  type="button"
                  onClick={() => setRainTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="fomo-rain-cols modern-cols">
              <span className="mcol-player">Type</span>
              <span className="mcol-date">Date</span>
              <span className="mcol-payout">Amount</span>
            </div>
            <div className="fomo-rain-body">
              {user.txs.length === 0 ? (
                <div className="fomo-empty-state">No Datas yet</div>
              ) : (
                user.txs.map((tx, i) => (
                  <div key={i} className="modern-board-row">
                    <div className="board-col-player">
                      <div className="board-avatar-box">
                        {tx.type === "Deposit" ? "↓" : tx.type === "Withdraw" ? "↑" : "🎲"}
                      </div>
                      <span className="board-player-name">{tx.type}</span>
                    </div>
                    <div className="board-col-date">
                      <span className="board-date-main">{tx.date}</span>
                    </div>
                    <div className="board-col-payout">
                      <span className="board-num-val">
                        ${Math.abs(tx.amount).toFixed(2)}
                      </span>
                      {tx.type === "Deposit" && (
                        <span className="board-status-badge">Deposit</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
