import { describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { createServer } from "../src/server.js";
import { issueSessionToken } from "../src/session.js";

const config: BffConfig = {
  host: "127.0.0.1",
  port: 3001,
  backendApiUrl: "http://backend-api:8100",
  backendServiceToken: "test-token",
  backendSigningSecret: "test-signing-secret",
  backendSigningKeyId: "test-key-id",
  requestTimeoutMs: 5_000,
  sessionSecret: "test-session-secret",
  sessionTtlSeconds: 28_800,
  cookieSecure: false,
};

const cases = [
  ["node.get", { node_id: 1, node_type: "GOAL" }],
  ["node.detect_type", { node_id: 1 }],
  ["work_logs.by_task", { task_id: 1 }],
  ["experiments.for_kr", { key_result_id: 1 }],
  ["experiments.active_for_kr", { key_result_id: 1 }],
  ["alignments.context", { objective_id: 1 }],
  ["mindmap.root", { node_id: 1, node_type: "TASK" }],
] as const;

function sessionCookie(): string {
  const token = issueSessionToken({
    user: {
      id: 1,
      username: "f2_reader",
      display_name: "F2 Reader",
      role: "member",
      team_id: null,
      manager_id: null,
      must_change_password: false,
    },
    secret: config.sessionSecret,
    ttlSeconds: config.sessionTtlSeconds,
  });
  return `okr_spa_session=${encodeURIComponent(token)}`;
}

describe("F2 read actor boundary", () => {
  it.each(cases)("refuses actorless %s before backend fetch", async (kind, params) => {
    const fetchFn = vi.fn();
    const app = createServer(config, { fetchFn });
    try {
      const response = await app.inject({
        method: "POST",
        url: "/api/backend/v1/read/query",
        payload: { kind, params, actor_username: "forged-payload-actor" },
      });
      expect(response.statusCode).toBe(401);
      expect(response.json().code).toBe("MISSING_SESSION");
      expect(fetchFn).not.toHaveBeenCalled();
    } finally {
      await app.close();
    }
  });

  it.each(cases)("forwards verified session actor for %s", async (kind, params) => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ node: { id: 1 } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const app = createServer(config, { fetchFn });
    try {
      const response = await app.inject({
        method: "POST",
        url: "/api/backend/v1/read/query",
        headers: { cookie: sessionCookie() },
        payload: { kind, params },
      });
      expect(response.statusCode).toBe(200);
      expect(fetchFn).toHaveBeenCalledTimes(1);
      const request = fetchFn.mock.calls[0][1];
      expect(request.headers["x-okr-actor"]).toBe("f2_reader");
      expect(JSON.parse(String(request.body))).toMatchObject({ kind, params });
    } finally {
      await app.close();
    }
  });
});
