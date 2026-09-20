import { ALLOWED_MODES, DEFAULT_MODE, MODE_ALIASES } from "@/lib/deeplink";

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

/**
 * Derive the active mode from a location.
 *
 * An explicit `mode` query parameter wins, because a deep link is an instruction
 * from the user. Otherwise the route path decides, because `/weekly` must render
 * the weekly panel even when it was reached by a plain navigation rather than a
 * sidebar click.
 *
 * This lives here, used by both the boot sync and the navigation watcher, so the
 * two cannot drift apart. They did drift: the shell used to read the mode from
 * the path exactly once per mount, which was only correct while every navigation
 * remounted the whole shell. Once a shared layout keeps the shell mounted, a
 * path read that happens only at boot leaves the wrong panel rendered.
 */
export function modeForLocation(pathname: string, search: string): string {
  const explicitMode = parseDeepLinkSearch(search).mode;
  return explicitMode || modeForPath(pathname) || DEFAULT_MODE;
}

function parseDeepLinkSearch(search: string): { mode: string } {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const raw = String(params.get("mode") || "")
    .trim()
    .toLowerCase();
  const aliased = MODE_ALIASES.get(raw) || raw;
  if (!aliased) {
    return { mode: "" };
  }
  // An unrecognised explicit mode falls back to the path rather than to the
  // default, so a typo in a link cannot silently change the panel.
  return { mode: ALLOWED_MODES.has(aliased) ? aliased : "" };
}

export function modeDisplayLabel(mode: string): string {
  return MODE_LABEL_MAP.get(mode) || mode;
}
