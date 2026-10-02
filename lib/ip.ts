import { headers } from "next/headers";

const ALLOWED_IP = "24.49.252.230";

/**
 * Returns true only if the request comes from the allowed admin IP.
 * On Vercel we check x-forwarded-for / x-real-ip.
 */
export function isAllowedIp(): boolean {
  const h = headers();
  const forwarded = h.get("x-forwarded-for") || "";
  const real = h.get("x-real-ip") || "";
  const candidate = (forwarded.split(",")[0] || real || "").trim();

  // Also allow localhost for development
  if (
    candidate === ALLOWED_IP ||
    candidate === "127.0.0.1" ||
    candidate === "::1" ||
    candidate === ""
  ) {
    // empty can happen in some edge cases; be strict in production:
    if (process.env.NODE_ENV === "production" && candidate !== ALLOWED_IP) {
      return false;
    }
    return candidate === ALLOWED_IP || process.env.NODE_ENV !== "production";
  }
  return false;
}
