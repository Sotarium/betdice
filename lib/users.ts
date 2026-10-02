/**
 * Real user store only — ZERO demo users.
 * Discord bot POSTs to /api/users/sync to add activity.
 */

export interface Tx {
  type: "Deposit" | "Withdraw" | "Play";
  date: string;
  amount: number;
  label?: string;
}

export interface UserStats {
  discordId: string;
  username: string;
  avatar: string | null;
  balance: number;
  profit: number;
  txs: Tx[];
  chart: { t: string; v: number }[];
}

// EMPTY — no hardcoded users
const store: Record<string, UserStats> = {};

export function getAllUsers(): UserStats[] {
  return Object.values(store).filter(
    (u) => u.txs.length > 0 || u.balance !== 0 || u.profit !== 0
  );
}

export function getUserByUsername(username: string): UserStats | null {
  const key = username.toLowerCase();
  return (
    Object.values(store).find((u) => u.username.toLowerCase() === key) || null
  );
}

export function getUserByDiscordId(id: string): UserStats | null {
  return store[id] || null;
}

export function upsertUser(data: UserStats) {
  store[data.discordId] = data;
}

export function avatarUrl(
  discordId: string,
  avatarHash: string | null,
  size = 128
): string {
  if (avatarHash) {
    const ext = avatarHash.startsWith("a_") ? "gif" : "png";
    return `https://cdn.discordapp.com/avatars/${discordId}/${avatarHash}.${ext}?size=${size}`;
  }
  const idx = Number(BigInt(discordId) % 6n);
  return `https://cdn.discordapp.com/embed/avatars/${idx}.png`;
}
