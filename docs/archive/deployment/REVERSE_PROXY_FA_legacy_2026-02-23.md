# راهنمای Reverse Proxy
Documentation HQ: [README](../../../README.md)

اهداف
- خاتمه TLS در proxy
- پشتیبانی websocket و ارتباطات طولانی
- پشتیبانی اختیاری از زیر‌مسیر
- خصوصی نگه داشتن backend API (عدم انتشار عمومی)

Nginx (زیر‌دامنه)
- از `deploy/nginx.conf` برای دامنه‌ای مثل `okr.example.com` استفاده کنید.
- template آماده شرکتی: `deploy/nginx.okr.mycompany.com.conf`
- `proxy_read_timeout` و `proxy_send_timeout` حداقل `3600`
- هدرهای websocket (`Upgrade`/`Connection`) تنظیم شوند
- فقط ترافیک UI از proxy عمومی عبور کند
- backend API (پورت پیش‌فرض `8100`) داخلی/loopback بماند
- endpointهای mutation backend (`/v1/nodes/*`, `/v1/timer/*`, `/v1/jobs/*`) را عمومی route نکنید

Nginx (زیر‌مسیر)
- مثال مسیر `/okr` را در `deploy/nginx.conf` استفاده کنید.
- در env مقدار `BASE_URL_PATH=okr` قرار دهید.
- قبل از proxy، prefix را rewrite و حذف کنید.

Caddy (نمونه)
- reverse proxy به `:8501` با پشتیبانی upgrade header و TLS
- هدر `Connection: upgrade` و timeout مناسب

Traefik (نمونه)
- IngressRoute با entrypoint مناسب
- websocket، timeout و sticky session بر اساس نیاز

خطاهای رایج
- نبود هدر websocket باعث blank page یا reconnect loop می‌شود
- تنظیم‌نشدن `BASE_URL_PATH` در زیر‌مسیر باعث خرابی assets می‌شود
- timeout کوتاه باعث قطع تعاملات طولانی می‌شود
- expose شدن پورت backend API سطح حمله را بالا می‌برد
