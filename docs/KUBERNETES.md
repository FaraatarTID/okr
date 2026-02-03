Kubernetes deployment

Prerequisites
- NGINX Ingress Controller and cert-manager installed
- TLS issuer available (ClusterIssuer or Issuer)

Manifests
- Namespace: create okr (kubectl create namespace okr)
- Secret: [deploy/k8s/secret-db.yaml](deploy/k8s/secret-db.yaml) with OKR_DATABASE_URL
- Deployment: [deploy/k8s/deployment.yaml](deploy/k8s/deployment.yaml)
  - Reads OKR_DATABASE_URL from Secret
  - Non-root securityContext
  - Probes on /
- Service: [deploy/k8s/service.yaml](deploy/k8s/service.yaml)
- Ingress: [deploy/k8s/ingress.yaml](deploy/k8s/ingress.yaml)
  - Set host and TLS secret

Subpath hosting
- Use a path-based rule and set BASE_URL_PATH in the Deployment env
- Ensure ingress annotations handle path rewrites for websockets

Scaling
- Keep replicas=1 with SQLite; with Postgres you can scale reads but Streamlit is stateful per-user via session
- Prefer horizontal scale by adding more pods and sticky sessions at the ingress

Rollouts
- Use image tags and rolling updates
- Observe readiness/liveness before full rollout

Monitoring & logs
- Use kubectl logs for pod logs; ingress logs for HTTP
- Health check: GET /

Backups
- Rely on managed Postgres backups
- If using PVC (SQLite fallback), snapshot the PVC
