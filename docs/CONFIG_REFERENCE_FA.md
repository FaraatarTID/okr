Documentation HQ: [README](../README.md)

# مرجع تنظیمات (فارسی)

این سند مرجع کلیدهای اصلی پیکربندی runtime است.

## اولویت خواندن تنظیمات
1. Environment variables
2. Streamlit secrets (`streamlit_app/.streamlit/secrets.toml`)

## دیتابیس

- کلیدهای env:
  - `OKR_DATABASE_URL` (توصیه‌شده)
  - `DATABASE_URL` (alias)
- قالب معتبر:
  - `postgresql+psycopg2://...`
- سیاست production:
  - استفاده از Supabase transaction pooler (`*.pooler.supabase.com:6543`)
  - `sslmode=require`
  - استفاده از کاربر کم‌اختیار (مثل `okr_app`) و نه `postgres`

## Streamlit

- `PORT` (پیش‌فرض `8501`)
- `BASE_URL_PATH` (برای subpath)
- فایل: `streamlit_app/.streamlit/config.toml`

## PDF

- حالت‌های پشتیبانی‌شده:
  - `PDF_METHOD=pdfshift`
  - `PDF_METHOD=chromium`
- کلیدها:
  - برای `pdfshift`: `pdfshift_api_key` (در secrets) یا `PDFSHIFT_API_KEY` (env)
  - برای `chromium`: نصب Playwright + Chromium (اختیاری: `OKR_CHROMIUM_EXECUTABLE_PATH`)

## AI

- `AI_PROVIDER`: `gemini` یا `openai_compatible`
- `ALLOW_EXTERNAL_AI`: اگر `false` باشد، تماس بیرونی AI مسدود می‌شود.
- برای `gemini`:
  - `GEMINI_API_KEY`
  - `GEMINI_MODEL` (اختیاری)
- برای `openai_compatible`:
  - `AI_BASE_URL`
  - `AI_MODEL`
  - `AI_API_KEY` (اختیاری)

## Runtime Preflight

- `OKR_STRICT_RUNTIME_PREFLIGHT`:
  - پیش‌فرض: `true`
  - `false` فقط برای عیب‌یابی موقت
- در production:
  - `OKR_BOOTSTRAP_ADMIN_PASSWORD` اجباری است و باید strong باشد:
    - حداقل 12 کاراکتر
    - uppercase + lowercase + number + symbol
  - `OKR_BACKEND_SECURITY_STATE_BACKEND=database` یا `redis` اجباری است.
  - اگر `OKR_BACKEND_SECURITY_STATE_BACKEND=redis` باشد، `OKR_BACKEND_SECURITY_STATE_REDIS_URL` باید تنظیم شود.

## Backend API

### مسیر Streamlit به Backend
- `OKR_BACKEND_API_URL`
- `OKR_BACKEND_SERVICE_TOKEN`
- `OKR_BACKEND_SIGNING_SECRET`
- `OKR_BACKEND_DEFAULT_ACTOR`
- `OKR_BACKEND_PROXY_MUTATIONS` (توصیه: `true`)
- `OKR_ALLOW_LOCAL_MUTATION_FALLBACK` (production: `false`)
- `OKR_ALLOW_LOCAL_READ_FALLBACK` (production: `false`)
- `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` (legacy compatibility fallback when scoped flags are unset)

### Runtime Backend
- `OKR_BACKEND_HOST` (پیش‌فرض `0.0.0.0`)
- `OKR_BACKEND_PORT` (پیش‌فرض `8100`)
- `OKR_BACKEND_ENFORCE_TOKEN` (پیش‌فرض `true`)
- `OKR_BACKEND_ENFORCE_REQUEST_SIGNING`
  - پیش‌فرض production: `true`
  - پیش‌فرض non-production: `false`
- `OKR_BACKEND_REQUEST_SIGNING_WINDOW_SECONDS` (پیش‌فرض `300`)
- `OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS` (پیش‌فرض `60`)
- `OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS` (پیش‌فرض `120`)

### امنیت توزیع‌شده (Phase 2)
- `OKR_BACKEND_SECURITY_STATE_BACKEND`
  - production پیش‌فرض: `database`
  - non-production پیش‌فرض: `memory`
- `OKR_BACKEND_SECURITY_STATE_REDIS_URL`
  - وقتی backend روی `redis` باشد اجباری است.
- `OKR_BACKEND_SECURITY_STATE_REDIS_PREFIX`
  - اختیاری؛ پیش‌فرض: `okr:security`
