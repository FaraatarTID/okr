import { describe, expect, it } from "vitest";

import {
  clearSessionCookie,
  issueSessionCookie,
  issueSessionToken,
  parseCookieHeader,
  verifySessionToken,
} from "../src/session.js";

const USER = {
  id: 5,
  username: "admin",
  display_name: "Admin User",
  role: "admin",
  team_id: 1,
  manager_id: null,
  must_change_password: false,
} as const;

describe("session token helpers", () => {
  it("issues and verifies a signed token", () => {
    const token = issueSessionToken({
      user: USER,
      secret: "session-secret",
      nowEpochSeconds: 1_700_000_000,
      ttlSeconds: 600,
    });
    const verified = verifySessionToken({
      token,
      secret: "session-secret",
      nowEpochSeconds: 1_700_000_300,
    });
    expect(verified?.username).toBe("admin");
    expect(verified?.role).toBe("admin");
  });

  it("rejects tampered tokens", () => {
    const token = issueSessionToken({
      user: USER,
      secret: "session-secret",
      nowEpochSeconds: 1_700_000_000,
      ttlSeconds: 600,
    });
    const tampered = `${token.slice(0, -1)}a`;
    const verified = verifySessionToken({
      token: tampered,
      secret: "session-secret",
      nowEpochSeconds: 1_700_000_300,
    });
    expect(verified).toBeNull();
  });

  it("rejects expired tokens", () => {
    const token = issueSessionToken({
      user: USER,
      secret: "session-secret",
      nowEpochSeconds: 1_700_000_000,
      ttlSeconds: 60,
    });
    const verified = verifySessionToken({
      token,
      secret: "session-secret",
      nowEpochSeconds: 1_700_000_061,
    });
    expect(verified).toBeNull();
  });

  it("builds and clears secure cookie strings", () => {
    const setCookie = issueSessionCookie({
      token: "abc.def",
      ttlSeconds: 600,
      secure: true,
    });
    expect(setCookie).toContain("HttpOnly");
    expect(setCookie).toContain("SameSite=Lax");
    expect(setCookie).toContain("Secure");

    const clearCookie = clearSessionCookie({ secure: true });
    expect(clearCookie).toContain("Max-Age=0");
    expect(clearCookie).toContain("Expires=");
    expect(clearCookie).toContain("Secure");
  });

  it("parses cookie headers", () => {
    const parsed = parseCookieHeader("a=1; b=two");
    expect(parsed.a).toBe("1");
    expect(parsed.b).toBe("two");
  });

  it("skips cookies with malformed percent-encoding", () => {
    const parsed = parseCookieHeader("good=ok; bad=%ZZ; also=%; clean=yes");
    expect(parsed.good).toBe("ok");
    expect(parsed.bad).toBeUndefined();
    expect(parsed.also).toBeUndefined();
    expect(parsed.clean).toBe("yes");
  });

  it("returns empty object for header with only malformed cookies", () => {
    const parsed = parseCookieHeader("bad=%ZZ; worse=%");
    expect(Object.keys(parsed)).toHaveLength(0);
  });
});
