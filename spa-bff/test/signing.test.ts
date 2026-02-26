import { describe, expect, it } from "vitest";

import {
  bodyDigestHex,
  buildBackendSecurityHeaders,
  canonicalSigningPayload,
  requestSignatureHex,
} from "../src/signing.js";

describe("signing helpers", () => {
  it("builds canonical payload using backend contract ordering", () => {
    const payload = canonicalSigningPayload({
      method: "post",
      path: "/v1/read/query",
      timestamp: "1700000000",
      nonce: "abc123",
      bodyDigest: "deadbeef",
    });
    expect(payload).toBe("POST\n/v1/read/query\n1700000000\nabc123\ndeadbeef");
  });

  it("produces deterministic signature for fixed input", () => {
    const body = new TextEncoder().encode('{"kind":"atlas_snapshot"}');
    const digest = bodyDigestHex(body);
    expect(digest).toHaveLength(64);

    const signature = requestSignatureHex({
      method: "POST",
      path: "/v1/read/query",
      timestamp: "1700000000",
      nonce: "0123456789abcdef",
      bodyBytes: body,
      signingSecret: "super-secret",
    });
    expect(signature).toHaveLength(64);
    expect(signature).toMatch(/^[a-f0-9]{64}$/);
  });

  it("includes service token and signing headers when secret exists", () => {
    const headers = buildBackendSecurityHeaders({
      method: "POST",
      path: "/v1/timer/start",
      bodyBytes: new TextEncoder().encode("{}"),
      serviceToken: "token-1",
      signingSecret: "signing-1",
      nowEpochSeconds: 1700000000,
      nonce: "abcdefabcdefabcdefabcdefabcdefab",
    });

    expect(headers["x-okr-service-token"]).toBe("token-1");
    expect(headers["x-okr-timestamp"]).toBe("1700000000");
    expect(headers["x-okr-nonce"]).toBe("abcdefabcdefabcdefabcdefabcdefab");
    expect(headers["x-okr-signature"]).toMatch(/^[a-f0-9]{64}$/);
  });
});

