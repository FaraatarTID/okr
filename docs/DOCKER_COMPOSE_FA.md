# استقرار با Docker Compose
Documentation HQ: [README](../README.md)

سرویس‌های پشته:
- `okr` (رابط Streamlit)
- `backend-api` (سرویس داخلی FastAPI برای mutation/timer/job)
- `backend-worker` (worker غیرهمزمان برای AI/PDF)

تعامل سرویس‌ها:
- `okr` درخواست‌های داخلی را با `OKR_BACKEND_SERVICE_TOKEN` به backend می‌فرستد.
- با `OKR_BACKEND_PROXY_MUTATIONS=true` (پیش‌فرض)، جریان‌های نوشتنی UI از `backend-api` عبور می‌کنند.
- `backend-api` jobها را در جدول `async_job` ذخیره می‌کند.
- `backend-worker` jobهای `ai.generate_json` و `pdf.weekly` را اجرا می‌کند.
- در production رفتار پیش‌فرض fail-closed است.
- fallback اضطراری فقط با `OKR_ALLOW_LOCAL_BACKEND_FALLBACK=true` و صرفا غیر production.

سناریوی پیشنهادی: یک هاست با زیر‌دامنه
- `deploy/docker/.env.example` را به `deploy/docker/.env` کپی کنید.
- برای زیر‌دامنه، `BASE_URL_PATH` را خالی بگذارید.
- مقادیر حیاتی را تنظیم کنید:
  - `OKR_DATABASE_URL` (pooler `:6543` + `sslmode=require`)
  - `OKR_BACKEND_SERVICE_TOKEN`
  - `OKR_BACKEND_SIGNING_SECRET`
  - `OKR_BACKEND_PROXY_MUTATIONS=true`
  - `OKR_BACKEND_SECURITY_STATE_BACKEND=database`
  - `PDFSHIFT_API_KEY`
- سرویس‌ها را بالا بیاورید:
  - `docker compose -f deploy/docker/docker-compose.yml up -d --build`
- Nginx را جلوی سرویس قرار دهید (TLS روی proxy).

سناریوی زیر‌مسیر
- `BASE_URL_PATH` را مثلا `okr` بگذارید.
- در reverse proxy مسیر `/okr` را rewrite کنید.

پایگاه‌داده
- DB موردنیاز: Supabase PostgreSQL
- مقدار `OKR_DATABASE_URL` را در `.env` بگذارید.
- برای runtime از transaction pooler روی `:6543` استفاده کنید.

secrets
- در صورت نیاز فایل secrets را بسازید و mount کنید:
  - `/app/streamlit_app/.streamlit/secrets.toml`
- از `deploy/secrets/secrets.toml.example` به‌عنوان template استفاده کنید.
- اگر mount ندارید، معادل env vars را در `.env` بگذارید.
- قبل از go-live این گیت را اجرا کنید:
  - `python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml`

پایداری داده
- تمام داده runtime در Supabase PostgreSQL ذخیره می‌شود.
- بکاپ DB باید فعال باشد.

سلامت و لاگ
- سلامت اپ: `GET /` باید `200` برگرداند.
- سلامت backend (پیش‌فرض host-local):
  - `GET http://127.0.0.1:${OKR_BACKEND_HOST_PORT:-8100}/healthz`
- لاگ‌ها:
  - `docker compose logs okr`
  - `docker compose logs backend-api`
  - `docker compose logs backend-worker`

ارتقا
- کد/ایمیج جدید را pull کنید و سرویس‌ها را rebuild/restart کنید.

بازگشت نسخه
- کانتینر را با image tag قبلی recreate کنید.
