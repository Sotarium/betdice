"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface LastRoll {
  result: number;
  won: boolean;
  payout: number;
  target: number;
  direction: "under" | "over";
  serverSeedHash: string;
  clientSeed: string;
  nonce: number;
  serverSeed?: string;
}

export default function PlayPage() {
  const [balance, setBalance] = useState(100);
  const [bet, setBet] = useState(1);
  const [target, setTarget] = useState(50);
  const [direction, setDirection] = useState<"under" | "over">("under");
  const [rolling, setRolling] = useState(false);
  const [lastRoll, setLastRoll] = useState<LastRoll | null>(null);
  const [clientSeed, setClientSeed] = useState("");

  useEffect(() => {
    const saved = localStorage.getItem("betdice_balance");
    if (saved) setBalance(parseFloat(saved));
    const seed = localStorage.getItem("betdice_client_seed");
    if (seed) setClientSeed(seed);
    else {
      const newSeed = Math.random().toString(36).slice(2, 12);
      setClientSeed(newSeed);
      localStorage.setItem("betdice_client_seed", newSeed);
    }
  }, []);

  function saveBalance(b: number) {
    setBalance(b);
    localStorage.setItem("betdice_balance", b.toString());
  }

  // Multiplier calculation (house edge ~1%)
  const winChance = direction === "under" ? target : 100 - target;
  const multiplier = winChance > 0 ? (99 / winChance) : 0;
  const potentialWin = +(bet * multiplier).toFixed(2);

  async function handleRoll() {
    if (bet <= 0 || bet > balance || rolling) return;
    setRolling(true);
    setLastRoll(null);

    try {
      const res = await fetch("/api/play", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bet,
          target,
          direction,
          clientSeed,
          balance, // demo only – production must check server-side balance
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        alert(data.error || "Roll failed");
        return;
      }

      const newBalance = data.won
        ? balance - bet + data.payout
        : balance - bet;

      saveBalance(+newBalance.toFixed(2));
      setLastRoll(data);
    } catch (e) {
      alert("Network error");
    } finally {
      setRolling(false);
    }
  }

  return (
    <div className="container">
      <div className="row" style={{ marginBottom: 20, justifyContent: "space-between" }}>
        <Link href="/" className="muted">
          ← Back
        </Link>
        <div style={{ fontWeight: 600 }}>🎲 {balance.toFixed(2)} dices</div>
      </div>

      <div className="card">
        <div className="label">Bet amount</div>
        <input
          type="number"
          min={0.01}
          step={0.01}
          value={bet}
          onChange={(e) => setBet(Math.max(0, parseFloat(e.target.value) || 0))}
          style={{ marginBottom: 16 }}
        />

        <div className="label">Roll {direction === "under" ? "Under" : "Over"}</div>
        <div className="row" style={{ marginBottom: 8 }}>
          <button
            className={`btn ${direction === "under" ? "btn-primary" : "btn-secondary"}`}
            style={{ flex: 1 }}
            onClick={() => setDirection("under")}
          >
            Under
          </button>
          <button
            className={`btn ${direction === "over" ? "btn-primary" : "btn-secondary"}`}
            style={{ flex: 1 }}
            onClick={() => setDirection("over")}
          >
            Over
          </button>
        </div>

        <input
          type="range"
          min={1}
          max={95}
          value={target}
          onChange={(e) => setTarget(parseInt(e.target.value))}
          style={{ width: "100%", margin: "12px 0" }}
        />
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
          <span className="muted">Target: {target}</span>
          <span className="muted">Win chance: {winChance.toFixed(2)}%</span>
          <span style={{ color: "#23a559" }}>×{multiplier.toFixed(4)}</span>
        </div>

        <button
          className="btn btn-success"
          style={{ width: "100%", padding: 14, fontSize: 16 }}
          disabled={rolling || bet <= 0 || bet > balance}
          onClick={handleRoll}
        >
          {rolling ? "Rolling..." : `Roll · Win ${potentialWin} dices`}
        </button>
      </div>

      {lastRoll && (
        <div
          className="card"
          style={{
            borderLeft: `4px solid ${lastRoll.won ? "var(--green)" : "var(--red)"}`,
          }}
        >
          <div style={{ fontSize: 32, fontWeight: 700, marginBottom: 8 }}>
            {lastRoll.result.toFixed(2)}
          </div>
          <div style={{ marginBottom: 12 }}>
            {lastRoll.won ? (
              <span style={{ color: "var(--green)" }}>
                Won +{lastRoll.payout.toFixed(2)} dices
              </span>
            ) : (
              <span style={{ color: "var(--red)" }}>Lost</span>
            )}
          </div>

          <div className="muted" style={{ fontSize: 12, lineHeight: 1.6 }}>
            <div>Server seed hash: {lastRoll.serverSeedHash.slice(0, 24)}…</div>
            <div>Client seed: {lastRoll.clientSeed}</div>
            <div>Nonce: {lastRoll.nonce}</div>
            {lastRoll.serverSeed && (
              <div style={{ marginTop: 8 }}>
                <strong>Server seed (revealed):</strong>
                <br />
                <code style={{ wordBreak: "break-all" }}>{lastRoll.serverSeed}</code>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="card">
        <div className="label">Your client seed</div>
        <input
          value={clientSeed}
          onChange={(e) => {
            setClientSeed(e.target.value);
            localStorage.setItem("betdice_client_seed", e.target.value);
          }}
        />
        <p className="muted" style={{ marginTop: 8 }}>
          Change this anytime. It is mixed with the server seed to produce the roll.
        </p>
      </div>
    </div>
  );
}