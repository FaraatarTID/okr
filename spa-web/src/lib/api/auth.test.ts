import { describe, expect, it } from "vitest";

import {
  FORCED_PASSWORD_CHANGE_PARAM,
  FORCED_PASSWORD_CHANGE_PATH,
  forcedPasswordChangeLocation,
  type AuthUser,
} from "@/lib/api/auth";

const USER: AuthUser = {
  id: 7,
  username: "atlas-user",
  display_name: "Atlas User",
  role: "member",
};

describe("forcedPasswordChangeLocation", () => {
  it("sends a user owing a password change to the change flow", () => {
    const destination = forcedPasswordChangeLocation(
      { ...USER, must_change_password: true },
      "/dashboard",
    );

    const parsed = new URL(destination, "https://spa.test");
    expect(parsed.pathname).toBe(FORCED_PASSWORD_CHANGE_PATH);
    expect(parsed.searchParams.get(FORCED_PASSWORD_CHANGE_PARAM)).toBe("1");
    expect(parsed.searchParams.get("return_to")).toBe("/dashboard");
  });

  it("omits return_to when the origin route is unknown", () => {
    const destination = forcedPasswordChangeLocation({
      ...USER,
      must_change_password: true,
    });

    const parsed = new URL(destination, "https://spa.test");
    expect(parsed.searchParams.get(FORCED_PASSWORD_CHANGE_PARAM)).toBe("1");
    expect(parsed.searchParams.has("return_to")).toBe(false);
  });

  it("returns the requested route for a user with no pending change", () => {
    expect(
      forcedPasswordChangeLocation({ ...USER, must_change_password: false }, "/timeline"),
    ).toBe("/timeline");
  });

  it("treats a missing flag as no pending change", () => {
    expect(forcedPasswordChangeLocation(USER, "/weekly")).toBe("/weekly");
  });

  it("refuses to echo an absolute or protocol-relative return path", () => {
    expect(forcedPasswordChangeLocation(USER, "https://evil.test")).toBe("/");

    const destination = forcedPasswordChangeLocation(
      { ...USER, must_change_password: true },
      "//evil.test",
    );
    expect(destination).not.toContain("evil.test");
  });
});
