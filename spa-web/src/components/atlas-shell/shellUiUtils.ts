export type CyclePeriodLike = {
  start_date?: string | null;
  end_date?: string | null;
};

export type ResolvedCycleLike = {
  id: number;
  title?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

export type CycleOptionLike = ResolvedCycleLike & {
  is_active: boolean;
};

export function parseOwnerIds(raw: string): { value: number[] | undefined; error: string } {
  const normalized = String(raw || "").trim();
  if (!normalized) {
    return { value: undefined, error: "" };
  }

  const parsed = normalized
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number.parseInt(item, 10));

  if (parsed.some((value) => !Number.isFinite(value) || value <= 0)) {
    return {
      value: undefined,
      error: "Owner IDs must be comma-separated positive integers.",
    };
  }

  return {
    value: Array.from(new Set(parsed)),
    error: "",
  };
}

export function parsePreviewBypass(search: string): boolean {
  const params = new URLSearchParams(String(search || ""));
  const raw = String(params.get("spa_preview") || "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
}

export function quarterLabel(dateLike: unknown): string {
  const text = String(dateLike || "").trim();
  if (!text) {
    return "";
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const quarter = Math.floor(parsed.getMonth() / 3) + 1;
  return `Q${quarter}-${parsed.getFullYear()}`;
}

export function cyclePeriodLabel(cycle: CyclePeriodLike | null): string {
  if (!cycle) {
    return "";
  }
  const start = quarterLabel(cycle.start_date);
  const end = quarterLabel(cycle.end_date);
  if (start && end && start !== end) {
    return `${start} to ${end}`;
  }
  return start || end;
}

export function cycleDisplayLabel(cycle: ResolvedCycleLike | null): string {
  if (!cycle) {
    return "Resolving...";
  }
  const period = cyclePeriodLabel(cycle);
  if (period) {
    return period;
  }
  const title = String(cycle.title || "").trim();
  return title || `Cycle ${cycle.id}`;
}

export function cycleOptionLabel(cycle: CycleOptionLike): string {
  const period = cyclePeriodLabel(cycle);
  const title = String(cycle.title || "").trim();
  const base = period || title || `Cycle ${cycle.id}`;
  return cycle.is_active ? `${base} (active)` : base;
}

export function normalizeTaskStatus(raw: unknown): string {
  const text = String(raw || "").trim().toUpperCase();
  if (text === "IN ACTION") {
    return "IN_PROGRESS";
  }
  if (text === "IN PROGRESS") {
    return "IN_PROGRESS";
  }
  if (text === "TODO" || text === "IN_PROGRESS" || text === "DONE" || text === "BLOCKED") {
    return text;
  }
  return "TODO";
}

export function timelineStatusLabel(status: string): string {
  if (status === "IN_PROGRESS") {
    return "In Progress";
  }
  if (status === "DONE") {
    return "Done";
  }
  if (status === "BLOCKED") {
    return "Blocked";
  }
  return "Todo";
}
