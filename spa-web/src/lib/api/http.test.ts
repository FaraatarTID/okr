import { describe, expect, it } from "vitest";

import { jsonHeaders } from "@/lib/api/http";

describe("jsonHeaders", () => {
  it("omits JSON content type when includeJsonContentType is false", () => {
    expect(jsonHeaders("admin", false)).toEqual({
      "x-okr-actor": "admin",
    });
  });

  it("includes JSON content type by default", () => {
    expect(jsonHeaders("admin")).toEqual({
      "content-type": "application/json",
      "x-okr-actor": "admin",
    });
  });
});
