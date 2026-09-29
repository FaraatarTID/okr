import { NextRequest, NextResponse } from "next/server";

/**
 * Cross-origin rejection for cookie-authenticated, state-changing route handlers.
 *
 * Why this lives here and not in `spa-bff`: the browser never reaches the BFF. It talks
 * to these Next route handlers, and `proxyToBff` forwards a fixed header list that omits
 * `Origin`. This is the only hop that sees the browser's own request, so it is the only
 * place an origin decision can be made.
 *
 * Why origin and not a CSRF token for login: `/session/login` is what *issues* the CSRF
 * cookie, so a fresh browser holds none. An origin check needs no pre-existing state.
 *
 * Decision, in order:
 *
 * 1. `Sec-Fetch-Site` is set by the browser and cannot be set or forged by page script.
 *    `same-origin` (and `none`, a user-initiated navigation) passes. `same-site` and
 *    `cross-site` are rejected: a sibling subdomain is still not this origin.
 * 2. Without it (older browsers), a present `Origin` must name the host the request was
 *    addressed to. A browser fills `Host` itself, so a cross-site page cannot make the two
 *    agree. The literal `null` origin (sandboxed frames, some redirects) never matches.
 * 3. With neither header the caller is not a browser: curl, the SLO and smoke probes,
 *    health checks. CSRF is a browser-only attack, and a browser sends at least one of the
 *    two on every cross-site POST, so this case is allowed rather than locking out tooling.
 *
 * Scheme is not compared in step 2: it cannot be derived reliably behind a TLS-terminating
 * proxy, and HSTS already prevents a plain-HTTP origin for this host.
 */

export type OriginRejection = "cross_site_fetch" | "origin_mismatch" | "origin_unverifiable";

const MAX_LOGGED_VALUE_LENGTH = 200;

function firstListValue(raw: string | null): string {
  return String(raw ?? "").split(",")[0]?.trim().toLowerCase() ?? "";
}

/** Returns why the request must be refused, or `null` when it may proceed. */
export function classifyOrigin(headers: Headers): OriginRejection | null {
  const fetchSite = String(headers.get("sec-fetch-site") ?? "").trim().toLowerCase();
  if (fetchSite) {
    return fetchSite === "same-origin" || fetchSite === "none" ? null : "cross_site_fetch";
  }

  const origin = String(headers.get("origin") ?? "").trim();
  if (!origin) {
    return null;
  }

  // Prefer the host the edge saw. Nginx sets `Host $host`, so both normally agree.
  const requestHost = firstListValue(headers.get("x-forwarded-host")) || firstListValue(headers.get("host"));
  if (!requestHost) {
    return "origin_unverifiable";
  }

  let originHost: string;
  try {
    originHost = new URL(origin).host.toLowerCase();
  } catch {
    return "origin_mismatch";
  }
  return originHost === requestHost ? null : "origin_mismatch";
}

/**
 * Guard for a route handler: returns a 403 response to send, or `null` to continue.
 * Logs the reason and route only. It never logs cookies or the request body.
 */
export function rejectCrossOrigin(request: NextRequest): NextResponse | null {
  const reason = classifyOrigin(request.headers);
  if (!reason) {
    return null;
  }
  console.warn(
    JSON.stringify({
      event: "spa_web_origin_rejected",
      method: request.method,
      route: request.nextUrl.pathname,
      status: 403,
      reason,
      origin: String(request.headers.get("origin") ?? "").slice(0, MAX_LOGGED_VALUE_LENGTH),
      sec_fetch_site: String(request.headers.get("sec-fetch-site") ?? "").slice(0, 32),
      ts: new Date().toISOString(),
    }),
  );
  return NextResponse.json(
    {
      code: "INVALID_ORIGIN",
      error: "Cross-origin request rejected.",
      message: "Cross-origin request rejected.",
    },
    { status: 403 },
  );
}
