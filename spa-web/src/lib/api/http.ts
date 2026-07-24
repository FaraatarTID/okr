export async function responseDetail(response: Response): Promise<string> {
  let detail = `${response.status}`;
  try {
    const payload = (await response.json()) as {
      detail?: string;
      error?: string;
      error_code?: string;
      bff_origin?: string;
    };
    const message = String(payload.error || payload.detail || payload.error_code || detail);
    const reason = String(payload.detail || "").trim();
    const bffOrigin = String(payload.bff_origin || "").trim();
    const extra: string[] = [];
    if (reason && reason !== message) {
      extra.push(`reason: ${reason}`);
    }
    if (bffOrigin) {
      extra.push(`bff_origin: ${bffOrigin}`);
    }
    detail = extra.length > 0 ? `${message} (${extra.join("; ")})` : message;
  } catch {
    // ignore body parse failure
  }
  return detail;
}

export function jsonHeaders(actor?: string, includeJsonContentType = true): Record<string, string> {
  const headers: Record<string, string> = {};
  if (includeJsonContentType) {
    headers["content-type"] = "application/json";
  }
  if (actor) {
    headers["x-okr-actor"] = actor;
  }
  // Include CSRF token from cookie for state-changing requests
  const csrfToken = readCsrfTokenFromDocumentCookie();
  if (csrfToken) {
    headers["x-xsrf-token"] = csrfToken;
  }
  return headers;
}

function readCsrfTokenFromDocumentCookie(): string {
  if (typeof document === "undefined") {
    return "";
  }
  const match = document.cookie.match(/(?:^|;\s*)okr_csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function waitMs(durationMs: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, Math.max(0, Math.floor(durationMs)));
  });
}

export async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), Math.max(1, Math.floor(timeoutMs)));
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

export function isTransientNetworkError(error: unknown): boolean {
  const text = String(error instanceof Error ? error.message : error || "")
    .trim()
    .toLowerCase();
  if (!text) {
    return false;
  }
  return (
    text.includes("socket hang up") ||
    text.includes("econnreset") ||
    text.includes("econnrefused") ||
    text.includes("etimedout") ||
    text.includes("aborted") ||
    text.includes("networkerror") ||
    text.includes("fetch failed")
  );
}

export function isTransientCycleQueryFailure(status: number, detail: string): boolean {
  if (status >= 500) {
    return true;
  }
  const normalized = String(detail || "").trim().toLowerCase();
  return (
    normalized.includes("socket hang up") ||
    normalized.includes("econnreset") ||
    normalized.includes("econnrefused") ||
    normalized.includes("etimedout") ||
    normalized.includes("timeout")
  );
}

export function normalizeBackendDateTime(value: unknown): string {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const matched = text.match(
    /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?([zZ]|[+\-]\d{2}:\d{2})?$/,
  );
  if (!matched) {
    return text;
  }
  const [, datePart, timePart, fractionalRaw, timezoneRaw] = matched;
  const fractional = fractionalRaw ? `.${fractionalRaw.slice(0, 3).padEnd(3, "0")}` : "";
  const timezone = timezoneRaw ? (timezoneRaw.toUpperCase() === "Z" ? "Z" : timezoneRaw) : "Z";
  return `${datePart}T${timePart}${fractional}${timezone}`;
}

function stableStringHash(text: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = (hash * 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function idempotencyKey(scope: string, payload: unknown): string {
  const serialized = JSON.stringify(payload ?? {});
  const bucket = Math.floor(Date.now() / 15_000);
  return `${scope}:${bucket}:${stableStringHash(serialized)}`.slice(0, 255);
}

export function jsonHeadersWithIdempotency(
  actor: string | undefined,
  scope: string,
  payload: unknown,
): Record<string, string> {
  return {
    ...jsonHeaders(actor),
    "x-okr-idempotency-key": idempotencyKey(scope, payload),
  };
}

export interface RetryWithFetchOptions {
  maxAttempts?: number;
  perAttemptTimeoutMs?: number;
  baseDelayMs?: number;
  label: string;
}

export async function retryWithFetch<T>(
  fetchFn: () => Promise<Response>,
  handleSuccess: (response: Response) => Promise<T>,
  options: RetryWithFetchOptions,
): Promise<T> {
  const {
    maxAttempts = 4,
    perAttemptTimeoutMs = 8_000,
    baseDelayMs = 250,
    label,
  } = options;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    let response: Response;
    try {
      response = await fetchFn();
    } catch (error) {
      const retryable = isTransientNetworkError(error);
      if (retryable && attempt < maxAttempts) {
        await waitMs(baseDelayMs * 2 ** (attempt - 1));
        continue;
      }
      throw new Error(
        `${label} failed: ${String(error instanceof Error ? error.message : error)}`,
      );
    }

    if (response.ok) {
      return await handleSuccess(response);
    }

    const detail = await responseDetail(response);
    const retryable = isTransientCycleQueryFailure(response.status, detail);
    if (retryable && attempt < maxAttempts) {
      await waitMs(baseDelayMs * 2 ** (attempt - 1));
      continue;
    }
    throw new Error(`${label} failed: ${detail}`);
  }
  throw new Error(`${label} failed: retry attempts exhausted.`);
}
