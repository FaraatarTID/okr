import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ReadQueryTeam, ReadQueryUser } from "@/lib/api";
import {
  mergeAdminResourcePair,
  readAdminResourcePair,
  readSortedAdminResources,
} from "@/lib/adminResources";
import { clearResourceCache } from "@/lib/resourceCache";

/**
 * `adminResources.ts` is production code that had no test of its own: the admin
 * hook tests mock this module, so nothing exercised it directly. It is covered
 * here at the network boundary — only `fetch` is mocked, so the real api layer,
 * retry machinery and cache all run — plus direct tests of the pure merge.
 */
function installFetchSpy() {
  const kinds: string[] = [];
  const fetchMock = vi.fn(async (_url: string, init: { body?: string }) => {
    const body = JSON.parse(String(init?.body ?? "{}")) as { kind?: string };
    const kind = String(body.kind ?? "");
    kinds.push(kind);
    const payload =
      kind === "teams.all"
        ? { teams: [{ id: 1, name: "Zeta" }, { id: 2, name: "Alpha" }] }
        : {
            users: [
              { id: 1, username: "zoe", display_name: "Zoe", role: "member" },
              { id: 2, username: "alice", display_name: "Alice", role: "admin" },
            ],
          };
    // A tick of latency so concurrent consumers genuinely overlap in flight.
    await new Promise((resolve) => setTimeout(resolve, 0));
    return { ok: true, status: 200, json: async () => payload } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, kinds };
}

describe("mergeAdminResourcePair", () => {
  it("sorts users by username and teams by name, ascending", () => {
    const merged = mergeAdminResourcePair({
      users: [
        { username: "zoe" },
        { username: "alice" },
      ] as never,
      teams: [{ name: "Zeta" }, { name: "Alpha" }] as never,
    });

    expect(merged.users.map((u) => u.username)).toEqual(["alice", "zoe"]);
    expect(merged.teams.map((t) => t.name)).toEqual(["Alpha", "Zeta"]);
  });

  it("does not mutate the arrays it was given", () => {
    const users = [{ username: "zoe" }, { username: "alice" }] as unknown as ReadQueryUser[];
    const teams = [{ name: "Zeta" }, { name: "Alpha" }] as unknown as ReadQueryTeam[];

    mergeAdminResourcePair({ users, teams });

    expect(users.map((u) => u.username)).toEqual(["zoe", "alice"]);
    expect(teams.map((t) => t.name)).toEqual(["Zeta", "Alpha"]);
  });

  it("tolerates missing username and name without throwing", () => {
    const merged = mergeAdminResourcePair({
      users: [{ username: undefined }, { username: "bob" }] as never,
      teams: [{ name: null }, { name: "Beta" }] as never,
    });

    expect(merged.users.map((u) => u.username)).toEqual([undefined, "bob"]);
    expect(merged.teams.map((t) => t.name)).toEqual([null, "Beta"]);
  });

  it("handles an empty pair", () => {
    expect(mergeAdminResourcePair({ users: [], teams: [] })).toEqual({ users: [], teams: [] });
  });
});

describe("readAdminResourcePair", () => {
  beforeEach(() => {
    clearResourceCache();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearResourceCache();
  });

  it("reads users.all and teams.all in one pair", async () => {
    const { fetchMock, kinds } = installFetchSpy();

    const pair = await readAdminResourcePair("admin-user");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect([...kinds].sort()).toEqual(["teams.all", "users.all"]);
    expect(pair.users).toHaveLength(2);
    expect(pair.teams).toHaveLength(2);
  });

  it("joins two concurrent consumers into one pair, not two", async () => {
    const { fetchMock } = installFetchSpy();

    await Promise.all([
      readAdminResourcePair("admin-concurrent"),
      readSortedAdminResources("admin-concurrent"),
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("serves a later consumer from the cache inside the TTL", async () => {
    const { fetchMock } = installFetchSpy();

    await readAdminResourcePair("admin-sequential");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await readAdminResourcePair("admin-sequential");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("bypasses the cache when the caller needs fresh data", async () => {
    const { fetchMock } = installFetchSpy();

    await readAdminResourcePair("admin-bypass");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await readAdminResourcePair("admin-bypass", { bypassCache: true });
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("keys by username, so two admins never share a pair", async () => {
    const { fetchMock } = installFetchSpy();

    await readAdminResourcePair("admin-a");
    await readAdminResourcePair("admin-b");

    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("propagates a failure and does not cache it", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("refused");
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(readAdminResourcePair("admin-fail")).rejects.toThrow();

    // A retry must reach the network again rather than replaying the failure.
    const { fetchMock: recovered } = installFetchSpy();
    const pair = await readAdminResourcePair("admin-fail");
    expect(pair.users).toHaveLength(2);
    expect(recovered).toHaveBeenCalledTimes(2);
  });

  it("returns the sorted pair from readSortedAdminResources", async () => {
    installFetchSpy();

    const pair = await readSortedAdminResources("admin-sorted");

    expect(pair.users.map((u) => u.username)).toEqual(["alice", "zoe"]);
    expect(pair.teams.map((t) => t.name)).toEqual(["Alpha", "Zeta"]);
  });

  it("degrades a missing collection to an empty array", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({}),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const pair = await readAdminResourcePair("admin-empty");

    expect(pair.users).toEqual([]);
    expect(pair.teams).toEqual([]);
  });
});
