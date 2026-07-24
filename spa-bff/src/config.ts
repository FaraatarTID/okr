export interface BffConfig {
  host: string;
  port: number;
  backendApiUrl: string;
  backendServiceToken: string;
  backendSigningSecret: string;
  requestTimeoutMs: number;
  sessionSecret: string;
  sessionTtlSeconds: number;
  cookieSecure: boolean;
}

const DEFAULT_HOST = "0.0.0.0";
const DEFAULT_PORT = 3001;
const DEFAULT_TIMEOUT_MS = 20_000;
const DEFAULT_SESSION_TTL_SECONDS = 28_800;

function parseBool(value: string | undefined, fallback: boolean): boolean {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return fallback;
  }
  return ["1", "true", "yes", "on"].includes(normalized);
}

function parsePositiveInt(value: string | undefined, fallback: number, key: string): number {
  if (!value || !value.trim()) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`Invalid ${key}: expected positive integer, received '${value}'.`);
  }
  return parsed;
}

function requireNonEmpty(value: string | undefined, key: string): string {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    throw new Error(`${key} is required for spa-bff runtime.`);
  }
  return normalized;
}

const INSECURE_SECRETS = new Set([
  "change-me",
  "CHANGE_ME",
  "CHANGE_ME_BFF_SESSION_SECRET",
  "changeme",
  "secret",
  "your-secret-here",
]);

function requireSessionSecret(env: NodeJS.ProcessEnv): string {
  const secret = String(env.BFF_SESSION_SECRET ?? "").trim();
  const isDevelopment = String(env.NODE_ENV ?? "").trim().toLowerCase() === "development";
  if (!secret) {
    if (isDevelopment) {
      const crypto = require("crypto");
      return crypto.randomBytes(32).toString("hex");
    }
    throw new Error("BFF_SESSION_SECRET is required for non-development spa-bff runtime.");
  }

  if (INSECURE_SECRETS.has(secret)) {
    throw new Error(
      `BFF_SESSION_SECRET is set to an insecure default value ("${secret}"). ` +
      `Generate a strong random secret: openssl rand -hex 32`,
    );
  }

  if (secret.length < 32) {
    throw new Error(
      "BFF_SESSION_SECRET must be at least 32 characters. " +
      "Generate one: openssl rand -hex 32",
    );
  }

  return secret;
}

function normalizeBackendUrl(raw: string): string {
  const candidate = String(raw).trim();
  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error(`Invalid OKR_BACKEND_API_URL: '${raw}'.`);
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(
      `Invalid OKR_BACKEND_API_URL protocol '${parsed.protocol}'. Use http:// or https://.`,
    );
  }

  parsed.pathname = "";
  parsed.search = "";
  parsed.hash = "";
  const normalized = parsed.toString().replace(/\/$/, "");
  if (!normalized) {
    throw new Error("OKR_BACKEND_API_URL resolved to an empty value.");
  }
  return normalized;
}

export function readConfig(env: NodeJS.ProcessEnv = process.env): BffConfig {
  const backendApiUrl = normalizeBackendUrl(requireNonEmpty(env.OKR_BACKEND_API_URL, "OKR_BACKEND_API_URL"));
  const backendServiceToken = requireNonEmpty(
    env.OKR_BACKEND_SERVICE_TOKEN,
    "OKR_BACKEND_SERVICE_TOKEN",
  );

  const sessionSecret = requireSessionSecret(env);
  const sessionTtlSeconds = parsePositiveInt(
    env.BFF_SESSION_TTL_SECONDS,
    DEFAULT_SESSION_TTL_SECONDS,
    "BFF_SESSION_TTL_SECONDS",
  );
  const cookieSecure = parseBool(
    env.BFF_COOKIE_SECURE,
    String(env.NODE_ENV ?? "").trim().toLowerCase() !== "development",
  );

  return {
    host: String(env.BFF_HOST ?? DEFAULT_HOST).trim() || DEFAULT_HOST,
    port: parsePositiveInt(env.BFF_PORT, DEFAULT_PORT, "BFF_PORT"),
    backendApiUrl,
    backendServiceToken,
    backendSigningSecret: String(env.OKR_BACKEND_SIGNING_SECRET ?? "").trim(),
    requestTimeoutMs: parsePositiveInt(env.BFF_REQUEST_TIMEOUT_MS, DEFAULT_TIMEOUT_MS, "BFF_REQUEST_TIMEOUT_MS"),
    sessionSecret,
    sessionTtlSeconds,
    cookieSecure,
  };
}
