# چک‌لیست استقرار سازمانی
Documentation HQ: [README](../README.md)

این چک‌لیست با `DEPLOYMENT.md` هم‌راستا است و برای:
- Docker Compose
- PostgreSQL
- Nginx
- HTTPS
- میزبانی زیر‌دامنه (`okr.mycompany.com`)

قبل از go-live همه موارد را تکمیل کنید.

آخرین به‌روزرسانی: 2026-02-20

انتخاب حالت
- اگر Streamlit Cloud استفاده می‌کنید: بخش `A`
- اگر سرور خودتان (Docker Compose) است: بخش `B`

A. چک‌لیست Streamlit Cloud (MVP)
- [ ] اپ به این مخزن در Streamlit Cloud متصل است.
- [ ] secrets در تنظیمات Streamlit Cloud قرار گرفته‌اند (نه در git).
- [ ] `PDF_METHOD=pdfshift` تنظیم شده است.
- [ ] `pdfshift_api_key` تنظیم شده است.
- [ ] `OKR_STRICT_RUNTIME_PREFLIGHT=1` تنظیم شده است.
- [ ] `GEMINI_API_KEY` تنظیم شده یا غیرفعال‌بودن AI مستند شده است.
- [ ] اپ بالا می‌آید و login کار می‌کند.
- [ ] مرحله SSH deploy در GitHub Actions به‌درستی skip می‌شود.
- [ ] می‌دانید SSH secrets فقط برای self-hosted لازم است.
- [ ] ریسک Streamlit Cloud برای داده محرمانه را پذیرفته‌اید.

B. چک‌لیست Self-hosted (Docker Compose + Nginx + TLS)

1. پیش‌نیازها
- [ ] سرور آماده و قابل‌دسترسی (SSH) است.
- [ ] Docker Engine و Docker Compose plugin نصب هستند.
- [ ] Nginx نصب است.
- [ ] DNS A record برای `okr.mycompany.com` ثبت شده است.
- [ ] endpoint و credentialهای PostgreSQL آماده است.
- [ ] روش TLS (PKI داخلی یا Certbot) مشخص شده است.

2. مخزن و پیکربندی
- [ ] مخزن روی سرور clone شده است.
- [ ] `deploy/docker/.env` از `.env.example` ساخته شده است.
- [ ] در صورت نیاز از `.env.mycompany.example` استفاده شده است.
- [ ] `OKR_DATABASE_URL` روی pooler `:6543` با `sslmode=require` تنظیم شده است.
- [ ] runtime DB user کم‌اختیار است (`okr_app`، نه `postgres`).
- [ ] DB-role verification به عنوان release gate انجام شده است.
- [ ] برای زیر‌دامنه، `BASE_URL_PATH` خالی است.
- [ ] secrets اختیاری در `deploy/secrets/secrets.toml` آماده است.
- [ ] گیت deploy config پاس می‌شود:
  - `python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml`
- [ ] `PDF_METHOD=pdfshift` تنظیم شده است.
- [ ] `pdfshift_api_key` موجود است.
- [ ] `OKR_BACKEND_API_URL` تنظیم شده است.
- [ ] `OKR_BACKEND_SERVICE_TOKEN` قوی تنظیم شده است.
- [ ] `OKR_BACKEND_SIGNING_SECRET` بین سرویس‌ها یکسان است.
- [ ] `OKR_BOOTSTRAP_ADMIN_PASSWORD` قوی تنظیم شده است.
- [ ] `OKR_BACKEND_PROXY_MUTATIONS=true` تنظیم شده است.
- [ ] `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` در production false/unset است.
- [ ] `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN` در production false/unset است.
- [ ] `OKR_STRICT_RUNTIME_PREFLIGHT=1` تنظیم شده است.
- [ ] `GEMINI_API_KEY` تنظیم شده یا تصمیم غیرفعال‌سازی AI مستند است.

