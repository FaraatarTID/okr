import policy from "./route-policy.json" with { type: "json" };

export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface AllowlistRule {
  pathTemplate: string;
  methods: readonly HttpMethod[];
  pathRegex: RegExp;
}

export const ALLOWLIST_POLICY_ROUTES: readonly AllowlistRule[] = policy.routes.map((route) => ({
  pathTemplate: route.pathTemplate,
  methods: route.methods as HttpMethod[],
  pathRegex: new RegExp(route.pathPattern),
}));

const ACTOR_OPTIONAL_POLICY_ROUTES: readonly AllowlistRule[] = ALLOWLIST_POLICY_ROUTES.filter((rule) =>
  policy.routes.find((route) => route.pathTemplate === rule.pathTemplate)?.actorRequired === false,
);

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
