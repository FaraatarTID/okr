import { NextRequest, NextResponse } from "next/server";

import { BFF_ORIGIN, proxyToBff } from "@/lib/bff-proxy";
import { rejectCrossOrigin } from "@/lib/origin-guard";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function buildBackendUrl(request: NextRequest, segments: string[]): string {
  const pathSuffix = segments.map((segment) => encodeURIComponent(segment)).join("/");
  const query = request.nextUrl.search || "";
  return `${BFF_ORIGIN}/api/backend/${pathSuffix}${query}`;
}

async function proxyBackendPath(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  // Reads are safe methods and stay unguarded. Every other method changes state or is
  // POST-shaped, so it is refused when the browser says it came from another origin.
  // The BFF's double-submit CSRF check is the second, independent layer.
  if (request.method !== "GET" && request.method !== "HEAD") {
    const rejected = rejectCrossOrigin(request);
    if (rejected) {
      return rejected;
    }
  }
  const { path = [] } = await context.params;
  const targetUrl = buildBackendUrl(request, path);
  return proxyToBff(request, targetUrl);
}

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyBackendPath(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyBackendPath(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyBackendPath(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyBackendPath(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyBackendPath(request, context);
}
