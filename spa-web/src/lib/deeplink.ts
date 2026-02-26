import { parseTypedRef } from "@/lib/atlas";

export const DEFAULT_MODE = "atlas";
export const DEFAULT_LENS = "focus";

const ALLOWED_LENSES = new Set(["focus", "health", "owner"]);
const ALLOWED_MODES = new Set([
  "atlas",
  "weekly",
  "daily",
  "ritual",
  "retrobox",
  "timeline",
  "dashboard",
  "admin",
]);

export interface AtlasDeepLinkState {
  cycle: string;
  mode: string;
  sel: string;
  ft: string;
  lens: string;
}

const MODE_ALIASES = new Map<string, string>([
  ["check-in", "ritual"],
  ["checkin", "ritual"],
]);

function normalizeCycle(raw: string | null | undefined): string {
  const text = String(raw || "").trim();
  if (!text) {
    return "";
  }
  const parsed = Number.parseInt(text, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return "";
  }
  return String(parsed);
}

function normalizeMode(raw: string | null | undefined): string {
  const source = String(raw || "").trim().toLowerCase();
  const text = MODE_ALIASES.get(source) || source;
  if (!text) {
    return DEFAULT_MODE;
  }
  if (!ALLOWED_MODES.has(text)) {
    return DEFAULT_MODE;
  }
  return text;
}

function normalizeLens(raw: string | null | undefined): string {
  const text = String(raw || "").trim().toLowerCase();
  if (!text) {
    return DEFAULT_LENS;
  }
  if (!ALLOWED_LENSES.has(text)) {
    return DEFAULT_LENS;
  }
  return text;
}

function normalizeTypedRef(raw: string | null | undefined): string {
  const text = String(raw || "").trim().toLowerCase();
  if (!text) {
    return "";
  }
  const parsed = parseTypedRef(text);
  if (!parsed.nodeType || !parsed.nodeId) {
    return "";
  }
  return `${parsed.nodeType.toLowerCase()}_${parsed.nodeId}`;
}

export function parseDeepLink(search: string): AtlasDeepLinkState {
  const params = new URLSearchParams(String(search || ""));
  return {
    cycle: normalizeCycle(params.get("cycle")),
    mode: normalizeMode(params.get("mode")),
    sel: normalizeTypedRef(params.get("sel")),
    ft: normalizeTypedRef(params.get("ft")),
    lens: normalizeLens(params.get("lens")),
  };
}

export function buildDeepLinkQuery(state: Partial<AtlasDeepLinkState>): string {
  const cycle = normalizeCycle(state.cycle);
  const mode = normalizeMode(state.mode);
  const selectedRef = normalizeTypedRef(state.sel);
  const focusTaskRef = normalizeTypedRef(state.ft);
  const lens = normalizeLens(state.lens);

  const params = new URLSearchParams();
  if (cycle) {
    params.set("cycle", cycle);
  }
  if (mode && mode !== DEFAULT_MODE) {
    params.set("mode", mode);
  }
  if (selectedRef) {
    params.set("sel", selectedRef);
  }
  if (focusTaskRef) {
    params.set("ft", focusTaskRef);
  }
  if (lens && lens !== DEFAULT_LENS) {
    params.set("lens", lens);
  }
  return params.toString();
}

export function normalizeFocusTaskRef(raw: string | null | undefined): string {
  const typedRef = normalizeTypedRef(raw);
  if (!typedRef.startsWith("task_")) {
    return "";
  }
  return typedRef;
}
