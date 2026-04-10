export function formatOptionalNumber(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value}`;
  }
  return "-";
}

export function parseDateOrNull(raw: unknown): Date | null {
  const text = String(raw || "").trim();
  if (!text) {
    return null;
  }
  // Canonicalize backend datetime strings to strict ISO-8601 UTC with
  // millisecond precision. This prevents local-time interpretation drift.
  let normalized = text;
  const matched = normalized.match(
    /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?([zZ]|[+\-]\d{2}:\d{2})?$/,
  );
  if (matched) {
    const [, datePart, timePart, fractionalRaw, timezoneRaw] = matched;
    const fractional = fractionalRaw
      ? `.${fractionalRaw.slice(0, 3).padEnd(3, "0")}`
      : "";
    const timezone = timezoneRaw
      ? (timezoneRaw.toUpperCase() === "Z" ? "Z" : timezoneRaw)
      : "Z";
    normalized = `${datePart}T${timePart}${fractional}${timezone}`;
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

export function formatOptionalDate(value: unknown): string {
  if (!value) {
    return "-";
  }
  const parsed = parseDateOrNull(value);
  if (!parsed || Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString();
}

export function toDateInputValue(value: unknown): string {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const month = `${parsed.getMonth() + 1}`.padStart(2, "0");
  const day = `${parsed.getDate()}`.padStart(2, "0");
  return `${parsed.getFullYear()}-${month}-${day}`;
}

export function toIsoStart(dateValue: string): string {
  return `${dateValue}T00:00:00Z`;
}

export function toIsoEnd(dateValue: string): string {
  return `${dateValue}T23:59:59Z`;
}

export function addDays(date: Date, days: number): Date {
  const clone = new Date(date.getTime());
  clone.setDate(clone.getDate() + days);
  return clone;
}

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

export function endOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}

export function reviewWindow(): { start: Date; end: Date } {
  const end = endOfDay(new Date());
  const start = startOfDay(addDays(end, -7));
  return { start, end };
}

export function toDateShortLabel(value: Date): string {
  return value.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function formatElapsedClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  return `${`${hours}`.padStart(2, "0")}:${`${minutes}`.padStart(2, "0")}:${`${seconds}`.padStart(2, "0")}`;
}

export function startOfWeekIso(today = new Date()): string {
  const date = new Date(today);
  const day = date.getDay();
  const delta = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + delta);
  return `${date.getFullYear()}-${`${date.getMonth() + 1}`.padStart(2, "0")}-${`${date.getDate()}`.padStart(2, "0")}`;
}

export function endOfWeekIso(today = new Date()): string {
  const start = new Date(`${startOfWeekIso(today)}T00:00:00`);
  start.setDate(start.getDate() + 6);
  return `${start.getFullYear()}-${`${start.getMonth() + 1}`.padStart(2, "0")}-${`${start.getDate()}`.padStart(2, "0")}`;
}
