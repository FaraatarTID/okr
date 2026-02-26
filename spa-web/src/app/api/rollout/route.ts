import { NextResponse } from "next/server";

import { parseSpaRolloutConfig } from "@/lib/rollout";

export const dynamic = "force-dynamic";

export async function GET() {
  const config = parseSpaRolloutConfig({
    enabled: process.env.OKR_SPA_ROLLOUT_ENABLED,
    allow_all: process.env.OKR_SPA_ROLLOUT_ALLOW_ALL,
    team_ids: process.env.OKR_SPA_ROLLOUT_TEAM_IDS,
    usernames: process.env.OKR_SPA_ROLLOUT_USERNAMES,
    roles: process.env.OKR_SPA_ROLLOUT_ROLES,
    allow_preview_bypass: process.env.OKR_SPA_ROLLOUT_ALLOW_PREVIEW_BYPASS,
  });

  return NextResponse.json(config, {
    headers: {
      "cache-control": "no-store",
    },
  });
}
