import { NextResponse } from "next/server";

import { BFF_ORIGIN } from "@/lib/bff-proxy";

export async function GET(): Promise<NextResponse> {
  try {
    const response = await fetch(`${BFF_ORIGIN}/healthz`, {
      cache: "no-store",
    });
    return new NextResponse(response.body, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json({ status: "unavailable" }, { status: 503 });
  }
}
