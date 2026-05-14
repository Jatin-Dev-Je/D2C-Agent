import type { AuthClaims } from "@/lib/api/types";

/**
 * Decodes JWT payload without signature verification.
 * Signature verification happens server-side.
 */
export function decodeJwtPayload(token: string): AuthClaims | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    const payload = parts[1];
    if (!payload) return null;

    const padded = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), "=");
    const decoded = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    const json: unknown = JSON.parse(decoded);

    if (typeof json !== "object" || json === null) return null;

    const obj = json as Record<string, unknown>;

    // Check expiry
    const exp = obj["exp"];
    if (typeof exp === "number" && Date.now() / 1000 > exp) return null;

    const merchant_id =
      (obj["merchant_id"] as string | undefined) ?? (obj["sub"] as string | undefined);
    const email =
      (obj["email"] as string | undefined) ??
      (obj["user_email"] as string | undefined) ??
      (obj["preferred_username"] as string | undefined);

    const appMeta = obj["app_metadata"];
    const role =
      (obj["role"] as string | undefined) ??
      (typeof appMeta === "object" && appMeta !== null
        ? ((appMeta as Record<string, unknown>)["role"] as string | undefined)
        : undefined) ??
      "merchant";

    if (!merchant_id?.trim() || !email?.trim()) return null;

    return {
      merchant_id: merchant_id.trim(),
      email: email.trim(),
      role: role.trim() || "merchant",
    };
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const claims = decodeJwtPayload(token);
  return claims === null;
}
