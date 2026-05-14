/**
 * All Decimal values from the backend arrive as strings.
 * These utilities parse and format them consistently.
 */

export function parseDecimal(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = parseFloat(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export function formatCurrency(
  value: string | number,
  currency = "INR",
): string {
  const num = typeof value === "string" ? parseDecimal(value) : value;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
}

export function formatNumber(value: string | number, decimals = 0): string {
  const num = typeof value === "string" ? parseDecimal(value) : value;
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
}

export function formatRoas(value: string | number): string {
  const num = typeof value === "string" ? parseDecimal(value) : value;
  return `${num.toFixed(2)}x`;
}

export function formatPercentage(value: string | number): string {
  const num = typeof value === "string" ? parseDecimal(value) : value;
  const formatted = Math.abs(num).toFixed(1);
  return num >= 0 ? `+${formatted}%` : `-${formatted}%`;
}

export function formatCompact(value: string | number): string {
  const num = typeof value === "string" ? parseDecimal(value) : value;
  if (num >= 1_00_00_000) return `₹${(num / 1_00_00_000).toFixed(1)}Cr`;
  if (num >= 1_00_000) return `₹${(num / 1_00_000).toFixed(1)}L`;
  if (num >= 1_000) return `₹${(num / 1_000).toFixed(1)}K`;
  return `₹${num.toFixed(0)}`;
}

export function isPositiveDelta(delta: string): boolean {
  return parseDecimal(delta) > 0;
}
