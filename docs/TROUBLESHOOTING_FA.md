# عیب‌یابی
Documentation HQ: [README](../README.md)

صفحه خالی یا reconnect loop
- هدرهای websocket در proxy (`Upgrade`/`Connection`) را بررسی کنید.
- اگر زیر‌مسیر دارید، `BASE_URL_PATH` باید درست تنظیم شده باشد.

خرابی خروجی PDF
- اگر PDFShift استفاده می‌کنید، `pdfshift_api_key` را در secrets بگذارید.
- مطمئن شوید `PDF_METHOD=pdfshift` است.
- اگر backend mode فعال است، `backend-worker` باید بالا باشد و `PDFSHIFT_API_KEY` داشته باشد.

خطاهای Runtime preflight
- اگر پیام `PDF_METHOD=pdfshift but PDFShift API key is missing` دیدید:
  - `pdfshift_api_key` را اضافه کنید.
- اگر پیام unsupported `PDF_METHOD` دیدید:
  - مقدار را `pdfshift` بگذارید.
- اگر پیام `OKR_BACKEND_PROXY_MUTATIONS=true but OKR_BACKEND_API_URL is not set` دیدید:
  - در UI خط `Config trace` را بررسی کنید (source: `env`/`secrets_root`/`secrets_app`/`default`)
  - در TOML از boolean واقعی استفاده کنید:
    - `OKR_BACKEND_PROXY_MUTATIONS = false`
  - override متضاد در env را حذف/اصلاح کنید و اپ را restart کنید.
- در strict mode (`OKR_STRICT_RUNTIME_PREFLIGHT=1`) startup تا رفع خطاهای بحرانی متوقف می‌ماند.

AI در دسترس نیست
- بررسی provider:
  - `python streamlit_app/scripts/ai_provider_health_check.py --json`
- اگر Gemini:
  - `AI_PROVIDER=gemini`
  - `GEMINI_API_KEY` معتبر و غیر placeholder
- اگر provider داخلی/لوکال:
  - `AI_PROVIDER=openai_compatible`
  - `AI_BASE_URL` و `AI_MODEL` تنظیم شده
  - endpoint از runtime قابل‌دسترسی باشد
- اگر backend mode فعال است:
  - `OKR_BACKEND_API_URL` از `okr` قابل‌دسترسی باشد
  - `OKR_BACKEND_SERVICE_TOKEN` بین سرویس‌ها یکسان باشد

خطاهای CRUD در UI
- اگر `OKR_BACKEND_PROXY_MUTATIONS=true`:
  - `OKR_BACKEND_API_URL` resolve شود
  - `/healthz` روی backend سالم باشد
  - `OKR_BACKEND_SERVICE_TOKEN` یکسان باشد
  - اگر signing فعال است، `OKR_BACKEND_SIGNING_SECRET` بین `okr` و `backend-api` یکسان باشد
  - لاگ backend برای 400/403 بررسی شود
- fallback محلی فقط برای شرایط اضطراری و غیر production:
  - `OKR_ALLOW_LOCAL_BACKEND_FALLBACK=true`

خطای migration
- DB از runtime قابل‌دسترسی باشد
- `OKR_DATABASE_URL` معتبر باشد و user مجوز DDL داشته باشد
- اگر `permission denied to reassign objects` دارید:
  - با admin role عملیات ownership/reassign را انجام دهید
  - runtime DSN را روی role کم‌اختیار (مثل `okr_app`) نگه دارید

خطای `Multiple classes found for path "User"`
- علت: stale mapper/class binding بعد از hot-reload
- همه importهای مدل باید از `src.models` باشند
- relationshipها ترجیحا lambda-resolved باشند
- تست‌های guard:
  - `python -m pytest tests/test_models_import_consistency.py tests/test_models_relationship_resolution.py tests/test_hot_reload_model_bindings.py tests/test_hot_reload_model_rebinding.py -q`
- اگر ادامه داشت، پروسه `okr` را restart کنید.

مشکل ورود
- ادمین پیش‌فرض فقط روی DB خالی ایجاد می‌شود.
- بعد از ورود از Admin Panel رمز را reset کنید.

خطاهای اتصال Supabase
- `OKR_DATABASE_URL` باید `postgresql+psycopg2://` باشد
- host باید شامل `supabase.com` باشد
- `sslmode=require` باید وجود داشته باشد
- برای runtime از transaction pooler `:6543` استفاده کنید
- اگر `MaxClientsInSessionMode` دیدید، از `:5432` به `:6543` بروید
- برای enforce سخت‌گیرانه URL در startup:
  - `OKR_ALLOW_NON_SUPABASE_DB=0`
- overrideهای کنترلی (فقط موارد استثنا):
  - `OKR_ALLOW_SUPABASE_SESSION_POOLER=1`
  - `OKR_ALLOW_SUPABASE_DIRECT_CONNECTION=1`
  - `OKR_ALLOW_SUPABASE_SUPERUSER=1`
- اگر رمز DB کاراکتر خاص دارد، URL-encode کنید.

خرابی assets در زیر‌مسیر
- rewrite باید prefix را حذف کند
- `--server.baseUrlPath` باید درست تنظیم باشد (در container CMD مدیریت می‌شود)

Timeout در تعاملات طولانی
- مقدار `proxy_read_timeout` و `proxy_send_timeout` را >= `3600` بگذارید.
