import type { components, paths } from "./generated/backend-schema.js";

export type BackendAuthUser = components["schemas"]["AuthUserView"];
export type BackendLoginResponse = components["schemas"]["AuthLoginResponse"];
export type BackendSessionResponse = components["schemas"]["AuthSessionResponse"];

export type BackendLoginSuccess =
  paths["/v1/auth/login"]["post"]["responses"][200]["content"]["application/json"];
export type BackendSessionSuccess =
  paths["/v1/auth/me"]["get"]["responses"][200]["content"]["application/json"];
