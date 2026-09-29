import net from "node:net";

/**
 * In-process fixed-window request limiter, a coarse flood backstop for the
 * unauthenticated and session routes of this BFF.
 *
 * It is deliberately NOT the authoritative control. The backend already owns the shared,
 * cross-replica limits (per-client-IP request limit and login lockout), and this package
 * may not hold shared state (`scripts/check_spa_bff_boundaries.py` forbids redis and
 * database clients). What it adds is cheap protection that runs before a request costs a
 * signed hop to the backend. Accepted consequences, recorded in the D4 register:
 *
 * - State is per process, so with N replicas the effective ceiling is N times the
 *   configured one, and it resets on restart. Limits are set loose enough that this
 *   only matters for genuine floods.
 * - Memory is bounded: at most `maxKeys` tracked keys. When full, expired windows are
 *   dropped first, then the oldest key. Evicting a live key lets that client's counter
 *   restart, which is the cost of never growing without bound.
 */

export interface RateLimitPolicy {
  /** Requests allowed per key per window. */
  max: number;
  windowMs: number;
}

export interface RateLimitDecision {
  allowed: boolean;
  /** Whole seconds until the window ends. Meaningful when `allowed` is false. */
  retryAfterSeconds: number;
}

interface Window {
  count: number;
  resetAt: number;
}

const MAX_KEY_LENGTH = 64;

export class FixedWindowLimiter {
  private readonly windows = new Map<string, Window>();

  constructor(
    private readonly policy: RateLimitPolicy,
    private readonly maxKeys: number,
    private readonly now: () => number = Date.now,
  ) {}

  /** Number of keys currently tracked. Exposed for tests and diagnostics. */
  get size(): number {
    return this.windows.size;
  }

  consume(key: string): RateLimitDecision {
    const now = this.now();
    const current = this.windows.get(key);

    if (!current || current.resetAt <= now) {
      // A new or expired window. Re-insert so `windows` stays ordered oldest-first,
      // which is what eviction relies on.
      this.windows.delete(key);
      this.makeRoom(now);
      this.windows.set(key, { count: 1, resetAt: now + this.policy.windowMs });
      return { allowed: true, retryAfterSeconds: 0 };
    }

    current.count += 1;
    if (current.count > this.policy.max) {
      return {
        allowed: false,
        retryAfterSeconds: Math.max(1, Math.ceil((current.resetAt - now) / 1000)),
      };
    }
    return { allowed: true, retryAfterSeconds: 0 };
  }

  private makeRoom(now: number): void {
    if (this.windows.size < this.maxKeys) {
      return;
    }
    for (const [key, window] of this.windows) {
      if (window.resetAt <= now) {
        this.windows.delete(key);
      }
    }
    while (this.windows.size >= this.maxKeys) {
      const oldest = this.windows.keys().next();
      if (oldest.done) {
        return;
      }
      this.windows.delete(oldest.value);
    }
  }
}

/**
 * The key a request is limited under.
 *
 * `trustedClientIp` is the private `X-OKR-Client-IP` header our edge overwrites at every
 * hop. It is used only when it parses as an IP address, so a malformed or oversized value
 * cannot bloat the map. Otherwise the socket peer is used (rule 6 of
 * docs/client-ip-trust-adr.md: a throughput limiter falls back to the peer rather than
 * dropping the key). Fastify's `request.ip` must not be passed here: with `trustProxy`
 * it is read from `X-Forwarded-For`, which the caller controls.
 */
export function resolveRateLimitKey(
  trustedClientIp: string | undefined,
  socketPeer: string | undefined,
): string {
  const header = String(trustedClientIp ?? "").trim();
  if (header && header.length <= MAX_KEY_LENGTH && net.isIP(header) !== 0) {
    return header.toLowerCase();
  }
  const peer = String(socketPeer ?? "").trim();
  return (peer || "unknown").slice(0, MAX_KEY_LENGTH).toLowerCase();
}

export type RateLimitBucket = "login" | "session";

/**
 * Which bucket a URL belongs to, or `null` when it is not limited here.
 *
 * Login is separated from the rest of `/session/*` because it is the credential-guessing
 * surface and gets a tighter ceiling, while `/session/me` is polled by the SPA and needs
 * headroom. The catch-all route's own login (`/api/backend/v1/auth/login`) is the same
 * surface reached a second way, so it shares the login bucket rather than being a bypass.
 * Authenticated backend traffic is not limited here: the backend limits it per client IP.
 */
export function classifyRateLimitBucket(method: string, rawUrl: string): RateLimitBucket | null {
  const queryIndex = rawUrl.indexOf("?");
  const path = (queryIndex >= 0 ? rawUrl.slice(0, queryIndex) : rawUrl).replace(/\/+$/, "").toLowerCase();

  if (path === "/session/login" || path === "/api/backend/v1/auth/login") {
    return method.toUpperCase() === "POST" ? "login" : null;
  }
  if (path === "/session/me" || path === "/session/logout") {
    return "session";
  }
  return null;
}
