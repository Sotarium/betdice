/**
 * Demo user store. Replace with real DB later.
 * Each user has deposits, withdrawals, plays and a profit history.
 */

export interface Tx {
  type: "Deposit" | "Withdraw" | "Play";
  date: string; // ISO or display string
  amount: number; // positive for deposit/win, negative for withdraw/loss
}

export interface UserStats {
  username: string;
  avatar?: string;
  balance: number;
  profit: number;
  txs: Tx[];
  /** profit over time points for the chart [timestamp, profit] */
  chart: { t: string; v: number }[];
}

// Seed with one example user matching your screenshot style
const store: Record<string, UserStats> = {
  username: {
    username: "username",
    balance: 1.39,
    profit: 1.39,
    txs: [
      { type: "Deposit", date: "2026/09/28 5:00 PM", amount: 0.17 },
    ],
    chart: [
      { t: "5:00 PM", v: 0.17 },
      { t: "", v: 0.4 },
      { t: "", v: 0.7 },
      { t: "", v: 1.0 },
      { t: "", v: 1.39 },
    ],
  },
};

export function getAllUsers(): UserStats[] {
  return Object.values(store);
}

export function getUser(username: string): UserStats | null {
  return store[username.toLowerCase()] || null;
}

export function upsertUser(data: UserStats) {
  store[data.username.toLowerCase()] = data;
}
