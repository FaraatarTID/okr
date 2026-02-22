# راهنمای اجرای اولیه (Runbook)
Documentation HQ: [README](../README.md)

این سند نسخه فارسی Runbook برای استقرار اولیه است.

1) ساخت و انتشار ایمیج (اختیاری)
- از GitHub Actions همین مخزن استفاده کنید، یا لوکال build کنید.

2) انتخاب مسیر استقرار
- Docker Compose روی یک VM (پیشنهادی برای شروع)
- Kubernetes در کلاستر (اختیاری)

3) تنظیم محیط
- `OKR_DATABASE_URL` برای Supabase PostgreSQL را تنظیم کنید (اجباری)
- نوع میزبانی را مشخص کنید: زیر‌دامنه یا زیر‌مسیر
- Reverse Proxy را با TLS و websocket آماده کنید
- تنظیم PDF:
  - همه محیط‌ها: `PDF_METHOD=pdfshift` و `pdfshift_api_key`
- تنظیم مسیر backend:
  - `OKR_BACKEND_API_URL` (پیش‌فرض compose: `http://backend-api:8100`)
  - `OKR_BACKEND_SERVICE_TOKEN` (توکن داخلی قوی)
  - `OKR_BACKEND_SIGNING_SECRET` (توصیه‌شده برای امضای درخواست داخلی)
  - `OKR_BOOTSTRAP_ADMIN_PASSWORD` (در production اجباری؛ حداقل 12 کاراکتر با uppercase/lowercase/number/symbol)
  - `OKR_BACKEND_PROXY_MUTATIONS=true` (توصیه‌شده)
  - `OKR_BACKEND_SECURITY_STATE_BACKEND=database` (در production اجباری)
  - در production مقدار `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN` را false/unset نگه دارید (runtime در production fail-open override را نادیده می‌گیرد)
  - در production مقدار `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` را false/unset نگه دارید
- در صورت فعال بودن AI، مقدار `GEMINI_API_KEY` یا provider معادل را تنظیم کنید
- در production، preflight سخت‌گیرانه را فعال نگه دارید: `OKR_STRICT_RUNTIME_PREFLIGHT=1`
- قبل از startup، گیت پیکربندی deploy را اجرا کنید:
  - `python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml`

4) بالا آوردن سرویس‌ها
- Compose: سرویس‌های `okr`، `backend-api`، `backend-worker` را اجرا کنید
- K8s: manifestها را apply کنید

5) بررسی‌های پس از استقرار
- Health check برنامه: `GET /`
- Health check backend: `GET /healthz` روی backend-api
- ورود اولیه با ادمین bootstrap:
  - production: `admin/<OKR_BOOTSTRAP_ADMIN_PASSWORD>`
  - غیر production/dev: fallback برابر `admin/admin`
- بلافاصله رمز عبور را تغییر دهید
- اولین cycle و کاربران اولیه را ایجاد کنید
- مطمئن شوید preflight خطای بحرانی ندارد
- یک خروجی PDF موفق بگیرید
- یک اکشن AI موفق اجرا کنید (یا صراحتا غیرفعال‌بودن AI را مستند کنید)
- مسیر async job را انتهابه‌انتها بررسی کنید (ارسال job و تکمیل توسط worker)
- مسیرهای write فرانت‌اند را با backend API تست کنید (CRUD نودها، timer، user/cycle/team admin، Learning Loop، alignment)
- در صورت نیاز health check provider را اجرا کنید:
  - `python streamlit_app/scripts/ai_provider_health_check.py`

6) یکپارچه‌سازی‌های اختیاری
- در صورت نیاز `secrets.toml` برای PDFShift یا AI provider تکمیل شود.

7) بکاپ و مانیتورینگ
- بکاپ خودکار DB
- uptime check روی endpoint عمومی
- نگهداری لاگ proxy و اپ

8) حفاظت از فرایند release
- branch protection روی main فعال باشد
- عبور CI قبل از merge اجباری باشد:
  - Docs HQ Link Check
  - Deploy Config Template Gate
  - RBAC Regression Gate
  - Full tests
