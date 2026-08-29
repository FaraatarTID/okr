import { describe, expect, it } from "vitest";

import { parseHealthz } from "./backend-schema";

describe("parseHealthz", () => {
  it("parses a full healthz payload", () => {
    const parsed = parseHealthz({
      status: "ok",
      data_access_mode: "database",
      configured_mode: "database",
      dead_jobs: 3,
    });
    expect(parsed).toEqual({
      status: "ok",
      data_access_mode: "database",
      configured_mode: "database",
      dead_jobs: 3,
    });
  });

  it("accepts null dead_jobs", () => {
    const parsed = parseHealthz({ status: "ok", dead_jobs: null });
    expect(parsed?.dead_jobs).toBeNull();
  });

  it("returns null for non-object bodies", () => {
    expect(parseHealthz("oops")).toBeNull();
    expect(parseHealthz(42)).toBeNull();
    expect(parseHealthz(null)).toBeNull();
  });

  it("tolerates unknown extra fields", () => {
    const parsed = parseHealthz({ status: "ok", future_field: true });
    expect(parsed?.status).toBe("ok");
  });
});
