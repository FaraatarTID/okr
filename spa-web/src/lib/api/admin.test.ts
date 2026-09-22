import { describe, expect, it } from "vitest";

import type { ReadQueryResponse } from "@/lib/api/backend-schema";
import { toAuditSummaryView } from "@/lib/api/admin";

describe("toAuditSummaryView", () => {
  it("projects generated read-query fields and drops malformed screen data", () => {
    const view = toAuditSummaryView({
      total_events: 12,
      latest_event_at: "2026-09-22T08:00:00Z",
      by_actor_role: [
        { value: "admin", count: 3 },
        { value: {}, count: "not-a-number" },
      ],
      recent_events: [
        { id: 9, actor: "alice", action: "read", result: "success" },
        { id: "invalid", actor: "ignored" },
      ],
    } as ReadQueryResponse);

    expect(view).toMatchObject({
      total_events: 12,
      latest_event_at: "2026-09-22T08:00:00Z",
      by_actor_role: [{ value: "admin", count: 3 }],
      recent_events: [{ id: 9, actor: "alice", action: "read", result: "success" }],
    });
  });
});
