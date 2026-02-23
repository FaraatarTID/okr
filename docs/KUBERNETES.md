Documentation HQ: [README](../README.md)

Kubernetes deployment

Prerequisites

- NGINX Ingress Controller and cert-manager installed
- TLS issuer available (ClusterIssuer or Issuer)

Manifests

- Namespace: create okr (kubectl create namespace okr)
- Secret: [deploy/k8s/secret-db.yaml](../deploy/k8s/secret-db.yaml) with OKR_DATABASE_URL
- Backend auth secret: [deploy/k8s/secret-backend-auth.yaml](../deploy/k8s/secret-backend-auth.yaml)
- Streamlit Deployment: [deploy/k8s/deployment.yaml](../deploy/k8s/deployment.yaml)
- Streamlit Service: [deploy/k8s/service.yaml](../deploy/k8s/service.yaml)
- Backend API Deployment: [deploy/k8s/deployment-backend-api.yaml](../deploy/k8s/deployment-backend-api.yaml)
- Backend API Service: [deploy/k8s/service-backend-api.yaml](../deploy/k8s/service-backend-api.yaml)
- Backend Worker Deployment: [deploy/k8s/deployment-backend-worker.yaml](../deploy/k8s/deployment-backend-worker.yaml)
- Ingress: [deploy/k8s/ingress.yaml](../deploy/k8s/ingress.yaml)
  - Set host and TLS secret

Current scope of provided manifests (important)

- The checked-in manifests now include Streamlit + backend API + backend worker.
- Streamlit uses cluster-internal backend API Service via `OKR_BACKEND_API_URL=http://okr-backend-api:8100`.
- `OKR_BACKEND_PROXY_MUTATIONS=true` is enabled on Streamlit deployment.
- Keep backend API Service internal (`ClusterIP`) and avoid public ingress exposure.
- Shared environment/Secret values across app + backend:
  - `OKR_DATABASE_URL`
  - `OKR_BACKEND_SERVICE_TOKEN`
  - `OKR_BACKEND_SIGNING_SECRET`
  - `OKR_BACKEND_PROXY_MUTATIONS=true` (on `okr` workload)
  - `OKR_BACKEND_PROXY_READS=true` (optional; routes selected read-heavy paths via backend API)
  - `OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false` and `OKR_ALLOW_LOCAL_READ_FALLBACK=false` (recommended production default)
  - PDF renderer:
    - `PDF_METHOD=pdfshift` + `PDFSHIFT_API_KEY`, or
    - `PDF_METHOD=chromium` (+ Playwright/Chromium runtime)
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
