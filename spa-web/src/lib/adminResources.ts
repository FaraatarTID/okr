import { readBackendQuery, type ReadQueryTeam, type ReadQueryUser } from "@/lib/api";
import { cacheKeys, readThroughCache } from "@/lib/resourceCache";

export type AdminResourcePair = {
  users: ReadQueryUser[];
  teams: ReadQueryTeam[];
};

/**
 * Read and cache the admin `users.all` + `teams.all` pair.
 *
 * Both requests are issued in parallel, and a failure of either fails the whole
 * read, which matches the existing behaviour of the admin panel load. Call
 * `invalidateAdminResources(username)` from any mutation that changes users or
 * teams.
 */
export function readAdminResourcePair(
  username: string,
  options: { bypassCache?: boolean; ttlMs?: number } = {},
): Promise<AdminResourcePair> {
  return readThroughCache(
    cacheKeys.admin(username),
    async () => {
      const [usersPayload, teamsPayload] = await Promise.all([
        readBackendQuery({ actor_username: username, kind: "users.all" }),
        readBackendQuery({ actor_username: username, kind: "teams.all" }),
      ]);
      return {
        users: (usersPayload.users || []) as ReadQueryUser[],
        teams: (teamsPayload.teams || []) as ReadQueryTeam[],
      };
    },
    options,
  );
}

/**
 * Sort the pair the way the admin panel renders it: users by username and teams
 * by name, both ascending.
 */
export function mergeAdminResourcePair({
  users,
  teams,
}: AdminResourcePair): AdminResourcePair {
  return {
    users: [...users].sort((a, b) =>
      String(a.username || "").localeCompare(String(b.username || "")),
    ),
    teams: [...teams].sort((a, b) =>
      String(a.name || "").localeCompare(String(b.name || "")),
    ),
  };
}

/** Read the sorted admin pair the panel renders, through the shared cache. */
export function readSortedAdminResources(
  username: string,
  options: { bypassCache?: boolean; ttlMs?: number } = {},
): Promise<AdminResourcePair> {
  return readAdminResourcePair(username, options).then(mergeAdminResourcePair);
}
