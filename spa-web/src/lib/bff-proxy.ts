import { NextRequest, NextResponse } from "next/server";

export const BFF_ORIGIN = (process.env.BFF_PUBLIC_ORIGIN || "http://127.0.0.1:3001").replace(
  /\/$/,
  "",
);

const HOP_BY_HOP_RESPONSE_HEADERS = [
  "connection",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];

function shouldForwardBody(method: string): boolean {
  const normalized = String(method || "").toUpperCase();
  return !["GET", "HEAD"].includes(normalized);
}

const MAX_LOGGED_ERROR_LENGTH = 300;

/**
 * Mirrors the BFF's structured log shape — `event`, `method`, `route`,
 * `status`, `ts` — so a proxy failure can be grepped the same way on both sides
 * of the boundary. It logs the request pathname rather than the full URL, and
 * never headers, cookies or the body, so a credential cannot reach the log.
 */
function buildWebProxyLogPayload(
  event: string,
  request: NextRequest,
  status: number,
  opts?: Record<string, unknown>,
): Record<string, unknown> {
  return {
    event,
    method: request.method,
    route: request.nextUrl.pathname,
    status,
    ts: new Date().toISOString(),
    ...opts,
  };
}

function describeProxyError(error: unknown): {
  error_type: string;
  error_message: string;
  error_code?: string;
} {
  const name = (error as { name?: unknown } | null | undefined)?.name;
  const message = (error as { message?: unknown } | null | undefined)?.message;
  const cause = (error as { cause?: unknown } | null | undefined)?.cause;
  const code = (cause as { code?: unknown } | null | undefined)?.code;
  const described: {
    error_type: string;
    error_message: string;
    error_code?: string;
  } = {
    error_type: typeof name === "string" && name ? name : typeof error,
    error_message: (
      typeof message === "string" && message ? message : String(error ?? "")
    ).slice(0, MAX_LOGGED_ERROR_LENGTH),
  };
  if (typeof code === "string" && code) {
    described.error_code = code;
  }
  return described;
}

function targetPathname(targetUrl: string): string {
  try {
    return new URL(targetUrl).pathname;
  } catch {
    return "";
  }
}

export async function proxyToBff(
  request: NextRequest,
  targetUrl: string,
  options?: { forwardHeaders?: string[] },
): Promise<NextResponse> {
  const headers = new Headers();
  const forwardHeaders = options?.forwardHeaders ?? [
    "accept",
    "content-type",
    "x-okr-idempotency-key",
    "x-xsrf-token",
    "x-request-id",
    "x-correlation-id",
    // The private client-IP header set by our edge. Without this the BFF has no
    // client address to pass on, so every user shares one throttle bucket. See
    // docs/client-ip-trust-adr.md.
    "x-okr-client-ip",
    "cookie",
  ];
  for (const headerName of forwardHeaders) {
    const value = request.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  }

  let body: ArrayBuffer | undefined;
  if (shouldForwardBody(request.method)) {
    const buffered = await request.arrayBuffer();
    body = buffered.byteLength > 0 ? buffered : undefined;
  }
  if (!body) {
    headers.delete("content-type");
  }

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });

    const responseHeaders = new Headers(response.headers);
    for (const headerName of HOP_BY_HOP_RESPONSE_HEADERS) {
      responseHeaders.delete(headerName);
    }

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    // The BFF logs its own lifecycle, but a request that never reached it left
    // no trace there, so the failure is recorded on this side of the boundary.
    // The client still gets the same generic 502 as before.
    console.error(
      JSON.stringify(
        buildWebProxyLogPayload("spa_web_bff_proxy_error", request, 502, {
          target: targetPathname(targetUrl),
          ...describeProxyError(error),
        }),
      ),
    );
    return NextResponse.json(
      {
        error: "BFF request failed.",
      },
      { status: 502 },
    );
  }
}
