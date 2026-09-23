import { createHash, timingSafeEqual } from "node:crypto";
import { decodeProtectedHeader, importJWK, jwtVerify, type JWK, type JWTPayload } from "jose";

const ALLOWED_ALGORITHMS = ["RS256", "ES256", "PS256"] as const;
const MAX_CACHE_TTL_MS = 5 * 60 * 1000;
const MAX_JWKS_KEYS = 128;
const CLOCK_TOLERANCE_SECONDS = 60;
const DEFAULT_FETCH_TIMEOUT_MS = 3_000;
const MAX_FETCH_TIMEOUT_MS = 10_000;

export interface OidcJwks {
  keys: JWK[];
}

export interface OidcTokenVerifierOptions {
  issuer: string;
  audience: string;
  fetchJwks: (signal: AbortSignal) => Promise<OidcJwks>;
  cacheTtlMs?: number;
  unknownKidRefreshCooldownMs?: number;
  fetchTimeoutMs?: number;
  now?: () => Date;
}

export interface OidcTokenVerifier {
  verify(token: string, expectedNonce: string): Promise<Readonly<JWTPayload>>;
}

function constantTimeStringEqual(left: string, right: string): boolean {
  const leftDigest = createHash("sha256").update(left, "utf8").digest();
  const rightDigest = createHash("sha256").update(right, "utf8").digest();
  return timingSafeEqual(leftDigest, rightDigest);
}

function compatibleKey(key: JWK, kid: string, alg: (typeof ALLOWED_ALGORITHMS)[number]): boolean {
  if (key.kid !== kid || (key.use !== undefined && key.use !== "sig")) return false;
  if (key.key_ops !== undefined && !key.key_ops.includes("verify")) return false;
  if (key.alg !== undefined && key.alg !== alg) return false;
  if (alg === "ES256") return key.kty === "EC" && key.crv === "P-256";
  return key.kty === "RSA";
}

