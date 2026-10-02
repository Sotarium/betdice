export interface UserBalance {
  id: string; // Discord user id or session id
  balance: number;
  serverSeed: string;
  serverSeedHash: string;
  clientSeed: string;
  nonce: number;
}

export interface RollResult {
  result: number;
  won: boolean;
  payout: number;
  serverSeedHash: string;
  clientSeed: string;
  nonce: number;
  // revealed only after the roll for verification
  serverSeed?: string;
}
