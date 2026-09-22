/**
 * Typed access to backend OpenAPI schema types.
 *
 * Generated from `src/lib/api/openapi.json` (exported by
 * `scripts/export_openapi.py`). Regenerate with `npm run gen:api`.
 * CI fails when the committed artifact drifts from the live schema.
 */
import type { components, operations, paths } from "./generated/schema";

export type BackendSchemas = components["schemas"];
export type BackendOperations = operations;
export type BackendPaths = paths;
export type BackendOperationId = keyof BackendOperations;

type JsonContent<T> = T extends { content: { "application/json": infer Value } }
  ? Value
  : never;

type BinaryContent<T> = T extends { content: infer Content }
  ? Content extends Record<string, unknown>
    ? {
        [MediaType in keyof Content]: MediaType extends "application/json" ? never : Content[MediaType];
      }[keyof Content]
    : never
  : never;

type JsonResponseForStatus<Responses, Status extends number> = Status extends number
  ? Responses extends Record<Status, infer Response>
    ? JsonContent<Response>
    : never
  : never;

type BinaryResponseForStatus<Responses, Status extends number> = Status extends number
  ? Responses extends Record<Status, infer Response>
    ? BinaryContent<Response>
    : never
  : never;

/** Generated JSON request payload for a documented backend operation. */
export type BackendRequestBody<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { requestBody: infer Body }
    ? JsonContent<Body>
    : never;

/** Whether OpenAPI requires the JSON request body for an operation. */
export type BackendRequestBodyRequired<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { requestBody: unknown } ? true : false;

/** Generated successful JSON response for a documented backend operation. */
export type BackendSuccessResponse<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { responses: infer Responses }
    ? JsonResponseForStatus<Responses, 200 | 201 | 202 | 203 | 204 | 205 | 206 | 207 | 208 | 226>
    : never;

/** Generated successful non-JSON response for a documented backend operation. */
export type BackendBinarySuccess<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { responses: infer Responses }
    ? BinaryResponseForStatus<Responses, 200 | 201 | 202 | 203 | 206 | 207 | 208 | 226>
    : never;

/** `void` for an operation whose documented successful response has no body. */
export type BackendNoContentSuccess<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { responses: infer Responses }
    ? Responses extends { 204: unknown } | { 205: unknown }
      ? void
      : never
    : never;

/** Generated path parameters for a documented backend operation. */
export type BackendPathParameters<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { parameters: { path?: infer Parameters } }
    ? Parameters
    : never;

/** Generated query parameters for a documented backend operation. */
export type BackendQueryParameters<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { parameters: { query?: infer Parameters } }
    ? Parameters
    : never;

/** Generated documented validation response for a backend operation. */
export type BackendValidationError<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { responses: infer Responses }
    ? JsonContent<Responses extends { 422: infer Response } ? Response : never>
    : never;

/** Union of generated, documented non-success JSON responses for an operation. */
export type BackendErrorResponse<Operation extends BackendOperationId> =
  BackendOperations[Operation] extends { responses: infer Responses }
    ? JsonResponseForStatus<Responses, 400 | 401 | 403 | 404 | 409 | 413 | 422 | 429 | 500 | 503>
    : never;

/** Request contract for the typed Atlas snapshot endpoint. */
export type AtlasSnapshotRequest = BackendSchemas["AtlasSnapshotRequest"];

/** Request contract for the discriminator-based read query endpoint. */
export type ReadQueryRequest = BackendSchemas["ReadQueryRequest"];

/** Typed common response sections for the discriminator-based read endpoint. */
export type ReadQueryResponse = BackendSchemas["ReadQueryResponse"];

export type ReadQueryKeyResult = BackendSchemas["ReadQueryKeyResultView"];
export type ReadQueryWeeklyPlan = BackendSchemas["ReadQueryWeeklyPlanView"];
export type ReadQueryWorkLog = BackendSchemas["ReadQueryWorkLogView"];
export type ReadQueryRetro = BackendSchemas["ReadQueryRetroView"];
export type ReadQueryExperiment = BackendSchemas["ReadQueryExperimentView"];
export type ReadQueryTask = BackendSchemas["ReadQueryTaskView"];
export type ReadQueryUser = BackendSchemas["ReadQueryUserView"];
export type ReadQueryTeam = BackendSchemas["ReadQueryTeamView"];
export type ReadQueryCycle = BackendSchemas["ReadQueryCycleView"];

/** Serialized async job returned by /v1/jobs endpoints. */
export type BackendJobView = BackendSchemas["JobView"];

/** Healthz payload including data-access mode and dead-job count. */
export type BackendHealthz = {
  status?: string;
  data_access_mode?: string;
  configured_mode?: string;
  dead_jobs?: number | null;
};

/**
 * Parse a healthz response body into a typed shape.
 * Unknown shapes return null so callers can fail closed.
 */
export function parseHealthz(body: unknown): BackendHealthz | null {
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const record = body as Record<string, unknown>;
  const deadJobsRaw = record.dead_jobs;
  return {
    status: typeof record.status === "string" ? record.status : undefined,
    data_access_mode:
      typeof record.data_access_mode === "string"
        ? record.data_access_mode
        : undefined,
    configured_mode:
      typeof record.configured_mode === "string"
        ? record.configured_mode
        : undefined,
    dead_jobs:
      typeof deadJobsRaw === "number"
        ? deadJobsRaw
        : deadJobsRaw === null
          ? null
          : undefined,
  };
}
