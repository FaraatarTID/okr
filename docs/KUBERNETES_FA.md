# استقرار Kubernetes
Documentation HQ: [README](../README.md)

پیش‌نیازها
- NGINX Ingress Controller و cert-manager نصب باشند
- TLS issuer (ClusterIssuer/Issuer) آماده باشد

مانیفست‌ها
- Namespace: ایجاد `okr` (با `kubectl create namespace okr`)
- Secret DB: `deploy/k8s/secret-db.yaml` شامل `OKR_DATABASE_URL`
- Deployment: `deploy/k8s/deployment.yaml`
  - خواندن `OKR_DATABASE_URL` از Secret
  - `securityContext` غیر root
  - probe روی `/`
- Service: `deploy/k8s/service.yaml`
- Ingress: `deploy/k8s/ingress.yaml`
  - host و TLS secret را تنظیم کنید

دامنه فعلی مانیفست‌های موجود (مهم)
- مانیفست‌های فعلی در مخزن فقط سرویس Streamlit (`okr-streamlit`) را deploy می‌کنند.
- برای هم‌ترازی با معماری backend-assisted، این سرویس‌ها را اضافه کنید:
  - `backend-api`
  - `backend-worker`
- سپس `OKR_BACKEND_API_URL` باید به سرویس داخلی backend اشاره کند.
- در workload مربوط به `okr`، مقدار `OKR_BACKEND_PROXY_MUTATIONS=true` بگذارید.
- backend API را `ClusterIP` نگه دارید و ingress عمومی برای آن نسازید.

افزونه‌های پیشنهادی K8s
- Deployment + Service برای `backend-api`
- Deployment برای `backend-worker`
- اشتراک env/secret بین app و backend:
  - `OKR_DATABASE_URL`
  - `OKR_BACKEND_SERVICE_TOKEN`
  - `OKR_BACKEND_SIGNING_SECRET`
  - `OKR_BACKEND_PROXY_MUTATIONS=true`
  - `OKR_ALLOW_LOCAL_BACKEND_FALLBACK=false`
  - `PDF_METHOD=pdfshift`, `PDFSHIFT_API_KEY`
  - مقادیر AI (`ALLOW_EXTERNAL_AI`, `AI_PROVIDER`, credentialها)
- بعد از baseline load test، HPA برای app/backend API

میزبانی زیر‌مسیر
- rule مسیرمحور در ingress
- مقدار `BASE_URL_PATH` در env deployment
- rewrite مناسب مسیر برای websocket

مقیاس‌پذیری
- Streamlit session-state دارد؛ در scale از sticky session استفاده کنید.
- scale افقی با pod بیشتر + sticky session در ingress

Rollout
- از image tag مشخص و rolling update استفاده کنید.
- پیش از rollout کامل، readiness/liveness را پایش کنید.

لاگ و پایش
- لاگ podها با `kubectl logs`
- لاگ HTTP از ingress
- health اپ: `GET /`
- health backend (در صورت deploy): `GET /healthz`

بکاپ
- از snapshot/backup های Supabase PostgreSQL استفاده کنید.