export function createOidcTokenVerifier(options: OidcTokenVerifierOptions): OidcTokenVerifier {
  const cacheTtlMs = options.cacheTtlMs ?? 60_000;
  const unknownKidRefreshCooldownMs = options.unknownKidRefreshCooldownMs ?? 30_000;
  const fetchTimeoutMs = options.fetchTimeoutMs ?? DEFAULT_FETCH_TIMEOUT_MS;
  if (!options.issuer || !options.audience) throw new Error("OIDC issuer and audience are required");
  if (!Number.isInteger(cacheTtlMs) || cacheTtlMs < 1 || cacheTtlMs > MAX_CACHE_TTL_MS) {
    throw new Error(`JWKS cache TTL must be between 1 and ${MAX_CACHE_TTL_MS} milliseconds`);
  }
  if (!Number.isInteger(unknownKidRefreshCooldownMs) || unknownKidRefreshCooldownMs < 1 || unknownKidRefreshCooldownMs > 60_000) {
    throw new Error("Unknown-kid refresh cooldown must be between 1 and 60000 milliseconds");
  }
  if (!Number.isInteger(fetchTimeoutMs) || fetchTimeoutMs < 1 || fetchTimeoutMs > MAX_FETCH_TIMEOUT_MS) {
    throw new Error(`JWKS fetch timeout must be between 1 and ${MAX_FETCH_TIMEOUT_MS} milliseconds`);
  }

  const now = options.now ?? (() => new Date());
  let cachedKeys: JWK[] | undefined;
  let cacheExpiresAt = 0;
  let refreshInFlight: Promise<JWK[]> | undefined;
  let lastUnknownKidRefreshAt = Number.NEGATIVE_INFINITY;

  const fetchAndCache = async (): Promise<JWK[]> => {
    const controller = new AbortController();
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const timedOut = new Promise<never>((_resolve, reject) => {
      timeout = setTimeout(() => {
        controller.abort();
        reject(new Error("JWKS fetch timed out"));
      }, fetchTimeoutMs);
    });
    let response: OidcJwks;
    try {
      response = await Promise.race([options.fetchJwks(controller.signal), timedOut]);
    } finally {
      if (timeout !== undefined) clearTimeout(timeout);
    }
    if (!response || !Array.isArray(response.keys) || response.keys.length === 0 || response.keys.length > MAX_JWKS_KEYS) {
      throw new Error("JWKS response has an invalid key set");
    }
    cachedKeys = response.keys;
    cacheExpiresAt = now().getTime() + cacheTtlMs;
    return cachedKeys;
  };

  const refresh = (): Promise<JWK[]> => {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = fetchAndCache().finally(() => { refreshInFlight = undefined; });
    return refreshInFlight;
  };

  const getKeys = async (): Promise<JWK[]> => {
    if (cachedKeys && now().getTime() < cacheExpiresAt) return cachedKeys;
    return refresh();
  };

  const refreshForUnknownKid = async (): Promise<JWK[]> => {
    if (refreshInFlight) return refreshInFlight;
    const currentTime = now().getTime();
    if (currentTime - lastUnknownKidRefreshAt < unknownKidRefreshCooldownMs) return cachedKeys ?? [];
    lastUnknownKidRefreshAt = currentTime;
    return refresh();
  };

  return {
    async verify(token, expectedNonce) {
      if (typeof token !== "string" || token.length === 0 || token.length > 32_768) {
        throw new Error("ID token is missing or too large");
      }
      if (typeof expectedNonce !== "string" || expectedNonce.length === 0) {
        throw new Error("Expected OIDC nonce is required");
      }

      const header = decodeProtectedHeader(token);
      if (typeof header.alg !== "string" || !ALLOWED_ALGORITHMS.includes(header.alg as (typeof ALLOWED_ALGORITHMS)[number])) {
        throw new Error("ID token algorithm is not allowed");
      }
      if (typeof header.kid !== "string" || header.kid.length === 0 || header.kid.length > 256) {
        throw new Error("ID token kid is required");
      }
      const alg = header.alg as (typeof ALLOWED_ALGORITHMS)[number];
      let keys = await getKeys();
      let matches = keys.filter((key) => compatibleKey(key, header.kid as string, alg));
      if (matches.length === 0) {
        keys = await refreshForUnknownKid();
        matches = keys.filter((key) => compatibleKey(key, header.kid as string, alg));
      }
      if (matches.length !== 1) throw new Error("ID token signing key is unknown or ambiguous");

      const key = await importJWK(matches[0]!, alg);
      const verificationTime = now();
      const { payload } = await jwtVerify(token, key, {
        algorithms: [alg],
        issuer: options.issuer,
        audience: options.audience,
        requiredClaims: ["exp", "iat", "nonce", "sub"],
        clockTolerance: CLOCK_TOLERANCE_SECONDS,
        currentDate: verificationTime,
      });

      if (payload.iss !== options.issuer) throw new Error("ID token issuer must match exactly");
      if (
        typeof payload.sub !== "string" ||
        payload.sub.length < 1 ||
        payload.sub.length > 255 ||
        [...payload.sub].some((character) => character.codePointAt(0)! > 0x7f)
      ) {
        throw new Error("ID token subject must contain 1 to 255 ASCII characters");
      }
      if (typeof payload.aud === "string") {
        if (payload.aud !== options.audience) throw new Error("ID token audience must match exactly");
      } else if (Array.isArray(payload.aud)) {
        if (payload.aud.length === 0 || payload.aud.some((audience) => typeof audience !== "string" || audience.length === 0)) {
          throw new Error("ID token audience array is invalid");
        }
        if (!payload.aud.includes(options.audience)) throw new Error("ID token audience must include the configured client");
        if (payload.aud.length > 1 && payload.azp !== options.audience) {
          throw new Error("ID token with multiple audiences must identify this client as azp");
        }
      } else {
        throw new Error("ID token audience claim is required");
      }
      if (payload.azp !== undefined && payload.azp !== options.audience) {
        throw new Error("ID token authorized party must match exactly");
      }
      if (typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) throw new Error("ID token exp claim is required");
      if (typeof payload.iat !== "number" || !Number.isFinite(payload.iat)) throw new Error("ID token iat claim is required");
      if (payload.iat > Math.floor(verificationTime.getTime() / 1000) + CLOCK_TOLERANCE_SECONDS) {
        throw new Error("ID token was issued too far in the future");
      }
      if (typeof payload.nonce !== "string" || !constantTimeStringEqual(payload.nonce, expectedNonce)) {
        throw new Error("ID token nonce does not match");
      }
      return Object.freeze({ ...payload });
    },
  };
}
