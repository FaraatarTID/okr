# مرجع تنظیمات (Configuration Reference)
Documentation HQ: [README](../README.md)

این سند نسخه فارسی مرجع تنظیمات runtime است.

نمای کلی
- ترتیب خواندن تنظیمات:
  1. Environment variables
  2. Streamlit secrets (`streamlit_app/.streamlit/secrets.toml`)

دیتابیس
- env keys:
  - `OKR_DATABASE_URL` (توصیه‌شده)
  - `DATABASE_URL` (alias)
- نمونه:
  - `postgresql+psycopg2://okr_app.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require`
- secrets:
  - ریشه: `OKR_DATABASE_URL`, `DATABASE_URL`
  - جدول `[database]` با کلید `url`
- رفتار اعتبارسنجی:
  - URL باید با `postgresql+psycopg2://` شروع شود
  - URL باید host داشته باشد

فلگ‌های سخت‌گیری URL دیتابیس
- `OKR_ALLOW_NON_SUPABASE_DB` (پیش‌فرض `1`)
  - `1`: حالت سازگاری نرم
  - `0`: سخت‌گیرانه Supabase
- `OKR_ALLOW_SUPABASE_SESSION_POOLER` (پیش‌فرض `0`)
- `OKR_ALLOW_SUPABASE_DIRECT_CONNECTION` (پیش‌فرض `0`)
- `OKR_ALLOW_SUPABASE_SUPERUSER` (پیش‌فرض `0`)

الزامات production
- `OKR_ALLOW_NON_SUPABASE_DB=0`
- استفاده از pooler تراکنشی Supabase (`*.pooler.supabase.com:6543`)
- `sslmode=require`
- استفاده از runtime role کم‌اختیار (مثل `okr_app`)
- عدم استفاده از `postgres` برای runtime app

کنترل pooling
- `OKR_DB_USE_NULL_POOL` (پیش‌فرض `1`)
- اگر `OKR_DB_USE_NULL_POOL=0`:
  - `OKR_DB_POOL_SIZE`
  - `OKR_DB_MAX_OVERFLOW`
  - `OKR_DB_POOL_TIMEOUT`
  - `OKR_DB_POOL_RECYCLE`

Streamlit server
- `PORT` (پیش‌فرض 8501)
- `BASE_URL_PATH` (برای subpath)
- فایل config:
  - `streamlit_app/.streamlit/config.toml`

PDF
- secrets:
  - `PDF_METHOD` (`pdfshift`)
  - `pdfshift_api_key` (برای خروجی PDF لازم)
- fallback env:
  - `PDF_METHOD`
  - `OKR_PDF_METHOD`
  - `PDFSHIFT_API_KEY`
- سیاست:
  - فقط `pdfshift` پشتیبانی می‌شود
  - در نبود PDFShift، fallback خروجی HTML

AI
- secrets:
  - `AI_PROVIDER` = `gemini` یا `openai_compatible`
  - `ALLOW_EXTERNAL_AI` (پیش‌فرض `false`)
  - `GEMINI_API_KEY`, `GEMINI_MODEL`
  - `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`
- fallback env:
  - `AI_PROVIDER`, `OKR_AI_PROVIDER`
  - `GEMINI_API_KEY`, `VITE_GEMINI_API_KEY`
  - `GEMINI_MODEL`
  - `AI_BASE_URL`, `OPENAI_BASE_URL`, `OLLAMA_BASE_URL`
  - `AI_MODEL`, `OPENAI_MODEL`, `OLLAMA_MODEL`
  - `AI_API_KEY`, `OPENAI_API_KEY`
  - `ALLOW_EXTERNAL_AI`, `OKR_ALLOW_EXTERNAL_AI`
- رفتار:
  - اگر `ALLOW_EXTERNAL_AI=false` باشد، تماس بیرونی AI مسدود است
  - provider نوع `openai_compatible` بدون Gemini کار می‌کند

سیاست Runtime preflight
- پیش‌فرض strict:
  - `OKR_STRICT_RUNTIME_PREFLIGHT=1`
  - مقدار `0` فقط برای رفع اشکال موقت
- preflight موارد زیر را بررسی می‌کند:
  - mode/key مربوط به PDF
  - wiring ایمن backend در production
  - وجود `OKR_BOOTSTRAP_ADMIN_PASSWORD` در production
- در strict mode، خطاهای بحرانی startup را متوقف می‌کنند

Backend API (توصیه‌شده برای مقیاس)
- Streamlit -> backend:
  - `OKR_BACKEND_API_URL`
  - `OKR_BACKEND_SERVICE_TOKEN`
  - `OKR_BACKEND_SIGNING_SECRET`
  - `OKR_BACKEND_DEFAULT_ACTOR`
  - `OKR_BACKEND_PROXY_MUTATIONS` (پیش‌فرض `true`)
  - `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` (پیش‌فرض `false`)
- runtime backend:
  - `OKR_BACKEND_HOST`
  - `OKR_BACKEND_PORT`
  - `OKR_BACKEND_ENFORCE_TOKEN`
  - `OKR_BACKEND_ENFORCE_REQUEST_SIGNING`
  - `OKR_BACKEND_REQUEST_SIGNING_WINDOW_SECONDS`
  - `OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS`
  - `OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS`
  - job quota vars برای user/team
- runtime worker:
  - `OKR_BACKEND_WORKER_POLL_SECONDS`

نکات عملیاتی backend
- با `OKR_BACKEND_API_URL` فعال، مسیرهای write + AI/PDF سنگین از backend عبور می‌کنند.
- `OKR_BACKEND_PROXY_MUTATIONS=true` authority نوشتن را در backend نگه می‌دارد.
- در production پیش‌فرض fail-closed است.
- در Docker Compose، backend روی `127.0.0.1` bind می‌شود.

پروفایل‌های پیشنهادی استقرار
- Streamlit Cloud:
  - مناسب MVP/demo
  - `PDF_METHOD=pdfshift`
  - `pdfshift_api_key` الزامی
  - `OKR_STRICT_RUNTIME_PREFLIGHT` سخت‌گیرانه
- Self-hosted:
  - `PDF_METHOD=pdfshift`
  - `AI_PROVIDER=openai_compatible` (در صورت نیاز gateway داخلی)
  - استقرار همزمان `okr` + `backend-api` + `backend-worker`
  - مناسب داده‌های محرمانه داخلی

حاکمیت release (CI)
- checkهای اجباری merge:
  - Docs HQ link check
  - Deploy config template gate
  - RBAC regression gate
  - Full pytest suite

Bootstrap ادمین
- روی اولین اجرای DB خالی:
  - username: `admin`
  - password:
    - production: `OKR_BOOTSTRAP_ADMIN_PASSWORD`
    - غیر production: fallback روی `admin`
- ادمین اولیه مجبور به تغییر رمز است.
- `OKR_BOOTSTRAP_ADMIN_PASSWORD` فقط از env خوانده می‌شود.

کنترل‌های policy احراز هویت
- `OKR_ENFORCE_STRONG_PASSWORD_POLICY`
  - production: پیش‌فرض فعال
  - non-production: پیش‌فرض غیرفعال
- `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN`
  - production: پیش‌فرض غیرفعال
  - non-production: پیش‌فرض فعال

سلامت و لاگ
- health endpoint: `GET /`
- لاگ runtime: stdout سرویس‌ها/کانتینرها
