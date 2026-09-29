// @vitest-environment node
//
// The default happy-dom environment strips `Origin`, `Host` and `Sec-Fetch-*` from a
// constructed request, which would make every case below pass vacuously.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { classifyOrigin, rejectCrossOrigin } from "@/lib/origin-guard";

function headers(entries: Record<string, string>): Headers {
  return new Headers(entries);
}

describe("classifyOrigin", () => {
  describe("Sec-Fetch-Site, when the browser supplies it", () => {
    it("allows same-origin and user-initiated navigations", () => {
      expect(classifyOrigin(headers({ "sec-fetch-site": "same-origin" }))).toBeNull();
      expect(classifyOrigin(headers({ "sec-fetch-site": "none" }))).toBeNull();
    });

    it("rejects cross-site and same-site", () => {
      expect(classifyOrigin(headers({ "sec-fetch-site": "cross-site" }))).toBe("cross_site_fetch");
      // A sibling subdomain is not this origin; same-site must not be waved through.
      expect(classifyOrigin(headers({ "sec-fetch-site": "same-site" }))).toBe("cross_site_fetch");
    });

    it("takes precedence over an Origin header that would match", () => {
      // The browser-set signal wins, so a matching Origin cannot rescue a cross-site fetch.
      expect(
        classifyOrigin(
          headers({
            "sec-fetch-site": "cross-site",
            origin: "https://app.example",
            host: "app.example",
          }),
        ),
      ).toBe("cross_site_fetch");
    });
  });

  describe("Origin against Host, when Sec-Fetch-Site is absent", () => {
    it("allows an Origin naming the host the request was addressed to", () => {
      expect(
        classifyOrigin(headers({ origin: "https://app.example", host: "app.example" })),
      ).toBeNull();
    });

    it("compares host and port, case-insensitively", () => {
      expect(
        classifyOrigin(headers({ origin: "http://APP.example:3000", host: "app.example:3000" })),
      ).toBeNull();
      expect(
        classifyOrigin(headers({ origin: "http://app.example:3000", host: "app.example:4000" })),
      ).toBe("origin_mismatch");
    });

    it("rejects a foreign Origin", () => {
      expect(
        classifyOrigin(headers({ origin: "https://evil.example", host: "app.example" })),
      ).toBe("origin_mismatch");
    });

    it("rejects a look-alike host that merely contains the real one", () => {
      expect(
        classifyOrigin(headers({ origin: "https://app.example.evil.com", host: "app.example" })),
      ).toBe("origin_mismatch");
      expect(
        classifyOrigin(headers({ origin: "https://evilapp.example", host: "app.example" })),
      ).toBe("origin_mismatch");
    });

    it("rejects the literal null origin and an unparseable one", () => {
      expect(classifyOrigin(headers({ origin: "null", host: "app.example" }))).toBe(
        "origin_mismatch",
      );
      expect(classifyOrigin(headers({ origin: "not a url", host: "app.example" }))).toBe(
        "origin_mismatch",
      );
    });

    it("prefers X-Forwarded-Host over Host, using its first entry", () => {
      expect(
        classifyOrigin(
          headers({
            origin: "https://public.example",
            host: "spa-web:3000",
            "x-forwarded-host": "public.example, proxy.internal",
          }),
        ),
      ).toBeNull();
    });

    it("fails closed when an Origin is present but no host is known", () => {
      expect(classifyOrigin(headers({ origin: "https://app.example" }))).toBe(
        "origin_unverifiable",
      );
    });
  });

  it("allows a request carrying neither header, which is not a browser", () => {
    // curl, the SLO and smoke probes, health checks. Documented so the allowance is a
    // decision and not an accident of which branch returns first.
    expect(classifyOrigin(headers({}))).toBeNull();
    expect(classifyOrigin(headers({ host: "app.example" }))).toBeNull();
  });
});

describe("rejectCrossOrigin", () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;
  const logged: string[] = [];

  beforeEach(() => {
    logged.length = 0;
    warnSpy = vi.spyOn(console, "warn").mockImplementation((...args) => {
      logged.push(args.map((value) => String(value)).join(" "));
    });
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  function request(entries: Record<string, string>): NextRequest {
    return new NextRequest("https://app.example/api/session/login", {
      method: "POST",
      headers: { cookie: "okr_spa_session=COOKIE_SECRET", ...entries },
    });
  }

  it("returns a 403 INVALID_ORIGIN response for a cross-origin request", async () => {
    const response = rejectCrossOrigin(
      request({ origin: "https://evil.example", host: "app.example" }),
    );

    expect(response).not.toBeNull();
    expect(response?.status).toBe(403);
    await expect(response?.json()).resolves.toMatchObject({ code: "INVALID_ORIGIN" });
  });

  it("returns null for a same-origin request", () => {
    expect(
      rejectCrossOrigin(request({ origin: "https://app.example", host: "app.example" })),
    ).toBeNull();
    expect(logged).toHaveLength(0);
  });

  it("logs the reason and route but never the cookie", () => {
    rejectCrossOrigin(request({ origin: "https://evil.example", host: "app.example" }));

    expect(logged).toHaveLength(1);
    const payload = JSON.parse(logged[0] ?? "{}") as Record<string, unknown>;
    expect(payload.event).toBe("spa_web_origin_rejected");
    expect(payload.reason).toBe("origin_mismatch");
    expect(payload.route).toBe("/api/session/login");
    expect(payload.status).toBe(403);
    expect(logged[0]).not.toContain("COOKIE_SECRET");
  });
});
