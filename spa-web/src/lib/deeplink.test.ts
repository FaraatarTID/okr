import { describe, expect, it } from "vitest";

import { buildDeepLinkQuery, parseDeepLink } from "@/lib/deeplink";

describe("deeplink lens normalization", () => {
  it("maps legacy scope/branch lens aliases to canonical values", () => {
    expect(parseDeepLink("?lens=scope").lens).toBe("focus");
    expect(parseDeepLink("?lens=branch").lens).toBe("owner");
  });

  it("serializes only canonical lens values", () => {
    expect(buildDeepLinkQuery({ lens: "scope" })).toBe("");
    expect(buildDeepLinkQuery({ lens: "branch" })).toBe("lens=owner");
  });
});
