export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface AllowlistRule {
  pathTemplate: string;
  methods: readonly HttpMethod[];
  pathRegex: RegExp;
}

export const ALLOWLIST_POLICY_ROUTES: readonly AllowlistRule[] = [
  { pathTemplate: "/v1/auth/login", methods: ["POST"], pathRegex: /^\/v1\/auth\/login$/ },
  { pathTemplate: "/v1/auth/me", methods: ["GET"], pathRegex: /^\/v1\/auth\/me$/ },
  { pathTemplate: "/v1/read/query", methods: ["POST"], pathRegex: /^\/v1\/read\/query$/ },
  {
    pathTemplate: "/v1/read/atlas/snapshot",
    methods: ["POST"],
    pathRegex: /^\/v1\/read\/atlas\/snapshot$/,
  },
  {
    pathTemplate: "/v1/read/leadership/metrics",
    methods: ["POST"],
    pathRegex: /^\/v1\/read\/leadership\/metrics$/,
  },
  {
    pathTemplate: "/v1/admin/ai-health",
    methods: ["GET"],
    pathRegex: /^\/v1\/admin\/ai-health$/,
  },
  {
    pathTemplate: "/v1/admin/pdf-health",
    methods: ["GET"],
    pathRegex: /^\/v1\/admin\/pdf-health$/,
  },
  {
    pathTemplate: "/v1/admin/db-backup",
    methods: ["GET"],
    pathRegex: /^\/v1\/admin\/db-backup$/,
  },
  {
    pathTemplate: "/v1/admin/db-restore",
    methods: ["POST"],
    pathRegex: /^\/v1\/admin\/db-restore$/,
  },
  {
    pathTemplate: "/v1/ai/analyze-node",
    methods: ["POST"],
    pathRegex: /^\/v1\/ai\/analyze-node$/,
  },
  {
    pathTemplate: "/v1/ai/team-coach",
    methods: ["POST"],
    pathRegex: /^\/v1\/ai\/team-coach$/,
  },
  {
    pathTemplate: "/v1/ai/strategy-pulse",
    methods: ["POST"],
    pathRegex: /^\/v1\/ai\/strategy-pulse$/,
  },
  { pathTemplate: "/v1/timer/start", methods: ["POST"], pathRegex: /^\/v1\/timer\/start$/ },
  { pathTemplate: "/v1/timer/stop", methods: ["POST"], pathRegex: /^\/v1\/timer\/stop$/ },
  { pathTemplate: "/v1/jobs", methods: ["POST"], pathRegex: /^\/v1\/jobs$/ },
  {
    pathTemplate: "/v1/jobs/{job_id}",
    methods: ["GET", "DELETE"],
    pathRegex: /^\/v1\/jobs\/[^/]+$/,
  },
  {
    pathTemplate: "/v1/jobs/{job_id}/cancel",
    methods: ["POST"],
    pathRegex: /^\/v1\/jobs\/[^/]+\/cancel$/,
  },
  {
    pathTemplate: "/v1/nodes/{create_type}",
    methods: ["POST"],
    pathRegex: /^\/v1\/nodes\/(goal|objective|key_result|task)$/,
  },
  {
    pathTemplate: "/v1/nodes/{node_type}/{node_id:int}",
    methods: ["PATCH", "DELETE"],
    pathRegex: /^\/v1\/nodes\/[a-zA-Z_]+\/\d+$/,
  },
  { pathTemplate: "/v1/users", methods: ["POST"], pathRegex: /^\/v1\/users$/ },
  {
    pathTemplate: "/v1/users/{user_id:int}",
    methods: ["PATCH"],
    pathRegex: /^\/v1\/users\/\d+$/,
  },
  {
    pathTemplate: "/v1/users/{user_id:int}/reset-password",
    methods: ["POST"],
    pathRegex: /^\/v1\/users\/\d+\/reset-password$/,
  },
  { pathTemplate: "/v1/cycles", methods: ["POST"], pathRegex: /^\/v1\/cycles$/ },
  {
    pathTemplate: "/v1/cycles/{cycle_id:int}",
    methods: ["PATCH", "DELETE"],
    pathRegex: /^\/v1\/cycles\/\d+$/,
  },
  { pathTemplate: "/v1/teams", methods: ["POST"], pathRegex: /^\/v1\/teams$/ },
  {
    pathTemplate: "/v1/teams/{team_id:int}",
    methods: ["PATCH", "DELETE"],
    pathRegex: /^\/v1\/teams\/\d+$/,
  },
  { pathTemplate: "/v1/check-ins", methods: ["POST"], pathRegex: /^\/v1\/check-ins$/ },
  {
    pathTemplate: "/v1/experiments",
    methods: ["POST"],
    pathRegex: /^\/v1\/experiments$/,
  },
  {
    pathTemplate: "/v1/experiments/{experiment_id:int}",
    methods: ["PATCH"],
    pathRegex: /^\/v1\/experiments\/\d+$/,
  },
  {
    pathTemplate: "/v1/experiments/{experiment_id:int}/close",
    methods: ["POST"],
    pathRegex: /^\/v1\/experiments\/\d+\/close$/,
  },
  {
    pathTemplate: "/v1/retrospectives",
    methods: ["POST"],
    pathRegex: /^\/v1\/retrospectives$/,
  },
  {
    pathTemplate: "/v1/retrospectives/{retrospective_id:int}/experiment-outcomes",
    methods: ["PUT"],
    pathRegex: /^\/v1\/retrospectives\/\d+\/experiment-outcomes$/,
  },
  {
    pathTemplate: "/v1/weekly-plans",
    methods: ["POST"],
    pathRegex: /^\/v1\/weekly-plans$/,
  },
  {
    pathTemplate: "/v1/alignments",
    methods: ["POST"],
    pathRegex: /^\/v1\/alignments$/,
  },
  {
    pathTemplate: "/v1/alignments/{edge_id:int}",
    methods: ["DELETE"],
    pathRegex: /^\/v1\/alignments\/\d+$/,
  },
  {
    pathTemplate: "/v1/objective-alignment-links",
    methods: ["POST"],
    pathRegex: /^\/v1\/objective-alignment-links$/,
  },
  {
    pathTemplate: "/v1/objective-alignment-links/{link_id:int}",
    methods: ["DELETE"],
    pathRegex: /^\/v1\/objective-alignment-links\/\d+$/,
  },
  {
    pathTemplate: "/v1/work-logs/{work_log_id:int}",
    methods: ["DELETE"],
    pathRegex: /^\/v1\/work-logs\/\d+$/,
  },
  {
    pathTemplate: "/v1/state/{key}",
    methods: ["GET"],
    pathRegex: /^\/v1\/state\/[^/]+$/,
  },
  {
    pathTemplate: "/v1/state/{key}",
    methods: ["POST"],
    pathRegex: /^\/v1\/state\/[^/]+$/,
  },
];

