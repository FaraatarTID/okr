import { DEFAULT_MODE } from "@/lib/deeplink";

export const SIDEBAR_ITEMS: Array<{
  id: string;
  label: string;
  mode: string;
  path: string;
}> = [
  { id: "atlas", label: "Atlas Workspace", mode: "atlas", path: "/" },
  { id: "dashboard", label: "Dashboard", mode: "dashboard", path: "/dashboard" },
  { id: "weekly", label: "Weekly Report", mode: "weekly", path: "/weekly" },
  { id: "daily", label: "Daily Report", mode: "daily", path: "/daily" },
  { id: "ritual", label: "Check-In", mode: "ritual", path: "/check-in" },
  { id: "retrobox", label: "Retrobox", mode: "retrobox", path: "/retrobox" },
  { id: "timeline", label: "Timeline", mode: "timeline", path: "/timeline" },
  { id: "admin", label: "Admin", mode: "admin", path: "/admin" },
];

const MODE_PATH_MAP = new Map(SIDEBAR_ITEMS.map((item) => [item.mode, item.path]));
const PATH_MODE_MAP = new Map(SIDEBAR_ITEMS.map((item) => [item.path, item.mode]));
const MODE_LABEL_MAP = new Map(SIDEBAR_ITEMS.map((item) => [item.mode, item.label]));
PATH_MODE_MAP.set("/ritual", "ritual");

export function pathForMode(mode: string): string {
  return MODE_PATH_MAP.get(mode) || "/";
}

export function modeForPath(pathname: string): string {
  const normalized = String(pathname || "").trim() || "/";
  return PATH_MODE_MAP.get(normalized) || DEFAULT_MODE;
}

export function modeDisplayLabel(mode: string): string {
  return MODE_LABEL_MAP.get(mode) || mode;
}
