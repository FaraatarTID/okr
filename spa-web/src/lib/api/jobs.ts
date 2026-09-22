import { backendJsonRequest } from "@/lib/api/http";
import type { BackendJobView, BackendRequestBody } from "@/lib/api/backend-schema";

/**
 * Job view backed by the generated OpenAPI schema (components["schemas"]
 * ["JobView"]). Regenerate via `npm run gen:api` after backend schema changes.
 */
export type AsyncJobView = BackendJobView;

type JobSubmitRequest = BackendRequestBody<"api_submit_job_v1_jobs_post">;

export async function submitBackendJob(input: {
  actor_username: string;
  kind: "pdf.weekly" | "ai.generate_json";
  payload: Record<string, unknown>;
  max_attempts?: number;
}): Promise<AsyncJobView> {
  const body: JobSubmitRequest = {
    actor_username: input.actor_username,
    kind: input.kind,
    payload: input.payload,
    max_attempts: input.max_attempts ?? 2,
  };
  return backendJsonRequest({
    operation: "api_submit_job_v1_jobs_post",
    path: "/v1/jobs",
    actor: input.actor_username,
    body,
    label: "Job submit",
  });
}

export async function readBackendJob(input: {
  actor_username: string;
  job_id: string;
}): Promise<AsyncJobView> {
  return backendJsonRequest({
    operation: "api_get_job_v1_jobs__job_id__get",
    path: `/v1/jobs/${encodeURIComponent(input.job_id)}`,
    actor: input.actor_username,
    cache: "no-store",
    label: "Job read",
  });
}
