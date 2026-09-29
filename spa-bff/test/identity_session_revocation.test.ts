import { afterEach, describe, expect, it, vi } from "vitest";
import { issueSessionToken, revokeSessionsForIdentity, verifySessionToken } from "../src/session.js";

describe("deferred external-subject session bookkeeping", () => {
  afterEach(() => vi.useRealTimers());

  it("does not let local external-subject bookkeeping decide cookie authentication", () => {
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
    expect(revokeSessionsForIdentity("subject-42", input.nowEpochSeconds + 1)).toBe(2);
    expect(verifySessionToken({ token: first, secret: input.secret, nowEpochSeconds: input.nowEpochSeconds + 1 })).not.toBeNull();
    expect(verifySessionToken({ token: second, secret: input.secret, nowEpochSeconds: input.nowEpochSeconds + 1 })).not.toBeNull();
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

  it("prunes bookkeeping on helper access only after the accepted expiry second", () => {
    const now = 1_700_000_000;
    const expiresAt = now + 60;
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now * 1000));
    const token = issueSessionToken({
      user: {
        id: 43,
        username: "boundary@example.test",
        display_name: "Boundary User",
        role: "member",
        external_subject: "subject-boundary",
      },
      secret: "test-secret",
      nowEpochSeconds: now,
      ttlSeconds: 60,
    });

    vi.setSystemTime(new Date(expiresAt * 1000));
    expect(verifySessionToken({ token, secret: "test-secret", nowEpochSeconds: expiresAt })).not.toBeNull();
    vi.setSystemTime(new Date((expiresAt + 1) * 1000));
    expect(revokeSessionsForIdentity("subject-boundary")).toBe(0);
  });

  it("prunes expired entries when issuing a later credential", () => {
    const now = 1_700_000_100;
    const expiresAt = now + 60;
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now * 1000));
    const user = {
      id: 44,
      username: "repeat@example.test",
      display_name: "Repeat User",
      role: "member",
      external_subject: "subject-repeat",
    };
    issueSessionToken({ user, secret: "test-secret", nowEpochSeconds: now, ttlSeconds: 60 });

    const nextIat = expiresAt + 1;
    vi.setSystemTime(new Date(nextIat * 1000));
    issueSessionToken({ user, secret: "test-secret", nowEpochSeconds: nextIat, ttlSeconds: 60 });
    expect(revokeSessionsForIdentity("subject-repeat")).toBe(1);
  });
});
