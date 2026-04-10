import { NextRequest, NextResponse } from "next/server";

import { BFF_ORIGIN, proxyToBff } from "@/lib/bff-proxy";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function buildBackendUrl(request: NextRequest, segments: string[]): string {
  const pathSuffix = segments.map((segment) => encodeURIComponent(segment)).join("/");
  const query = request.nextUrl.search || "";
  return `${BFF_ORIGIN}/api/backend/${pathSuffix}${query}`;
}

async function proxyBackendPath(request: NextRequest, context: RouteContext): Promise<NextResponse> {
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
