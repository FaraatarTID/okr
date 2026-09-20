import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  cacheKeys,
  clearResourceCache,
  invalidateCache,
  isCacheFresh,
  readThroughCache,
  writeThroughCache,
} from "@/lib/resourceCache";

/** Let queued microtasks run so promise-driven cache state settles. */
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("resourceCache", () => {
  beforeEach(() => {
    clearResourceCache();
  });

  describe("readThroughCache", () => {
    it("issues one request when several callers read the same key together", async () => {
      const loader = vi.fn(async () => "value");

      const [first, second, third] = await Promise.all([
        readThroughCache("k", loader),
        readThroughCache("k", loader),
        readThroughCache("k", loader),
      ]);

      expect(loader).toHaveBeenCalledTimes(1);
      expect([first, second, third]).toEqual(["value", "value", "value"]);
    });

    it("serves a settled value from cache within the TTL", async () => {
      const loader = vi.fn(async () => "value");

      await readThroughCache("k", loader, { ttlMs: 1000 });
      const second = await readThroughCache("k", loader, { ttlMs: 1000 });

      expect(second).toBe("value");
      expect(loader).toHaveBeenCalledTimes(1);
    });

    it("reloads once the TTL has passed", async () => {
      let now = 1_000;
      const nowSpy = vi.spyOn(Date, "now").mockImplementation(() => now);
      const loader = vi.fn(async () => "value");

      try {
        await readThroughCache("k", loader, { ttlMs: 100 });
        expect(loader).toHaveBeenCalledTimes(1);

        // Exactly at the boundary the entry is no longer fresh.
        now += 101;
        await readThroughCache("k", loader, { ttlMs: 100 });

        expect(loader).toHaveBeenCalledTimes(2);
      } finally {
        nowSpy.mockRestore();
      }
    });

    it("does not serve a value at the exact expiry instant", async () => {
      let now = 5_000;
      const nowSpy = vi.spyOn(Date, "now").mockImplementation(() => now);
      const loader = vi.fn(async () => "value");

      try {
        await readThroughCache("k", loader, { ttlMs: 100 });
        now += 100;
        await readThroughCache("k", loader, { ttlMs: 100 });
        expect(loader).toHaveBeenCalledTimes(2);
      } finally {
        nowSpy.mockRestore();
      }
    });

    it("bypasses a settled value but still joins an in-flight request", async () => {
      const loader = vi.fn(async () => "value");

      await readThroughCache("k", loader, { ttlMs: 10_000 });
      await readThroughCache("k", loader, { ttlMs: 10_000, bypassCache: true });
      expect(loader).toHaveBeenCalledTimes(2);

      // Now with one request in flight, a bypassing caller must join it rather
      // than open a second request.
      let release: (value: string) => void = () => {};
      const slowLoader = vi.fn(
        () => new Promise<string>((resolve) => {
          release = resolve;
        }),
      );
      const pendingRead = readThroughCache("slow", slowLoader, { ttlMs: 10_000 });
      const bypassingRead = readThroughCache("slow", slowLoader, {
        ttlMs: 10_000,
        bypassCache: true,
      });
      release("done");

      expect(await Promise.all([pendingRead, bypassingRead])).toEqual(["done", "done"]);
      expect(slowLoader).toHaveBeenCalledTimes(1);
    });

    it("never caches a rejection, so the next read retries", async () => {
      const failing = vi.fn(async () => {
        throw new Error("network");
      });

      await expect(readThroughCache("k", failing)).rejects.toThrow("network");
      expect(isCacheFresh("k")).toBe(false);

      const succeeding = vi.fn(async () => "recovered");
      await expect(readThroughCache("k", succeeding)).resolves.toBe("recovered");
      expect(succeeding).toHaveBeenCalledTimes(1);
    });

    it("propagates a rejection to every caller that joined the request", async () => {
      const failing = vi.fn(async () => {
        throw new Error("boom");
      });

      const results = await Promise.allSettled([
        readThroughCache("k", failing),
        readThroughCache("k", failing),
      ]);

      expect(failing).toHaveBeenCalledTimes(1);
      expect(results.map((entry) => entry.status)).toEqual(["rejected", "rejected"]);
    });

    it("keeps different keys independent", async () => {
      const loader = vi.fn(async (key: string) => `value:${key}`);

      await readThroughCache("a", () => loader("a"));
      const b = await readThroughCache("b", () => loader("b"));

      expect(b).toBe("value:b");
      expect(loader).toHaveBeenCalledTimes(2);
    });
  });

  describe("isCacheFresh", () => {
    it("is false while a request is in flight and true once it settles", async () => {
      let release: (value: string) => void = () => {};
      const loader = () => new Promise<string>((resolve) => {
        release = resolve;
      });

      const pending = readThroughCache("k", loader);
      expect(isCacheFresh("k")).toBe(false);

      release("value");
      await pending;
      expect(isCacheFresh("k")).toBe(true);
    });

    it("is false for an unknown key", () => {
      expect(isCacheFresh("never-read")).toBe(false);
    });
  });

  describe("invalidateCache", () => {
    it("drops the namespace and its children but leaves other namespaces", async () => {
      await readThroughCache(cacheKeys.cycles("alice"), async () => "alice-cycles");
      await readThroughCache(cacheKeys.admin("alice"), async () => "alice-admin");
      await readThroughCache(cacheKeys.cycles("bob"), async () => "bob-cycles");

      invalidateCache(cacheKeys.cycles("alice"));

      expect(isCacheFresh(cacheKeys.cycles("alice"))).toBe(false);
      expect(isCacheFresh(cacheKeys.cycles("bob"))).toBe(true);
      expect(isCacheFresh(cacheKeys.admin("alice"))).toBe(true);
    });

    it("drops every user in a namespace when given the namespace prefix", async () => {
      await readThroughCache(cacheKeys.cycles("alice"), async () => "a");
      await readThroughCache(cacheKeys.cycles("bob"), async () => "b");
      await readThroughCache(cacheKeys.admin("alice"), async () => "c");

      invalidateCache("cycles");

      expect(isCacheFresh(cacheKeys.cycles("alice"))).toBe(false);
      expect(isCacheFresh(cacheKeys.cycles("bob"))).toBe(false);
      expect(isCacheFresh(cacheKeys.admin("alice"))).toBe(true);
    });
  });

  describe("clearResourceCache", () => {
    it("drops every entry so the next identity cannot read the previous one", async () => {
      await readThroughCache(cacheKeys.cycles("alice"), async () => "alice-cycles");
      await readThroughCache(cacheKeys.admin("alice"), async () => "alice-admin");

      clearResourceCache();

      expect(isCacheFresh(cacheKeys.cycles("alice"))).toBe(false);
      expect(isCacheFresh(cacheKeys.admin("alice"))).toBe(false);
    });
  });

  describe("writeThroughCache", () => {
    it("publishes a resolved value so other readers reuse it", async () => {
      writeThroughCache("k", "fresh", 10_000);
      await flush();

      const loader = vi.fn(async () => "stale");
      expect(await readThroughCache("k", loader, { ttlMs: 10_000 })).toBe("fresh");
      expect(loader).not.toHaveBeenCalled();
    });

    it("publishes an in-flight request so a concurrent reader joins it", async () => {
      let release: (value: string) => void = () => {};
      const seeded = new Promise<string>((resolve) => {
        release = resolve;
      });
      writeThroughCache("k", seeded, 10_000);

      const loader = vi.fn(async () => "other");
      const read = readThroughCache("k", loader, { ttlMs: 10_000 });
      release("seeded");

      expect(await read).toBe("seeded");
      expect(loader).not.toHaveBeenCalled();
    });

    it("does not cache a rejected seeded request", async () => {
      writeThroughCache("k", Promise.reject(new Error("seed failed")), 10_000);
      await flush();

      expect(isCacheFresh("k")).toBe(false);
    });
  });

  describe("cacheKeys", () => {
    it("namespaces by resource and identity so users cannot collide", () => {
      expect(cacheKeys.cycles("alice")).toBe("cycles:alice");
      expect(cacheKeys.admin("alice")).toBe("admin:alice");
      expect(cacheKeys.cycles("alice")).not.toBe(cacheKeys.admin("alice"));
      expect(cacheKeys.cycles("alice")).not.toBe(cacheKeys.cycles("bob"));
    });
  });
});
