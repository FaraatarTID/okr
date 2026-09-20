/**
 * Minimal short-TTL read-through cache for the shell's read datasets.
 *
 * Why hand-rolled instead of React Query or SWR: the shell has a small number of
 * resources, each already has an explicit refresh path, and a new runtime
 * dependency would have to clear `scripts/check_dependency_manifest.py` plus the
 * dependency-scan and licence gates. Nothing here needs a query language.
 *
 * What it fixes: the shell used to issue the identical `cycles.all` +
 * `cycles.active` pair from two separate hooks on the same mount, and the admin
 * panel issued a third `cycles.all`.
 *
 * Deliberate limitation — the session is NOT cached. `readSessionUser()` carries
 * `role`, and the role gate lives in `useShellAccessControl.ts` and decides what
 * chrome is rendered. Caching it would widen the window in which a user demoted
 * server-side still sees admin controls from one round trip to the whole TTL.
 * The plan flags that as the highest-blast-radius risk in Workstream C, so the
 * session keeps reading fresh. Because C8 removed the per-navigation remount,
 * that costs one request per shell lifetime rather than one per navigation, so
 * there is nothing left to gain by caching it.
 *
 * Invalidation is explicit and namespace-based. Callers that cannot tolerate a
 * stale read (mutation paths, and read paths whose freshness the caller owns)
 * pass `bypassCache` rather than relying on the TTL.
 */

const DEFAULT_TTL_MS = 60_000;

type Entry<T> = {
  expiresAt: number;
  promise: Promise<T>;
  /**
   * False once the request settles. Tracked explicitly because promise state is
   * not observable synchronously.
   */
  pending: boolean;
};

const entries = new Map<string, Entry<unknown>>();

/**
 * Cache key namespaces. Kept explicit so invalidation reads as a domain
 * operation rather than a string match, and so a typo cannot silently create a
 * second namespace that never gets invalidated.
 */
export const cacheKeys = {
  cycles: (username: string) => `cycles:${username}`,
  admin: (username: string) => `admin:${username}`,
} as const;

export type CacheReadOptions = {
  /** How long a resolved value stays fresh. Defaults to 60 seconds. */
  ttlMs?: number;
  /**
   * Refuse a settled cached value and issue a new request. An in-flight request
   * for the same key is still joined, so a burst of bypassing callers collapses
   * to one request. Use this on mutation paths and on reads whose freshness the
   * caller owns.
   */
  bypassCache?: boolean;
};

/**
 * Return the cached value for `key`, or start (or join) a single request.
 *
 * Concurrent callers share one promise, so N components mounting together
 * produce one request. A rejected promise is never cached: the entry is removed
 * and the rejection propagates to every caller that joined it, so a transient
 * failure can be retried immediately instead of being cached as an error.
 */
export function readThroughCache<T>(
  key: string,
  loader: () => Promise<T>,
  options: CacheReadOptions = {},
): Promise<T> {
  const ttlMs = options.ttlMs ?? DEFAULT_TTL_MS;
  const now = Date.now();
  const existing = entries.get(key) as Entry<T> | undefined;

  if (existing) {
    if (existing.pending) {
      // Join the in-flight request, whether or not this caller bypasses.
      return existing.promise;
    }
    if (!options.bypassCache && existing.expiresAt > now) {
      return existing.promise;
    }
  }

  const promise = loader().then(
    (value) => {
      markSettled(key, promise);
      return value;
    },
    (error: unknown) => {
      // Never cache a failure, so the next read retries.
      drop(key, promise);
      throw error;
    },
  );

  entries.set(key, { expiresAt: now + ttlMs, promise, pending: true });
  return promise;
}

/**
 * Publish an authoritative value, or an in-flight request, under `key`.
 *
 * Use this on mutation paths that bypass the cache: the caller has just read the
 * authoritative value, so seeding it keeps every other reader of the same key
 * consistent instead of leaving them to serve the stale value or open a second
 * request. Passing a promise seeds the in-flight state, so a concurrent reader
 * joins it.
 */
export function writeThroughCache<T>(
  key: string,
  value: T | Promise<T>,
  ttlMs: number = DEFAULT_TTL_MS,
): void {
  const promise = Promise.resolve(value);
  entries.set(key, { expiresAt: Date.now() + ttlMs, promise, pending: true });
  void promise.then(
    () => {
      markSettled(key, promise);
    },
    () => {
      drop(key, promise);
    },
  );
}

/** Drop every cache entry whose key is `prefix` or starts with `prefix:`. */
export function invalidateCache(prefix: string): void {
  for (const key of [...entries.keys()]) {
    if (key === prefix || key.startsWith(`${prefix}:`)) {
      entries.delete(key);
    }
  }
}

/**
 * Drop every entry. Sign-out and identity changes must call this so one user's
 * cycles and teams can never be served to the next user on a shared browser.
 */
export function clearResourceCache(): void {
  entries.clear();
}

/**
 * Whether `key` holds a settled value a caller may reuse. Exposed for tests and
 * for callers that need to distinguish "fresh" from "in flight" without
 * triggering a read.
 */
export function isCacheFresh(key: string, now: number = Date.now()): boolean {
  const entry = entries.get(key);
  return Boolean(entry && !entry.pending && entry.expiresAt > now);
}

/**
 * Mark the entry settled, but only if it still holds this exact promise. A newer
 * read may have replaced the entry while this one was in flight, and clearing
 * the newer entry's pending flag would let a stale value be served.
 */
function markSettled(key: string, promise: Promise<unknown>): void {
  const current = entries.get(key);
  if (current?.promise === promise) {
    current.pending = false;
  }
}

/** Remove the entry, but only if it still holds this exact promise. */
function drop(key: string, promise: Promise<unknown>): void {
  if (entries.get(key)?.promise === promise) {
    entries.delete(key);
  }
}
