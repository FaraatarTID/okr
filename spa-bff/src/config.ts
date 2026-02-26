export interface BffConfig {
  host: string;
  port: number;
  backendApiUrl: string;
  backendServiceToken: string;
  backendSigningSecret: string;
  requestTimeoutMs: number;
}

const DEFAULT_HOST = "0.0.0.0";
const DEFAULT_PORT = 3001;
const DEFAULT_TIMEOUT_MS = 90_000;

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

  return {
    host: String(env.BFF_HOST ?? DEFAULT_HOST).trim() || DEFAULT_HOST,
    port: parsePositiveInt(env.BFF_PORT, DEFAULT_PORT, "BFF_PORT"),
    backendApiUrl,
    backendServiceToken,
    backendSigningSecret: String(env.OKR_BACKEND_SIGNING_SECRET ?? "").trim(),
    requestTimeoutMs: parsePositiveInt(env.BFF_REQUEST_TIMEOUT_MS, DEFAULT_TIMEOUT_MS, "BFF_REQUEST_TIMEOUT_MS"),
  };
}
