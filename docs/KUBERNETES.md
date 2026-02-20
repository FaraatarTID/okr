Documentation HQ: [README](../README.md)

Kubernetes deployment

Prerequisites

- NGINX Ingress Controller and cert-manager installed
- TLS issuer available (ClusterIssuer or Issuer)

Manifests

- Namespace: create okr (kubectl create namespace okr)
- Secret: [deploy/k8s/secret-db.yaml](../deploy/k8s/secret-db.yaml) with OKR_DATABASE_URL
- Deployment: [deploy/k8s/deployment.yaml](../deploy/k8s/deployment.yaml)
  - Reads OKR_DATABASE_URL from Secret
  - Non-root securityContext
  - Probes on /
- Service: [deploy/k8s/service.yaml](../deploy/k8s/service.yaml)
- Ingress: [deploy/k8s/ingress.yaml](../deploy/k8s/ingress.yaml)
  - Set host and TLS secret

Current scope of provided manifests (important)

- The checked-in Kubernetes manifests currently deploy the Streamlit app service (`okr-streamlit`) only.
- For full backend-assisted architecture parity with Docker Compose, add internal services for:
  - `backend-api` (FastAPI)
  - `backend-worker` (job processor)
- Streamlit should then use `OKR_BACKEND_API_URL` pointing to the cluster-internal backend API Service.
- Set `OKR_BACKEND_PROXY_MUTATIONS=true` on the `okr` Deployment to route node writes through backend API.
- Keep backend API Service internal (`ClusterIP`) and avoid public ingress exposure.

Recommended backend K8s additions

- Deployment + Service for `backend-api`.
- Deployment for `backend-worker`.
- Shared environment/Secret values across app + backend:
  - `OKR_DATABASE_URL`
  - `OKR_BACKEND_SERVICE_TOKEN`
  - `OKR_BACKEND_SIGNING_SECRET`
  - `OKR_BACKEND_PROXY_MUTATIONS=true` (on `okr` workload)
  - `OKR_ALLOW_LOCAL_BACKEND_FALLBACK=false` (recommended production default)
  - `PDF_METHOD=pdfshift`, `PDFSHIFT_API_KEY`
  - AI policy/provider values (`ALLOW_EXTERNAL_AI`, `AI_PROVIDER`, provider credentials)
- Optional HorizontalPodAutoscaler for app and backend API after baseline load testing.

Subpath hosting

- Use a path-based rule and set BASE_URL_PATH in the Deployment env
- Ensure ingress annotations handle path rewrites for websockets

Scaling

- Streamlit is stateful per-user via session; use sticky sessions at ingress when scaling
- Prefer horizontal scale by adding more pods and sticky sessions at the ingress

Rollouts

- Use image tags and rolling updates
- Observe readiness/liveness before full rollout

Monitoring & logs

- Use kubectl logs for pod logs; ingress logs for HTTP
- Health check: GET /
- Backend health (when deployed): GET /healthz on backend-api Service

Backups

- Rely on Supabase PostgreSQL backups/snapshots
