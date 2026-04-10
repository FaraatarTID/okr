import { NextRequest, NextResponse } from "next/server";

import { BFF_ORIGIN, proxyToBff } from "@/lib/bff-proxy";

export async function POST(request: NextRequest): Promise<NextResponse> {
  return proxyToBff(request, `${BFF_ORIGIN}/session/logout`);
}
