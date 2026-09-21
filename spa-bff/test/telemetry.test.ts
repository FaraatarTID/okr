import { describe, expect, it } from "vitest";
import { extractPublicTraceContext, injectSuppliedTraceContext } from "../src/telemetry.js";

describe("public trace context policy", () => {
  it("rejects arbitrary public trace context by default", () => {
    const result = extractPublicTraceContext({ traceparent: "00-11111111111111111111111111111111-2222222222222222-01" }, false);
    expect(result.traceparent).not.toContain("11111111111111111111111111111111");
  });
  it("injects only the sanitized BFF context into backend requests", () => {
    const headers: Record<string, string> = {};
    injectSuppliedTraceContext(headers, { traceparent: "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01" });
    expect(headers.traceparent).toBe("00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01");
  });
});
