Documentation HQ: [README](../README.md)

Reverse proxy guide

Goals
- Terminate TLS
- Support websockets and long-lived connections
- Optionally serve under a subpath

Nginx (subdomain)
- Use deploy/nginx.conf server block for okr.example.com
- For a ready-made company-domain template, use deploy/nginx.okr.mycompany.com.conf
- Ensure proxy_read_timeout and proxy_send_timeout >= 3600
- Pass Upgrade and Connection headers for websocket

Nginx (subpath)
- Use the /okr location example in deploy/nginx.conf
- Set BASE_URL_PATH=okr in the app environment
- Rewrite to strip the prefix before proxying

Caddy (example)
- Reverse proxy to :8501 with header upgrade support and TLS
- Add header Connection "upgrade" and keepalive timeouts

Traefik (example)
- Define an IngressRoute with the appropriate entrypoints
- Enable websocket, timeouts, and sticky sessions if desired

Common pitfalls
- Missing websocket headers causes blank page or reconnect loops
- Not setting BASE_URL_PATH when hosting under a subpath breaks static assets
- Short proxy timeouts break long interactions
