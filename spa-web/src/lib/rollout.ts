export interface SpaRolloutConfig {
  enabled: boolean;
  allow_all: boolean;
  team_ids: number[];
  usernames: string[];
  roles: string[];
  allow_preview_bypass: boolean;
}

export interface RolloutSubject {
  username: string;
  role?: string | null;
  team_id?: number | null;
}

export interface RolloutDecision {
  allowed: boolean;
  reason:
    | "disabled"
    | "allow_all"
    | "username"
    | "role"
    | "team"
    | "preview_bypass"
    | "no_user"
    | "cohort_miss";
}

interface ParseInput {
  enabled?: string | boolean | null;
  allow_all?: string | boolean | null;
  team_ids?: string | null;
  usernames?: string | null;
  roles?: string | null;
  allow_preview_bypass?: string | boolean | null;
}

function parseBool(value: string | boolean | null | undefined, fallback = false): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (!normalized) {
    return fallback;
  }
  return ["1", "true", "yes", "on"].includes(normalized);
}

function parseCsv(value: string | null | undefined): string[] {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return [];
  }
  return Array.from(
    new Set(
      normalized
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean),
    ),
  );
}

function parseIntCsv(value: string | null | undefined): number[] {
  const output: number[] = [];
  for (const item of parseCsv(value)) {
    const parsed = Number.parseInt(item, 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      output.push(parsed);
    }
  }
  return Array.from(new Set(output)).sort((left, right) => left - right);
}

export function parseSpaRolloutConfig(input: ParseInput): SpaRolloutConfig {
  return {
    enabled: parseBool(input.enabled, false),
    allow_all: parseBool(input.allow_all, false),
    team_ids: parseIntCsv(input.team_ids),
    usernames: parseCsv(input.usernames),
    roles: parseCsv(input.roles),
    allow_preview_bypass: parseBool(input.allow_preview_bypass, false),
  };
}

export function evaluateSpaRollout(
  user: RolloutSubject | null,
  config: SpaRolloutConfig,
  options?: { previewBypass?: boolean },
): RolloutDecision {
  const previewBypass = Boolean(options?.previewBypass);

  if (!config.enabled) {
    return { allowed: false, reason: "disabled" };
  }

  if (previewBypass && config.allow_preview_bypass) {
    return { allowed: true, reason: "preview_bypass" };
  }

  if (!user) {
    return { allowed: false, reason: "no_user" };
  }

  const normalizedUsername = String(user.username || "").trim().toLowerCase();
  const normalizedRole = String(user.role || "").trim().toLowerCase();
  const normalizedTeamId = Number(user.team_id);

  if (config.allow_all) {
    return { allowed: true, reason: "allow_all" };
  }
  if (normalizedUsername && config.usernames.includes(normalizedUsername)) {
    return { allowed: true, reason: "username" };
  }
  if (normalizedRole && config.roles.includes(normalizedRole)) {
    return { allowed: true, reason: "role" };
  }
  if (Number.isFinite(normalizedTeamId) && config.team_ids.includes(Math.trunc(normalizedTeamId))) {
    return { allowed: true, reason: "team" };
  }
  return { allowed: false, reason: "cohort_miss" };
}

export function rolloutReasonMessage(reason: RolloutDecision["reason"]): string {
  if (reason === "disabled") {
    return "SPA rollout is disabled for this environment.";
  }
  if (reason === "cohort_miss") {
    return "Your account is outside the current SPA pilot cohort.";
  }
  if (reason === "no_user") {
    return "Login is required before rollout policy evaluation.";
  }
  if (reason === "preview_bypass") {
    return "Temporary preview bypass is active.";
  }
  if (reason === "allow_all") {
    return "SPA rollout is enabled for all cohorts in this environment.";
  }
  if (reason === "username") {
    return "SPA rollout is enabled for this username cohort.";
  }
  if (reason === "role") {
    return "SPA rollout is enabled for this role cohort.";
  }
  return "SPA rollout is enabled for this team cohort.";
}
