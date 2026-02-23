Documentation HQ: [README](README.md)

راهنمای استقرار سازمانی (نسخه فارسی)

این سند نسخه فارسی خلاصه‌شده برای استقرار امن است. برای جزئیات کامل، `DEPLOYMENT.md` را نیز مرجع قرار دهید.

بهترین مسیر پیشنهادی
- Docker Compose
- Supabase PostgreSQL
- Nginx reverse proxy
- HTTPS
- مسیر backend-assisted شامل `okr` + `backend-api` + `backend-worker`

الزامات مهم
- `OKR_DATABASE_URL` روی Supabase transaction pooler (`:6543`) با `sslmode=require`
- استفاده از runtime DB role کم‌اختیار (مثل `okr_app`، نه `postgres`)
- `OKR_BACKEND_SERVICE_TOKEN` قوی
- `OKR_BACKEND_SIGNING_SECRET` قوی
- `OKR_BOOTSTRAP_ADMIN_PASSWORD` قوی (در production اجباری): حداقل 12 کاراکتر شامل uppercase/lowercase/number/symbol
- `OKR_BACKEND_PROXY_MUTATIONS=true`
- `OKR_BACKEND_SECURITY_STATE_BACKEND=database` یا `redis` در production (اگر `redis` است، `OKR_BACKEND_SECURITY_STATE_REDIS_URL` اجباری است)
- `OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false` و `OKR_ALLOW_LOCAL_READ_FALLBACK=false` در production
- `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false` در production (در production حتی اگر true شود، runtime همچنان fail-open را اعمال نمی‌کند)
- PDF:
  - `PDF_METHOD=pdfshift` و `PDFSHIFT_API_KEY`، یا
  - `PDF_METHOD=chromium` با Playwright/Chromium runtime
- `OKR_STRICT_RUNTIME_PREFLIGHT=true`

گام‌های سریع

1) آماده‌سازی host
- Docker, Compose plugin, Nginx را نصب کنید.

2) گرفتن کد
```bash
git clone <YOUR_REPO_URL> okr
cd okr
```

3) ساخت env
```bash
cp deploy/docker/.env.example deploy/docker/.env
```
یا برای دامنه نمونه شرکت:
```bash
cp deploy/docker/.env.mycompany.example deploy/docker/.env
```

4) تنظیم secrets اختیاری
```bash
mkdir -p deploy/secrets
cp deploy/secrets/secrets.toml.example deploy/secrets/secrets.toml
```

5) اجرای گیت پیکربندی قبل از startup
```bash
python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml
```
باید بدون `ERROR` تمام شود.

6) بالا آوردن سرویس‌ها
```bash
docker compose -f deploy/docker/docker-compose.yml up -d --build
docker compose -f deploy/docker/docker-compose.yml ps
curl -I http://127.0.0.1:8501/
curl -f http://127.0.0.1:8100/healthz
```

7) تنظیم Nginx + DNS + TLS
- proxy را به `127.0.0.1:8501` بدهید.
- DNS دامنه را به IP سرور وصل کنید.
- TLS را با Certbot یا PKI داخلی فعال کنید.

8) ورود اولیه و hardening
- در production ورود اولیه: `admin/<OKR_BOOTSTRAP_ADMIN_PASSWORD>` (با الگوی strong بالا)
- در غیر production fallback: `admin/admin`
- بلافاصله رمز عبور را تغییر دهید.
- ادمین‌های واقعی را بسازید و کاربرهای تست را غیرفعال کنید.

9) اعتبارسنجی go-live
- login/logout
- ساخت Goal/Objective/KR/Task
- مسیر write با backend API
- timer
- report/PDF
- نبود reconnect loop
- عدم وجود خطای بحرانی preflight

اسناد مرتبط
- `DEPLOYMENT.md`
- `docs/DEPLOYMENT_OPERATIONS_GUIDE_FA.md`
- `docs/DOCKER_COMPOSE.md`
- `docs/DOCKER_COMPOSE_FA.md`
- `docs/TROUBLESHOOTING.md`
- `docs/TROUBLESHOOTING_FA.md`
