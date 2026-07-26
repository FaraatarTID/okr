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
const PRODUCTION_ENVS = new Set(["prod", "production"]);

const INSECURE_BACKEND_VALUES = new Set([
  "CHANGE_ME",
  "CHANGE_ME_SIGNING_SECRET",
  "CHANGE_ME_SHARED_TOKEN",
  "your-secret-here",
  "change-me",
  "changeme",
  "replace-me",
  "replace_me",
]);

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

function _isProductionRuntime(env: NodeJS.ProcessEnv): boolean {
  const runtime = String(
    env.OKR_RUNTIME_ENV ?? env.OKR_ENV ?? env.NODE_ENV ?? "development",
  ).trim().toLowerCase();
  return PRODUCTION_ENVS.has(runtime);
}

function _looksLikePlaceholder(value: string): boolean {
  const raw = String(value || "").trim();
  if (!raw) {
    return true;
  }
  if (raw.startsWith("<") && raw.endsWith(">")) {
    return true;
  }
  const lowered = raw.toLowerCase();
  for (const token of INSECURE_BACKEND_VALUES) {
    const normalizedToken = String(token).trim().toLowerCase();
    if (!normalizedToken) {
      continue;
    }
    if (lowered === normalizedToken || lowered.startsWith(`${normalizedToken}_`)) {
      return true;
    }
  }
  return false;
}

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

function validateProductionConfig(config: BffConfig, env: NodeJS.ProcessEnv): void {
  if (!_isProductionRuntime(env)) {
    return;
  }

  if (_looksLikePlaceholder(config.backendServiceToken)) {
    throw new Error(
      "OKR_BACKEND_SERVICE_TOKEN must be set to a strong non-placeholder value in production.",
    );
  }
  if (config.backendServiceToken.length < 24) {
    throw new Error(
      "OKR_BACKEND_SERVICE_TOKEN must be at least 24 characters in production.",
    );
  }

  if (_looksLikePlaceholder(config.backendSigningSecret)) {
    throw new Error(
      "OKR_BACKEND_SIGNING_SECRET must be set to a strong non-placeholder value in production.",
    );
  }
  if (config.backendSigningSecret.length < 32) {
    throw new Error(
      "OKR_BACKEND_SIGNING_SECRET must be at least 32 characters in production.",
    );
  }

  if (!config.cookieSecure) {
    throw new Error(
      "BFF_COOKIE_SECURE must be true in production to protect session cookies.",
    );
  }
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

  const config: BffConfig = {
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

  validateProductionConfig(config, env);
  return config;
}
