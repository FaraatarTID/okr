import { describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { createServer } from "../src/server.js";
import { issueSessionToken, type SessionUser } from "../src/session.js";

const baseConfig: BffConfig = {
  host: "127.0.0.1",
  port: 3001,
  backendApiUrl: "http://backend-api:8100",
  backendServiceToken: "test-token",
  backendSigningSecret: "test-signing-secret",
  requestTimeoutMs: 5_000,
  sessionSecret: "test-session-secret",
  sessionTtlSeconds: 28_800,
  cookieSecure: false,
};

const DEFAULT_USER: SessionUser = {
  id: 1,
  username: "member-1",
  display_name: "Member One",
  role: "member",
  team_id: 11,
  manager_id: null,
  must_change_password: false,
};

const NODE_CREATE_CASES = [
  {
    label: "goal",
    path: "/api/backend/v1/nodes/goal",
    expectedNodeType: "GOAL",
    payload: {
      user_id: "member-1",
      title: "Goal A",
      description: "Create goal via bff",
      actor_username: "member-1",
    },
  },
  {
    label: "objective",
    path: "/api/backend/v1/nodes/objective",
    expectedNodeType: "OBJECTIVE",
    payload: {
      goal_id: 51,
      title: "Objective A",
      description: "Create objective via bff",
      actor_username: "member-1",
    },
  },
  {
    label: "key_result",
    path: "/api/backend/v1/nodes/key_result",
    expectedNodeType: "KEY_RESULT",
    payload: {
      objective_id: 52,
      title: "KR A",
      description: "Create KR via bff",
      target_value: 100,
      unit: "%",
      actor_username: "member-1",
    },
  },
  {
    label: "task",
    path: "/api/backend/v1/nodes/task",
    expectedNodeType: "TASK",
    payload: {
      key_result_id: 53,
      title: "Task A",
      description: "Create task via bff",
      estimated_minutes: 30,
      actor_username: "member-1",
    },
  },
] as const;

const NODE_DELETE_CASES = [
  {
    label: "goal",
    path: "/api/backend/v1/nodes/goal/91",
    expectedNodeType: "GOAL",
  },
  {
    label: "objective",
    path: "/api/backend/v1/nodes/objective/91",
    expectedNodeType: "OBJECTIVE",
  },
  {
    label: "key_result",
    path: "/api/backend/v1/nodes/key_result/91",
    expectedNodeType: "KEY_RESULT",
  },
  {
    label: "task",
    path: "/api/backend/v1/nodes/task/91",
    expectedNodeType: "TASK",
  },
] as const;

function sessionCookie(user: SessionUser = DEFAULT_USER): string {
  const token = issueSessionToken({
    user,
    secret: baseConfig.sessionSecret,
    ttlSeconds: baseConfig.sessionTtlSeconds,
  });
  return `okr_spa_session=${encodeURIComponent(token)}`;
}

describe("spa-bff server", () => {
  it("returns health payload", async () => {
    const app = createServer(baseConfig, {
      fetchFn: vi.fn(),
    });

    const response = await app.inject({
      method: "GET",
      url: "/healthz",
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({
      status: "ok",
      service: "spa-bff",
      backendApiUrl: "http://backend-api:8100",
    });
  });

  it("creates session cookie via /session/login", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          user: {
            id: 2,
            username: "admin",
            display_name: "Admin",
            role: "admin",
            team_id: 9,
            manager_id: null,
            must_change_password: false,
          },
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );
    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/session/login",
      payload: {
        username: "admin",
        password: "secret",
      },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json().user.username).toBe("admin");
    const setCookie = response.headers["set-cookie"];
    expect(String(setCookie)).toContain("okr_spa_session=");
    expect(String(setCookie)).toContain("HttpOnly");
    expect(String(setCookie)).toContain("SameSite=Lax");
  });

  it("returns session user for /session/me", async () => {
    const app = createServer(baseConfig, { fetchFn: vi.fn() });
    const response = await app.inject({
      method: "GET",
      url: "/session/me",
      headers: {
        cookie: sessionCookie(),
      },
    });
    await app.close();
    expect(response.statusCode).toBe(200);
    expect(response.json().user.username).toBe("member-1");
  });

  it("rejects /session/me when cookie is missing", async () => {
    const app = createServer(baseConfig, { fetchFn: vi.fn() });
    const response = await app.inject({
      method: "GET",
      url: "/session/me",
    });
    await app.close();
    expect(response.statusCode).toBe(401);
  });

  it("clears session cookie on /session/logout", async () => {
    const app = createServer(baseConfig, { fetchFn: vi.fn() });
    const response = await app.inject({
      method: "POST",
      url: "/session/logout",
    });
    await app.close();
    expect(response.statusCode).toBe(200);
    const setCookie = String(response.headers["set-cookie"] ?? "");
    expect(setCookie).toContain("okr_spa_session=");
    expect(setCookie).toContain("Max-Age=0");
  });

  it("rejects non-allowlisted routes", async () => {
    const app = createServer(baseConfig, {
      fetchFn: vi.fn(),
    });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/state/forbidden",
      payload: { value: "x" },
      headers: { cookie: sessionCookie() },
    });
    await app.close();

    expect(response.statusCode).toBe(403);
    expect(response.json().error).toContain("allowlisted");
  });

  it("uses session actor for actor-scoped routes and ignores forged client actor header", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      headers: {
        cookie: sessionCookie({
          ...DEFAULT_USER,
          username: "admin",
          role: "admin",
        }),
        "x-okr-actor": "forged-user",
      },
      payload: {
        kind: "node",
        params: { node_type: "GOAL", node_id: 1 },
        actor_username: "forged-payload-user",
      },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ status: "ok" });
    expect(fetchFn).toHaveBeenCalledTimes(1);

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-service-token"]).toBe("test-token");
    expect(headers["x-okr-actor"]).toBe("admin");
    expect(headers["x-okr-signature"]).toMatch(/^[a-f0-9]{64}$/);
    expect(headers["x-okr-timestamp"]).toMatch(/^\d+$/);
    expect(headers["x-okr-nonce"]).toMatch(/^[a-f0-9]{32}$/);
  });

  it("rejects actor-scoped routes when session is missing", async () => {
    const fetchFn = vi.fn();
    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      payload: {
        kind: "cycles.active",
        params: {},
      },
    });
    await app.close();

    expect(response.statusCode).toBe(401);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("allows login route through backend proxy without session", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: false, error_code: "INVALID_CREDENTIALS" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );
    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/auth/login",
      payload: {
        username: "admin",
        password: "bad",
      },
    });
    await app.close();
    expect(response.statusCode).toBe(401);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("omits signing headers when signing secret is not configured", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(
      {
        ...baseConfig,
        backendSigningSecret: "",
      },
      { fetchFn },
    );

    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      headers: { cookie: sessionCookie() },
      payload: { kind: "atlas_scope", params: {}, actor_username: "member-1" },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-service-token"]).toBe("test-token");
    expect(headers["x-okr-signature"]).toBeUndefined();
    expect(headers["x-okr-timestamp"]).toBeUndefined();
    expect(headers["x-okr-nonce"]).toBeUndefined();
  });

  it("proxies timer route and preserves backend authorization error status", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Insufficient permissions." }), {
        status: 403,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/timer/start",
      headers: { cookie: sessionCookie() },
      payload: { task_id: 42, user_id: "member-1" },
    });
    await app.close();

    expect(response.statusCode).toBe(403);
    expect(response.json().detail).toContain("Insufficient");

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-actor"]).toBe("member-1");
  });

  it("proxies timer stop success response payload", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          work_log_id: 701,
          task_id: 42,
          duration_minutes: 18,
          start_time: "2026-02-25T10:00:00",
          end_time: "2026-02-25T10:18:00",
          summary: "Completed focus run",
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/timer/stop",
      headers: { cookie: sessionCookie() },
      payload: { task_id: 42, user_id: "member-1", summary: "Completed focus run" },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({
      work_log_id: 701,
      task_id: 42,
      duration_minutes: 18,
      start_time: "2026-02-25T10:00:00",
      end_time: "2026-02-25T10:18:00",
      summary: "Completed focus run",
    });
  });

  it("proxies node update mutation and returns payload", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 77,
          node_type: "TASK",
          title: "Task A",
          description: "Refined by SPA probe",
          progress: 60,
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "PATCH",
      url: "/api/backend/v1/nodes/task/77",
      headers: { cookie: sessionCookie() },
      payload: {
        actor_username: "member-1",
        updates: { title: "Task A", description: "Refined by SPA probe", progress: 60 },
      },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({
      id: 77,
      node_type: "TASK",
      title: "Task A",
      description: "Refined by SPA probe",
      progress: 60,
    });

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-actor"]).toBe("member-1");
  });

  it("proxies ai analyze-node route and returns payload", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          overall_score: 82,
          summary: "Trajectory is improving with remaining task-level variance.",
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/ai/analyze-node",
      headers: { cookie: sessionCookie() },
      payload: {
        node_id: 77,
        node_type: "KEY_RESULT",
        actor_username: "payload-user",
      },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json().overall_score).toBe(82);

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-actor"]).toBe("member-1");
  });

  it("proxies ai team-coach route and preserves backend bad-request status", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "AI provider unavailable" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/ai/team-coach",
      headers: { cookie: sessionCookie() },
      payload: {
        actor_username: "payload-user",
        team_data: { total_krs: 9, avg_confidence: 7.2 },
      },
    });
    await app.close();

    expect(response.statusCode).toBe(400);
    expect(response.json().detail).toContain("unavailable");
  });

  it("proxies ai strategy-pulse route and returns payload", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          burnout_risk: "Elevated",
          gap_signals: ["Objective A: STALLED (severity 74)"],
          predictive_outlook: "Execution risk is manageable with focused triage.",
          portfolio_actions: ["Reprioritize high-severity stalled objectives."],
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/ai/strategy-pulse",
      headers: {
        cookie: sessionCookie({ ...DEFAULT_USER, username: "manager-1", role: "manager" }),
      },
      payload: {
        actor_username: "payload-user",
        cycle_id: 8,
      },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json().burnout_risk).toBe("Elevated");

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-actor"]).toBe("manager-1");
  });

  it.each(NODE_CREATE_CASES)(
    "proxies node create route for $label and returns payload",
    async ({ path, expectedNodeType, payload }) => {
      const fetchFn = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: 901,
            node_type: expectedNodeType,
            title: payload.title,
            description: payload.description,
            progress: 0,
          }),
          {
            status: 201,
            headers: { "content-type": "application/json" },
          },
        ),
      );

      const app = createServer(baseConfig, { fetchFn });
      const response = await app.inject({
        method: "POST",
        url: path,
        headers: { cookie: sessionCookie() },
        payload,
      });
      await app.close();

      expect(response.statusCode).toBe(201);
      expect(response.json().node_type).toBe(expectedNodeType);

      const [url, options] = fetchFn.mock.calls[0] as [string, RequestInit];
      expect(String(url)).toContain(path.replace("/api/backend", ""));
      const headers = (options.headers ?? {}) as Record<string, string>;
      expect(headers["x-okr-actor"]).toBe("member-1");
    },
  );

  it.each(NODE_DELETE_CASES)(
    "proxies node delete route for $label and returns payload",
    async ({ path, expectedNodeType }) => {
      const fetchFn = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: 91,
            node_type: expectedNodeType,
            deleted: true,
          }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        ),
      );

      const app = createServer(baseConfig, { fetchFn });
      const response = await app.inject({
        method: "DELETE",
        url: path,
        headers: { cookie: sessionCookie() },
      });
      await app.close();

      expect(response.statusCode).toBe(200);
      expect(response.json()).toEqual({
        id: 91,
        node_type: expectedNodeType,
        deleted: true,
      });
    },
  );

  it("proxies node delete route and preserves not-found status", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Node not found." }), {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "DELETE",
      url: "/api/backend/v1/nodes/task/999",
      headers: { cookie: sessionCookie() },
    });
    await app.close();

    expect(response.statusCode).toBe(404);
    expect(response.json().detail).toContain("not found");
  });
});
