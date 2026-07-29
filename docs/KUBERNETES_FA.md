# راهنمای Kubernetes (مسیر سازگاری)
Documentation HQ: [README](../README.md)

این فایل برای سازگاری لینک‌ها نگه داشته شده است.

منابع canonical:
- راهنمای اصلی استقرار: [../DEPLOYMENT_FA.md](../DEPLOYMENT_FA.md)
- مانيفست‌های Kubernetes (در حد اسکلت): [../deploy/k8s](../deploy/k8s)  
  - پوشه `deploy/k8s/` در حال حاضر شامل اجزای بک‌اند (backend-api/backend-worker) و رازهای (secret) ارتباط دیتابیس است و برای استقرار production-ready کامل stack شامل `spa-web`/`spa-bff`، PostgreSQL، Ingress و NetworkPolicy هنوز تکمیل نشده است.
- مرجع تنظیمات و سیاست Runtime: [CONFIG_REFERENCE_FA.md](CONFIG_REFERENCE_FA.md)
