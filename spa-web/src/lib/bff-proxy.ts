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
    return NextResponse.json(
      {
        error: "BFF request failed.",
      },
      { status: 502 },
    );
  }
}
