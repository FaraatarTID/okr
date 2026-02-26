import { describe, expect, it } from "vitest";

import { isAllowlistedRoute, normalizeBackendPath, requiresActorHeader } from "../src/allowlist.js";

describe("normalizeBackendPath", () => {
  it("normalizes a valid path", () => {
    expect(normalizeBackendPath("v1/read/query")).toBe("/v1/read/query");
    expect(normalizeBackendPath("/v1/timer/start")).toBe("/v1/timer/start");
  });

  it("rejects invalid or unsafe values", () => {
    expect(normalizeBackendPath("")).toBeNull();
    expect(normalizeBackendPath("/healthz")).toBeNull();
    expect(normalizeBackendPath("../v1/read/query")).toBeNull();
    expect(normalizeBackendPath("/v1/read/query?x=1")).toBeNull();
  });
});

describe("isAllowlistedRoute", () => {
  it("allows known routes with correct method", () => {
    expect(isAllowlistedRoute("POST", "/v1/auth/login")).toBe(true);
    expect(isAllowlistedRoute("POST", "/v1/read/atlas/snapshot")).toBe(true);
    expect(isAllowlistedRoute("POST", "/v1/ai/analyze-node")).toBe(true);
    expect(isAllowlistedRoute("POST", "/v1/ai/team-coach")).toBe(true);
    expect(isAllowlistedRoute("POST", "/v1/ai/strategy-pulse")).toBe(true);
    expect(isAllowlistedRoute("GET", "/v1/admin/ai-health")).toBe(true);
    expect(isAllowlistedRoute("PATCH", "/v1/nodes/task/42")).toBe(true);
    expect(isAllowlistedRoute("DELETE", "/v1/work-logs/77")).toBe(true);
  });

  it("allows node CRUD routes for all pilot node types", () => {
    expect(isAllowlistedRoute("POST", "/v1/nodes/goal")).toBe(true);
    expect(isAllowlistedRoute("POST", "/v1/nodes/objective")).toBe(true);
    expect(isAllowlistedRoute("POST", "/v1/nodes/key_result")).toBe(true);
    expect(isAllowlistedRoute("POST", "/v1/nodes/task")).toBe(true);

    expect(isAllowlistedRoute("PATCH", "/v1/nodes/goal/11")).toBe(true);
    expect(isAllowlistedRoute("PATCH", "/v1/nodes/objective/11")).toBe(true);
    expect(isAllowlistedRoute("PATCH", "/v1/nodes/key_result/11")).toBe(true);
    expect(isAllowlistedRoute("PATCH", "/v1/nodes/task/11")).toBe(true);

    expect(isAllowlistedRoute("DELETE", "/v1/nodes/goal/11")).toBe(true);
    expect(isAllowlistedRoute("DELETE", "/v1/nodes/objective/11")).toBe(true);
    expect(isAllowlistedRoute("DELETE", "/v1/nodes/key_result/11")).toBe(true);
    expect(isAllowlistedRoute("DELETE", "/v1/nodes/task/11")).toBe(true);
  });

  it("rejects unknown routes or invalid method/path combinations", () => {
    expect(isAllowlistedRoute("GET", "/v1/auth/login")).toBe(false);
    expect(isAllowlistedRoute("POST", "/v1/healthz")).toBe(false);
    expect(isAllowlistedRoute("OPTIONS", "/v1/read/query")).toBe(false);
    expect(isAllowlistedRoute("POST", "/v1/state/atlas")).toBe(false);
  });
});

describe("requiresActorHeader", () => {
  it("requires actor for actor-scoped routes", () => {
    expect(requiresActorHeader("POST", "/v1/read/query")).toBe(true);
    expect(requiresActorHeader("POST", "/v1/ai/analyze-node")).toBe(true);
    expect(requiresActorHeader("POST", "/v1/ai/strategy-pulse")).toBe(true);
    expect(requiresActorHeader("POST", "/v1/timer/start")).toBe(true);
    expect(requiresActorHeader("DELETE", "/v1/work-logs/77")).toBe(true);
  });

  it("does not require actor for login route", () => {
    expect(requiresActorHeader("POST", "/v1/auth/login")).toBe(false);
  });
});