const ACTOR_OPTIONAL_POLICY_ROUTES: readonly AllowlistRule[] = [
  { pathTemplate: "/v1/auth/login", methods: ["POST"], pathRegex: /^\/v1\/auth\/login$/ },
];

function normalizeMethod(method: string): HttpMethod | null {
  const normalized = String(method || "").trim().toUpperCase();
  if (normalized === "GET" || normalized === "POST" || normalized === "PATCH" || normalized === "PUT" || normalized === "DELETE") {
    return normalized;
  }
  return null;
}

export function normalizeBackendPath(rawWildcardPath: string): string | null {
  const wildcard = String(rawWildcardPath || "").trim();
  const normalized = `/${wildcard.replace(/^\/+/, "")}`;
  if (!normalized.startsWith("/v1/")) {
    return null;
  }
  if (normalized.includes("..")) {
    return null;
  }
  if (!/^\/[a-zA-Z0-9/_-]+$/.test(normalized)) {
    return null;
  }
  return normalized;
}

export function isAllowlistedRoute(method: string, backendPath: string): boolean {
  const normalizedMethod = normalizeMethod(method);
  if (!normalizedMethod) {
    return false;
  }
  return ALLOWLIST_POLICY_ROUTES.some((rule) => {
    if (!rule.methods.includes(normalizedMethod)) {
      return false;
    }
    return rule.pathRegex.test(backendPath);
  });
}

export function policySignatures(): string[] {
  return ALLOWLIST_POLICY_ROUTES.flatMap((rule) =>
    rule.methods.map((method) => `${method} ${rule.pathTemplate}`),
  ).sort();
}

export function requiresActorHeader(method: string, backendPath: string): boolean {
  const normalizedMethod = normalizeMethod(method);
  if (!normalizedMethod) {
    return false;
  }
  return !ACTOR_OPTIONAL_POLICY_ROUTES.some((rule) => {
    if (!rule.methods.includes(normalizedMethod)) {
      return false;
    }
    return rule.pathRegex.test(backendPath);
  });
}
