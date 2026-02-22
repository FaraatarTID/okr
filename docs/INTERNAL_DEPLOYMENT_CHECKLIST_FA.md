# چک‌لیست استقرار داخلی و امنیت
Documentation HQ: [README](../README.md)

این چک‌لیست برای sign-off پایلوت داخلی سازمان است.

فاز 1: آماده‌سازی
- [ ] `deploy/secrets/secrets.toml.example` را به `secrets.toml` runtime کپی و تکمیل کنید.
- [ ] گیت deploy config را اجرا کنید و خطاها را رفع کنید:
  - `python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml`
- [ ] سینتکس TOML secrets را بررسی کنید (هر کلید در یک خط، بدون blob چندخطی داخل quote). مثال:
  ```toml
  PDF_METHOD = "pdfshift"
  OKR_BACKEND_PROXY_MUTATIONS = true
  OKR_ALLOW_LOCAL_BACKEND_FALLBACK = false
  OKR_STRICT_RUNTIME_PREFLIGHT = true
  ```
- [ ] provider AI را انتخاب کنید (`openai_compatible` برای gateway داخلی توصیه می‌شود).
- [ ] `ALLOW_EXTERNAL_AI=false` بماند مگر تایید صریح وجود داشته باشد.
- [ ] `OKR_BACKEND_SERVICE_TOKEN` قوی تنظیم شود.
- [ ] `OKR_BACKEND_SIGNING_SECRET` تنظیم و `OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true` حفظ شود.
- [ ] در production مقدار `OKR_BACKEND_SECURITY_STATE_BACKEND=database` حفظ شود تا nonce/rate-limit بین replicaها مشترک بماند.
- [ ] `docs/ACCEPTED_FINDINGS_IMPLEMENTATION_PLAN.md` مرور و اجرا شود.
- [ ] `DEPLOYMENT.md` و `docs/CONFIG_REFERENCE.md` مرور شوند.

فاز 2: زیرساخت
- [ ] استقرار در محیط کنترل‌شده داخلی با Docker Compose یا Kubernetes انجام شود.
- [ ] برنامه پشت Nginx/Traefik با TLS قرار گیرد.
- [ ] دسترسی به شبکه سازمان/VPN محدود شود.
- [ ] اتصال PostgreSQL (داخلی یا endpoint خصوصی تاییدشده) برقرار باشد.
- [ ] `OKR_DATABASE_URL` با runtime role کم‌اختیار (مثل `okr_app`) تنظیم شود.
- [ ] DB-role verification به عنوان check اجباری go-live انجام شود.
- [ ] پشته backend (`okr`، `backend-api`، `backend-worker`) بالا باشد.
- [ ] `OKR_BACKEND_API_URL` در `okr` تنظیم و `OKR_BACKEND_PROXY_MUTATIONS=true` فعال باشد.
- [ ] `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` در production false/unset باشد.
- [ ] رفتار برگشتی ناامن حذف شده باقی بماند (no direct local mutation fallback در production).
- [ ] bind آدرس backend خصوصی بماند (`127.0.0.1` مگر نیاز خاص).

فاز 3: امنیت و انطباق
- [ ] policy رمز و hardening ادمین اعمال شده باشد.
- [ ] جریان داده/provider AI توسط امنیت/انطباق تایید شده باشد.
- [ ] بکاپ و retention دیتابیس فعال باشد.
- [ ] مرزبندی RBAC (admin/manager/member) در کاربران پایلوت تایید شود.
- [ ] secrets خارج از git و در secret storage تاییدشده نگهداری شوند.
- [ ] مرز سرویس داخلی رعایت شود: backend API عمومی نشود.

فاز 4: تست و go-live
- [ ] smoke test: login، ساخت OKR، timer، dashboard، report، AI (در صورت فعال بودن)
- [ ] تست guard فرم:
  - `python -m pytest tests/test_streamlit_form_guardrails.py -q`
- [ ] تست throttle/login budget:
  - `python -m pytest tests/test_auth_rate_limit.py -q`
- [ ] تست integrity selector:
  - `python -m pytest tests/test_selector_integrity_guardrails.py -q`
- [ ] تست cache/latency اطلس:
  - `python -m pytest tests/test_atlas_cache_performance.py -q`
- [ ] تست timezone timestamp:
  - `python -m pytest tests/test_timestamp_timezone_guardrails.py -q`
- [ ] تست UTC API:
  - `python -m pytest tests/test_time_api_guardrails.py -q`
- [ ] تست bootstrap/cache چرخه:
  - `python -m pytest tests/test_app_cycle_cache_snapshot.py -q`
- [ ] تست pooling config دیتابیس:
  - `python -m pytest tests/test_database_engine_pooling.py -q`
- [ ] تست ساختاری mapper/reload:
  - `python -m pytest tests/test_models_import_consistency.py tests/test_models_relationship_resolution.py tests/test_hot_reload_model_bindings.py tests/test_hot_reload_model_rebinding.py tests/test_no_duplicate_top_level_functions.py -q`
- [ ] تست identity/cache invalidation مدل:
  - `python -m pytest tests/test_model_binding_identity_guard.py tests/test_hot_reload_cache_invalidation.py -q`
- [ ] مسیر write با backend API فعال موفق باشد.
- [ ] رفتار PDF/report با `PDF_METHOD=pdfshift` تایید شود.
- [ ] جریان job در backend-worker برای AI/PDF تایید شود.
- [ ] پایلوت محدود اجرا و بازخورد جمع‌آوری شود.
- [ ] لاگ app/proxy در پایلوت پایش شود.

نگهداری مستمر
- [ ] وابستگی‌ها به‌صورت دوره‌ای به‌روزرسانی شوند.
- [ ] credentialها و API keyها بر اساس برنامه rotate شوند.
- [ ] بعد از تغییرات بزرگ زیرساخت/provider، policy AI دوباره بررسی شود.
