import CryptoJS from "crypto-js";
import { v4 as uuidv4 } from "uuid";

/**
 * Provably Fair system
 * 1. Server generates a secret serverSeed (kept hidden until after the roll)
 * 2. Client provides clientSeed (or we generate one)
 * 3. Nonce increases every roll
 * 4. Result = HMAC-SHA256(serverSeed, clientSeed:nonce) → float 0-100
 */

export function generateServerSeed(): string {
  return uuidv4() + uuidv4().replace(/-/g, "");
}

export function hashServerSeed(serverSeed: string): string {
  return CryptoJS.SHA256(serverSeed).toString(CryptoJS.enc.Hex);
}

export function generateClientSeed(): string {
  return uuidv4().replace(/-/g, "").slice(0, 16);
}

/**
 * Returns a float between 0 (inclusive) and 100 (exclusive)
 * Used for dice under/over games
 */
export function getRollResult(
  serverSeed: string,
  clientSeed: string,
  nonce: number
): number {
  const message = `${clientSeed}:${nonce}`;
  const hash = CryptoJS.HmacSHA256(message, serverSeed).toString(
    CryptoJS.enc.Hex
  );

  // Take first 8 hex chars → 32-bit int → map to 0-100
  const int = parseInt(hash.slice(0, 8), 16);
  const result = (int / 0xffffffff) * 100;
  return Math.floor(result * 100) / 100; // 2 decimal places
}

export function verifyRoll(
  serverSeed: string,
  clientSeed: string,
  nonce: number,
  claimedResult: number
): boolean {
  const actual = getRollResult(serverSeed, clientSeed, nonce);
  return Math.abs(actual - claimedResult) < 0.01;
}
