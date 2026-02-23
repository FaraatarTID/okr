Documentation HQ: [README](../../../README.md)

# راهنمای یکپارچه استقرار و عملیات (فارسی)

این سند مرجع اصلی فارسی برای استقرار، چک‌لیست go-live، الزامات پایلوت داخلی و عملیات روزانه است.

این سند محتوای تکراری runbook/checklist/operations را در یک مرجع نگه‌داری‌شده یکپارچه می‌کند.

آخرین به‌روزرسانی: 2026-02-22

## 1) کاربرد این سند
- استقرار اولیه روی Docker Compose یا Kubernetes
- کنترل‌های امنیتی و پیکربندی قبل از go-live
- چک‌های پایلوت داخلی
- عملیات روزانه و پاسخ به رخداد

## 2) حداقل الزامات Production
- `OKR_BACKEND_PROXY_MUTATIONS=true`
- `OKR_BACKEND_API_URL` تنظیم و قابل‌دسترسی
- `OKR_BACKEND_SERVICE_TOKEN` قوی
- `OKR_BACKEND_SIGNING_SECRET` قوی
- `OKR_BACKEND_SECURITY_STATE_BACKEND=database|redis`
- اگر `redis`: مقدار `OKR_BACKEND_SECURITY_STATE_REDIS_URL` الزامی است
- `OKR_BOOTSTRAP_ADMIN_PASSWORD` قوی و تنظیم‌شده
- `OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false`
- `OKR_ALLOW_LOCAL_READ_FALLBACK=false`
- `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false`
- `OKR_STRICT_RUNTIME_PREFLIGHT=true`
- تنظیم PDF:
  - `PDF_METHOD=pdfshift` به‌همراه `pdfshift_api_key`، یا
  - `PDF_METHOD=chromium` به‌همراه runtimeِ Playwright/Chromium

اعتبارسنجی قبل از startup:
```bash
python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml
```

## 3) جریان استقرار اولیه
1. آماده‌سازی زیرساخت (سرور/کلاستر، DB، reverse proxy، TLS، DNS)
2. آماده‌سازی تنظیمات runtime (`deploy/docker/.env` و `deploy/secrets/secrets.toml`)
3. اجرای deploy-config gate
4. بالا آوردن سرویس‌ها:
   - Compose: `docker compose -f deploy/docker/docker-compose.yml up -d --build`
   - Kubernetes: apply کردن manifestهای `deploy/k8s/`
5. بررسی health:
   - App: `GET /`
   - Backend API: `GET /healthz`
6. سخت‌سازی ورود اولیه:
   - production: `admin/<OKR_BOOTSTRAP_ADMIN_PASSWORD>`
   - تغییر فوری رمز
   - ساخت ادمین‌های نام‌دار و غیرفعال‌سازی کاربران تست

## 4) چک‌لیست go-live (خلاصه)
- runtime preflight بدون خطای بحرانی
- مسیرهای write/timer/admin/learning-loop/alignment با backend فعال سالم هستند
- مسیر async job سالم است (`backend-worker` jobها را تکمیل می‌کند)
- RBAC برای admin/manager/member صحیح است
- سخت‌سازی پورت‌ها کامل است (public فقط `80/443`، backend خصوصی)
- بکاپ/بازیابی DB تست شده است
- مانیتورینگ و جمع‌آوری لاگ فعال است

## 5) چک‌های پایلوت داخلی
- بررسی/اجرای `docs/V2_PRIORITIZED_ISSUE_LIST.md`
- تایید DSN کم‌اختیار در runtime (هرگز `postgres`)
- خصوصی ماندن backend API
- غیرفعال‌بودن scoped fallbackها در production
- تایید امنیت/انطباق برای data-flow مربوط به AI قبل از فعال‌سازی AI خارجی

تست‌های guard پیشنهادی:
```bash
python -m pytest tests/test_streamlit_form_guardrails.py -q
python -m pytest tests/test_auth_rate_limit.py -q
python -m pytest tests/test_selector_integrity_guardrails.py -q
python -m pytest tests/test_atlas_cache_performance.py -q
python -m pytest tests/test_database_engine_pooling.py -q
```

## 6) عملیات روزانه
- پایش uptime (`/`, `/healthz`) و لاگ‌های proxy/container
- پایش فشار quota روی `/v1/jobs` (`429` و `Retry-After`)
- بررسی audit eventهای DB-backed در جدول `audit_event` (با fallback در `logs/audit.log`)
- چرخش دوره‌ای credentialها
- حفظ checkهای اجباری CI روی branch اصلی

### 6.1) عملیات Audit Event (رخداد/Forensics)
- مخزن اصلی: جدول `audit_event`
- فیلدهای مرجع: `actor`, `action`, `entity`, `result`, `details_json`, `correlation_id`, `request_id`, `created_at`
- fallback: `logs/audit.log` در صورت اختلال موقت sink دیتابیس

پرس‌وجوهای رایج:
```sql
-- آخرین رخدادهای failure
SELECT created_at, actor, action, entity, result, details_json
FROM audit_event
WHERE result = 'failure'
ORDER BY created_at DESC
LIMIT 200;
```

```sql
-- روند accepted/rejected در 24 ساعت اخیر
SELECT action, result, COUNT(*) AS total
FROM audit_event
WHERE action IN ('job_submit_accepted', 'job_submit_rejected')
  AND created_at >= NOW() - INTERVAL '24 hours'
GROUP BY action, result
ORDER BY action, result;
```

```sql
-- ردیابی رویدادهای مرتبط با request/correlation id
SELECT created_at, actor, action, entity, result, request_id, correlation_id
FROM audit_event
WHERE request_id = :request_id OR correlation_id = :correlation_id
ORDER BY created_at ASC;
```

نگه‌داری خودکار:
- `backend-worker` براساس `OKR_BACKEND_AUDIT_RETENTION_DAYS` (پیش‌فرض `365`) جدول `audit_event` را prune می‌کند.
- cadence و batch با prune مربوط به async job مشترک است (`OKR_BACKEND_JOB_PRUNE_INTERVAL_SECONDS`, `OKR_BACKEND_JOB_PRUNE_BATCH_SIZE`).

## 7) پاسخ به رخداد
- خطای startup ناشی از strict preflight را incident پیکربندی در نظر بگیرید
- قبل از تغییرات پرریسک snapshot بگیرید
- rollback تست‌شده داشته باشید (image tag + config)
- فقط در شرایط اضطراری غیر-production fallback scoped را موقت فعال کنید:
  - `OKR_ALLOW_LOCAL_MUTATION_FALLBACK=true` برای write/timer/job
  - `OKR_ALLOW_LOCAL_READ_FALLBACK=true` برای readهای proxied
- بعد از پایداری سرویس، fallback موقت را سریعاً غیرفعال کنید

## 8) مراجع مرتبط
- راهنمای کامل استقرار: `DEPLOYMENT_FA.md`
- مرجع تنظیمات: `docs/CONFIG_REFERENCE_FA.md`
- جزئیات Compose: `docs/DOCKER_COMPOSE_FA.md`
- جزئیات Kubernetes: `docs/KUBERNETES_FA.md`
- جزئیات Reverse Proxy: `docs/REVERSE_PROXY_FA.md`
- عیب‌یابی: `docs/TROUBLESHOOTING_FA.md`
