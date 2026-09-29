import { NextRequest, NextResponse } from "next/server";

import { BFF_ORIGIN, proxyToBff } from "@/lib/bff-proxy";
import { rejectCrossOrigin } from "@/lib/origin-guard";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const rejected = rejectCrossOrigin(request);
  if (rejected) {
    return rejected;
  }
  return proxyToBff(request, `${BFF_ORIGIN}/session/logout`);
}
