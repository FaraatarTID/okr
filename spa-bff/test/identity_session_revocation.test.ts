import { describe, expect, it } from "vitest";
import { issueSessionToken, revokeSessionsForIdentity, verifySessionToken } from "../src/session.js";

describe("provider-neutral identity session revocation", () => {
  it("revokes all local sessions for a deactivated external subject", () => {
    const input = {
      user: {
        id: 42,
        username: "user@example.test",
        display_name: "Example User",
        role: "member",
        external_subject: "subject-42",
      },
      secret: "test-secret",
      nowEpochSeconds: 1_700_000_000,
      ttlSeconds: 3600,
    };
    const first = issueSessionToken(input);
    const second = issueSessionToken(input);
    expect(revokeSessionsForIdentity("subject-42")).toBe(2);
    expect(verifySessionToken({ token: first, secret: input.secret, nowEpochSeconds: input.nowEpochSeconds + 1 })).toBeNull();
    expect(verifySessionToken({ token: second, secret: input.secret, nowEpochSeconds: input.nowEpochSeconds + 1 })).toBeNull();
  });

  it("does not revoke local-password sessions with no external subject", () => {
    const token = issueSessionToken({
      user: { id: 7, username: "local", display_name: "Local", role: "admin" },
      secret: "test-secret",
      nowEpochSeconds: 1_700_000_000,
      ttlSeconds: 3600,
    });
    expect(revokeSessionsForIdentity("subject-absent")).toBe(0);
    expect(verifySessionToken({ token, secret: "test-secret", nowEpochSeconds: 1_700_000_001 })).not.toBeNull();
  });
});
