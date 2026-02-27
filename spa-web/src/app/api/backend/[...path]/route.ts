import { NextRequest, NextResponse } from "next/server";

const BFF_ORIGIN = (process.env.BFF_PUBLIC_ORIGIN || "http://127.0.0.1:3001").replace(
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

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function buildBackendUrl(request: NextRequest, segments: string[]): string {
  const pathSuffix = segments.map((segment) => encodeURIComponent(segment)).join("/");
  const query = request.nextUrl.search || "";
  return `${BFF_ORIGIN}/api/backend/${pathSuffix}${query}`;
}

function shouldForwardBody(method: string): boolean {
  const normalized = String(method || "").toUpperCase();
  return !["GET", "HEAD"].includes(normalized);
}

async function proxyToBff(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path = [] } = await context.params;
  const targetUrl = buildBackendUrl(request, path);
  const headers = new Headers();
  const forwardHeaderNames = [
    "accept",
    "content-type",
    "x-okr-actor",
    "x-okr-idempotency-key",
    "x-request-id",
    "x-correlation-id",
  ];
  for (const headerName of forwardHeaderNames) {
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
    const detail =
      error instanceof Error && error.message
        ? error.message
        : String(error ?? "unknown proxy failure");
    return NextResponse.json(
      {
        error: "BFF request failed.",
        detail,
        bff_origin: BFF_ORIGIN,
      },
      { status: 502 },
    );
  }
}

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyToBff(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyToBff(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyToBff(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyToBff(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyToBff(request, context);
}
