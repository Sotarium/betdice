export interface PendingDeposit {
  id: string;
  discordId: string;
  amount: number;
  currency: string;
  txid: string;
  createdAt: number;
}

declare global {
  var _pendingDeposits: PendingDeposit[] | undefined;
}

if (!global._pendingDeposits) {
  global._pendingDeposits = [];
}

export function getPendingDeposits(): PendingDeposit[] {
  return global._pendingDeposits || [];
}

export function queueDeposit(deposit: Omit<PendingDeposit, "id" | "createdAt">): string {
  if (!global._pendingDeposits) {
    global._pendingDeposits = [];
  }
  const id = `${deposit.discordId}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
  global._pendingDeposits.push({
    ...deposit,
    id,
    createdAt: Date.now(),
  });
  console.log(`[Pending Deposits] Queued deposit ${id} for user ${deposit.discordId}: ${deposit.amount}`);
  return id;
}

export function removePendingDeposit(id: string): void {
  if (global._pendingDeposits && id) {
    global._pendingDeposits = global._pendingDeposits.filter((d) => d.id !== id);
  }
}
