/**
 * Real user store only — no demo data.
 * The Discord bot should POST to /api/users/sync to register activity.
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
  avatar: string | null; // Discord avatar hash
  balance: number;
  profit: number;
  txs: Tx[];
  chart: { t: string; v: number }[];
}

// In-memory (replace with DB later). Starts EMPTY — only real users.
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

/** Discord CDN avatar URL */
export function avatarUrl(discordId: string, avatarHash: string | null, size = 128): string {
  if (avatarHash) {
    const ext = avatarHash.startsWith("a_") ? "gif" : "png";
    return `https://cdn.discordapp.com/avatars/${discordId}/${avatarHash}.${ext}?size=${size}`;
  }
  // Default Discord avatar based on user id
  const idx = Number(BigInt(discordId) % 6n);
  return `https://cdn.discordapp.com/embed/avatars/${idx}.png`;
}
