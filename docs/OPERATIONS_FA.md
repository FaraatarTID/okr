# راهنمای عملیات (Operations)
Documentation HQ: [README](../README.md)

اجرای اولیه
- migrationها در startup اجرا می‌شوند.
- حساب bootstrap روی DB خالی: `admin`
- منبع رمز production: `OKR_BOOTSTRAP_ADMIN_PASSWORD` (اجباری)
- fallback غیر production: `admin` (فقط برای توسعه)
- ادمین اولیه مجبور به تغییر رمز در اولین ورود است.

پشتیبان‌گیری
- برای Supabase PostgreSQL بکاپ خودکار/اسنپ‌شات فعال کنید.
- بازیابی را به‌صورت دوره‌ای تست کنید.

پایش
- uptime اپ: `GET /`
- uptime backend: `GET /healthz`
- لاگ Nginx برای access/error
- لاگ کانتینرهای `okr`، `backend-api` و `backend-worker`
- بررسی provider AI:
  - `python streamlit_app/scripts/ai_provider_health_check.py`
  - فقط بررسی config: `python streamlit_app/scripts/ai_provider_health_check.py --no-probe`
  - خروجی JSON: `python streamlit_app/scripts/ai_provider_health_check.py --json`

ارتقا
- Compose: pull image جدید و `up -d --build`
- Kubernetes: tag ایمیج جدید + rollout status

مدیریت secrets
- credentialها را فقط در secret manager/secrets نگه دارید (نه در git)
- چرخش دوره‌ای credentialها
- برای AI، کلیدها فقط در env/secrets
- provider را صریح تعیین کنید: `AI_PROVIDER`
- mode PDF را صریح تعیین کنید: `PDF_METHOD`
- در production توصیه می‌شود `OKR_STRICT_RUNTIME_PREFLIGHT=1`

سخت‌سازی امنیت
- TLS اجباری
- محدودسازی پورت‌های public (فقط proxy)
- runtime non-root
- firewall طوری تنظیم شود که فقط proxy به app دسترسی داشته باشد
- پورت backend خصوصی بماند (`127.0.0.1` در compose)
- امضای درخواست داخلی با `OKR_BACKEND_SIGNING_SECRET` فعال باشد
- در production مقدار `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN` را false/unset نگه دارید
- credentialهای DB را rotate کنید

پاسخ به رخداد
- قبل از تغییرات پرریسک snapshot بگیرید
- مراحل rollback برای Compose/K8s مستند و آماده باشد
- در شبکه داخلی ترجیحا pull-based deploy استفاده کنید

Runtime preflight
- در startup سازگاری PDF/API key و wiring بحرانی بررسی می‌شود.
- در strict mode اگر خطای بحرانی باشد startup متوقف می‌شود.
- برای رفع mismatch:
  - همه محیط‌ها: `PDF_METHOD=pdfshift` و `pdfshift_api_key`

نکته معماری
- read-heavy هنوز در Streamlit اجرا می‌شود.
- write/timer/job در backend services مدیریت می‌شود وقتی `OKR_BACKEND_API_URL` فعال است.
- در استقرار داخلی `OKR_BACKEND_PROXY_MUTATIONS=1` را فعال نگه دارید.
- در production `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` را false/unset نگه دارید.

حاکمیت release
- branch main با CI اجباری محافظت شود.
- checkهای اجباری:
  - Docs HQ link checker
  - Deploy config template gate
  - RBAC regression gate
  - Full pytest suite
