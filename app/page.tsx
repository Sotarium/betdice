"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function Home() {
  const [balance, setBalance] = useState(100);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // In production this would come from Discord OAuth / API
    const saved = localStorage.getItem("betdice_balance");
    if (saved) setBalance(parseFloat(saved));
  }, []);

  function saveBalance(b: number) {
    setBalance(b);
    localStorage.setItem("betdice_balance", b.toString());
  }

  return (
    <div className="container">
      <header style={{ marginBottom: 24, textAlign: "center" }}>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>🎲 Betdice</h1>
        <p className="muted">Provably fair dice · Discord linked</p>
      </header>

      {/* Balance card - matches your Discord embed style */}
      <div className="card" style={{ textAlign: "center" }}>
        <div className="label">Your balance</div>
        <div className="balance-value" style={{ margin: "8px 0 16px" }}>
          🎲 {balance.toFixed(2)} dices
        </div>

        <div className="row" style={{ justifyContent: "center" }}>
          <button
            className="btn btn-secondary"
            onClick={() => alert("Deposit: Connect Plisio API key in Vercel env to enable unique addresses")}
          >
            ⬇️ Deposit
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => alert("Withdraw: Coming after Plisio setup")}
          >
            ⬆️ Withdraw
          </button>
        </div>
      </div>

      {/* Play button */}
      <Link href="/play">
        <button className="btn btn-primary" style={{ width: "100%", padding: 14, fontSize: 16 }}>
          🎲 Play Dice
        </button>
      </Link>

      <div className="card" style={{ marginTop: 24 }}>
        <div className="label">How it works</div>
        <p className="muted" style={{ lineHeight: 1.5, marginTop: 8 }}>
          Every roll is provably fair. Server seed is hashed before you play.
          After the roll you can verify the result yourself using the revealed
          server seed, your client seed and the nonce.
        </p>
      </div>
    </div>
  );
}