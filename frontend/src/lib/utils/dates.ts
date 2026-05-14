import {
  format,
  formatDistanceToNow,
  parseISO,
  subDays,
  startOfDay,
  endOfDay,
} from "date-fns";

export function formatDate(iso: string): string {
  return format(parseISO(iso), "MMM d, yyyy");
}

export function formatDateTime(iso: string): string {
  return format(parseISO(iso), "MMM d, yyyy · h:mm a");
}

export function formatRelative(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true });
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`;
}

export function isoNow(): string {
  return new Date().toISOString();
}

export function isoStartOf(daysAgo: number): string {
  return startOfDay(subDays(new Date(), daysAgo)).toISOString();
}

export function isoEndOfToday(): string {
  return endOfDay(new Date()).toISOString();
}

export function last30Days(): { start: string; end: string } {
  return {
    start: isoStartOf(30),
    end: isoEndOfToday(),
  };
}

export function last7Days(): { start: string; end: string } {
  return {
    start: isoStartOf(7),
    end: isoEndOfToday(),
  };
}

export function previous7Days(): { start: string; end: string } {
  return {
    start: isoStartOf(14),
    end: isoStartOf(7),
  };
}
