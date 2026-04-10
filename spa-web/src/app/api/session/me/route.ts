import { NextRequest, NextResponse } from "next/server";

import { BFF_ORIGIN, proxyToBff } from "@/lib/bff-proxy";

export async function GET(request: NextRequest): Promise<NextResponse> {
  return proxyToBff(request, `${BFF_ORIGIN}/session/me`);
}