- `OKR_BACKEND_SECURITY_STATE_CLEANUP_SECONDS` (پیش‌فرض `60`)
- وقتی backend روی `database` باشد:
  - nonce replay و rate-limit در جداول shared DB ذخیره می‌شوند:
    - `backend_request_nonce`
    - `backend_rate_limit_counter`
  - کنترل‌ها بین replicaها سازگار می‌مانند.
- وقتی backend روی `redis` باشد:
  - nonce replay و rate-limit در Redis shared key-space ذخیره می‌شوند.
  - `OKR_BACKEND_SECURITY_STATE_REDIS_URL` اجباری است و `OKR_BACKEND_SECURITY_STATE_REDIS_PREFIX` namespace کلیدها را تعیین می‌کند.

## Worker

- `OKR_BACKEND_WORKER_POLL_SECONDS` (پیش‌فرض `2`)
- `OKR_BACKEND_JOB_RETENTION_DAYS` (پیش‌فرض `14`؛ نگه‌داری jobهای terminal قبل از prune)
- `OKR_BACKEND_AUDIT_RETENTION_DAYS` (پیش‌فرض `365`؛ نگه‌داری `audit_event` قبل از prune)
- `OKR_BACKEND_JOB_PRUNE_INTERVAL_SECONDS` (پیش‌فرض `300`؛ تناوب prune توسط worker)
- `OKR_BACKEND_JOB_PRUNE_BATCH_SIZE` (پیش‌فرض `200`؛ سقف حذف در هر نوبت prune)

## Bootstrap ادمین

- اولین اجرا روی DB خالی:
  - username: `admin`
  - password:
    - production: `OKR_BOOTSTRAP_ADMIN_PASSWORD`
    - non-production: fallback برابر `admin`
- رمز اولیه ادمین باید در اولین ورود تغییر کند.
- `OKR_BOOTSTRAP_ADMIN_PASSWORD` فقط از env خوانده می‌شود (نه secrets).

## کنترل‌های احراز هویت

- `OKR_ENFORCE_STRONG_PASSWORD_POLICY`
  - پیش‌فرض production: فعال
  - پیش‌فرض non-production: غیرفعال
  - در حالت فعال: create/reset password باید strong باشد (الگوی بالا)
- `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN`
  - پیش‌فرض production: غیرفعال
  - پیش‌فرض non-production: فعال
  - در production حتی اگر true شود، runtime مسیر fail-open را نادیده می‌گیرد.

## Logging و Health

- App health: `GET /`
- Backend health: `GET /healthz`
- لاگ‌ها: stdout سرویس‌ها (container/service logs)

## Job Quotas (Phase 3)

- `OKR_BACKEND_JOB_USER_WINDOW_SECONDS` (پیش‌فرض `60`)
- `OKR_BACKEND_JOB_USER_MAX_REQUESTS` (پیش‌فرض `8`)
- `OKR_BACKEND_JOB_USER_DAILY_MAX_REQUESTS` (پیش‌فرض `200`)
- `OKR_BACKEND_JOB_USER_PENDING_MAX_REQUESTS` (پیش‌فرض `3`)
- `OKR_BACKEND_JOB_TEAM_WINDOW_SECONDS` (پیش‌فرض `60`)
- `OKR_BACKEND_JOB_TEAM_MAX_REQUESTS` (پیش‌فرض `60`)
- `OKR_BACKEND_JOB_TEAM_DAILY_MAX_REQUESTS` (پیش‌فرض `1200`)
- `OKR_BACKEND_JOB_TEAM_PENDING_MAX_REQUESTS` (پیش‌فرض `40`)
- `OKR_BACKEND_JOB_BACKOFF_BASE_SECONDS` (پیش‌فرض `3`)

Notes:
- `POST /v1/jobs` از `X-OKR-Idempotency-Key` پشتیبانی می‌کند.
- در quota/backoff reject، پاسخ `429` با `detail.error_code` و `detail.retry_after_seconds` برمی‌گردد.
- header `Retry-After` در همان پاسخ ارسال می‌شود.
- رویدادهای accepted/rejected submit در جدول `audit_event` (با fallback فایل log) ثبت می‌شوند.

## Audit Trail

- مخزن اصلی: جدول `audit_event`
- fallback: فایل `streamlit_app/logs/audit.log` وقتی sink دیتابیس موقتاً در دسترس نیست
- retention خودکار توسط worker:
  - `OKR_BACKEND_AUDIT_RETENTION_DAYS` (پیش‌فرض `365`)