3. اجرای اپ
- [ ] اپ با دستور compose اجرا شده است.
- [ ] سرویس‌های `okr`، `backend-api`، `backend-worker` در وضعیت Up هستند.
- [ ] health local روی `http://127.0.0.1:8501/` پاسخ می‌دهد.
- [ ] health backend روی `http://127.0.0.1:8100/healthz` پاسخ می‌دهد.
- [ ] خطای migration در startup وجود ندارد.
- [ ] حلقه job worker سالم است.

4. Reverse Proxy
- [ ] تنظیم Nginx برای proxy به `127.0.0.1:8501` اعمال شده است.
- [ ] هدرهای websocket (`Upgrade`, `Connection`) تنظیم شده‌اند.
- [ ] timeoutها حداقل `3600` هستند.
- [ ] `nginx -t` پاس می‌شود.
- [ ] Nginx با موفقیت reload شده است.

5. TLS
- [ ] گواهی HTTPS صادر و نصب شده است.
- [ ] HTTP به HTTPS ریدایرکت می‌شود.
- [ ] `curl -I https://okr.mycompany.com` پاسخ موفق دارد.

6. سخت‌سازی ورود اولیه
- [ ] ورود اولیه روی DB خالی در production با `admin/<OKR_BOOTSTRAP_ADMIN_PASSWORD>` انجام می‌شود.
- [ ] fallback `admin/admin` در production استفاده نمی‌شود.
- [ ] رمز ادمین بلافاصله تغییر می‌کند.
- [ ] اکانت‌های ادمین نام‌دار ساخته می‌شوند.
- [ ] کاربران تست/بدون استفاده غیرفعال شده‌اند.
- [ ] حداقل یک OKR cycle ساخته شده است.

7. smoke test عملکردی
- [ ] login/logout کار می‌کند.
- [ ] ساخت Goal > Objective > KR > Task کار می‌کند.
- [ ] جریان‌های write با backend API فعال کار می‌کنند.
- [ ] timer start/stop کار می‌کند.
- [ ] reportها render می‌شوند.
- [ ] reconnect loop مرورگر وجود ندارد.
- [ ] RBAC برای admin/manager/member درست است.
- [ ] preflight خطای بحرانی ندارد.

8. امنیت و عملیات
- [ ] دسترسی عمومی فقط روی پورت‌های `80/443` است.
- [ ] پورت `8501` عمومی نیست.
- [ ] پورت `8100` خصوصی است.
- [ ] بکاپ DB فعال و restore تست شده است.
- [ ] لاگ‌ها جمع‌آوری می‌شوند.
- [ ] uptime monitoring فعال است.
- [ ] فرایند rotation credential مستند است.
- [ ] secrets در git commit نمی‌شوند.

9. آمادگی ارتقا و rollback
- [ ] دستورهای ارتقا برای اپراتور مستند شده است.
- [ ] آخرین image پایدار ثبت شده است.
- [ ] فرایند rollback حداقل یک‌بار تست شده است.

10. GitHub Actions SSH Deploy (اختیاری)
- [ ] در صورت نیاز secrets تنظیم شده‌اند:
  - `ENABLE_SSH_DEPLOY=true`
  - `SSH_HOST` (یا `DEPLOY_HOST` / `HOST`)
  - `SSH_USER` (یا `DEPLOY_USER` / `USERNAME`)
  - `SSH_KEY` (یا `DEPLOY_KEY`)
  - `REMOTE_DEPLOY_DIR` (یا `DEPLOY_DIR`)
- [ ] `SSH_KEY` در GitHub Actions Secrets ذخیره شده است.
- [ ] private key در repository commit نشده است.

11. حاکمیت git (پیشنهادی)
- [ ] branch protection روی main فعال است.
- [ ] CI قبل از merge اجباری است.
- [ ] checkهای اجباری CI:
  - Docs HQ Link Check
  - Deploy Config Template Gate
  - RBAC Regression Gate
  - Full Test job

اسناد مرجع
- `DEPLOYMENT.md`
- `docs/CONFIG_REFERENCE.md`
- `docs/DOCKER_COMPOSE.md`
- `docs/REVERSE_PROXY.md`
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`
- `docs/INTERNAL_DEPLOYMENT_CHECKLIST.md`
