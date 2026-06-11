# Morpheme Studios — VPS Deployment Guide (no Docker)

**Stack:** Ubuntu LTS · PostgreSQL · **Redis** · Python 3.12 + gunicorn · **Celery worker** · Nginx + Certbot · static Vite build.
**No Docker, no ClamAV.** Time-consuming work (notification + confirmation emails) is **offloaded to a Celery background worker** with Redis as broker; Redis also backs the DRF throttle cache. Uploads are validated in-process (type + size + magic bytes).

## 0. Shape

PostgreSQL = data. Redis = Celery broker/result backend + cache. gunicorn = the web app. Celery worker = background jobs (emails) so form submissions return instantly. Nginx = TLS + static + proxy.

## 1. System packages

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv postgresql redis-server nginx certbot python3-certbot-nginx git
sudo systemctl enable --now redis-server
# Node (for building the frontend) — via nodesource or nvm:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs
```

## 2. PostgreSQL

```bash
sudo -u postgres psql -c "CREATE DATABASE morpheme_studios;"
sudo -u postgres psql -c "CREATE USER morpheme WITH PASSWORD '!!m0RphEMe$Tudi0s2026!!';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE morpheme_studios TO morpheme;"
```

## 3. Backend

```bash
sudo useradd -m -s /bin/bash morpheme
sudo mkdir -p /srv/morpheme && sudo chown morpheme:www-data /srv/morpheme
# as user 'morpheme':
git clone <repo> /srv/morpheme/backend     # or rsync the Morpheme-Studios-Backend dir
cd /srv/morpheme/backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements/prod.txt
cp .env.example .env && chmod 600 .env      # then edit: SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, SMTP, Turnstile

.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
```

(Throttle counters/cache live in Redis — no cache table needed.)

## 4. gunicorn + Celery worker (systemd)

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/morpheme.service
sudo cp deploy/celery.service   /etc/systemd/system/morpheme-celery.service
sudo systemctl daemon-reload
sudo systemctl enable --now morpheme morpheme-celery
sudo systemctl status morpheme morpheme-celery   # both active
# Verify the worker registered the tasks:
journalctl -u morpheme-celery -n 30   # look for: tasks: notify_new_lead, notify_new_application, send_confirmation_email
```

Form submissions enqueue the email task and return immediately; the worker sends it. If the worker is down, jobs queue in Redis and run when it comes back.

## 5. Frontend (static build)

```bash
cd /srv/morpheme/frontend           # clone/rsync Morpheme-Studios-Frontend here
npm ci
# Same-origin: the API is served at /api on the apex domain (Nginx proxies it),
# so the SPA targets the apex domain — NOT a separate api. subdomain.
VITE_API_URL=https://morphemestudios.com npm run build   # -> dist/
```

## 6. Nginx + TLS

```bash
sudo mkdir -p /etc/nginx/snippets
sudo cp /srv/morpheme/backend/deploy/nginx-security-headers.conf /etc/nginx/snippets/morpheme-security-headers.conf
sudo cp /srv/morpheme/backend/deploy/nginx-morphemestudios.conf /etc/nginx/sites-available/morphemestudios
sudo ln -s /etc/nginx/sites-available/morphemestudios /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d morphemestudios.com -d www.morphemestudios.com   # adds 443 + redirect + HSTS
```

Security headers (HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP) are applied via the snippet to all Nginx-served responses (SPA HTML, static, media). API/admin responses get equivalent headers from Django, so the snippet is deliberately not included on those proxied locations (avoids duplicate CSP). Adjust the CSP `connect-src`/`img-src` in the snippet to your real API/media origins.

## 6b. Redis durability + DB separation

Apply persistence + no-eviction so queued Celery tasks survive a restart and are
never evicted. On Ubuntu 24.04 the main config has **no `conf.d` include**, so
write directly to `/etc/redis/redis.conf` (do NOT use `/etc/redis/redis.conf.d/`
— it is ignored):

```bash
sudo tee -a /etc/redis/redis.conf >/dev/null <<'CONF'

# --- Morpheme Studios ---
appendonly yes
appendfsync everysec
maxmemory-policy noeviction
CONF
sudo systemctl restart redis-server

# Verify (must report 'yes' and 'noeviction'):
redis-cli config get appendonly
redis-cli config get maxmemory-policy
```

This project also uses **separate Redis logical DBs**: cache = DB 0, Celery
broker = DB 1, results = DB 2 (so a cache flush/eviction can't drop queued
tasks). Defaults are derived from `REDIS_URL`; the env templates set them
explicitly.

## 7. Updating (deploy a change)

```bash
cd /srv/morpheme/backend && git pull && .venv/bin/pip install -r requirements/prod.txt
.venv/bin/python manage.py migrate && .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart morpheme
cd /srv/morpheme/frontend && git pull && npm ci && npm run build   # SPA refresh
```

## 8. Backups (off-box) + restore

Off-box backups (survive total VPS loss) are handled by `deploy/backup.sh` +
`deploy/backup.cron` (Postgres dump + media tar pushed to Backblaze B2 via
rclone, with local/remote retention). Full setup and the **restore runbook** are
in **[09-backup-and-restore.md](./09-backup-and-restore.md)**.

```bash
sudo apt install -y rclone postgresql-client

# Backup dir must be owned by the user the job runs as (morpheme) — it cannot
# create dirs under root-owned /srv itself:
sudo mkdir -p /srv/backups && sudo chown morpheme:morpheme /srv/backups

# Configure rclone AS the morpheme user (the cron + script run as morpheme, and
# rclone reads ~/.config/rclone of the running user):
sudo -u morpheme rclone config                  # create remote "b2" -> your bucket

sudo chmod +x /srv/morpheme/backend/deploy/backup.sh
sudo crontab -u morpheme /srv/morpheme/backend/deploy/backup.cron
sudo -u morpheme /srv/morpheme/backend/deploy/backup.sh   # run once to verify
sudo -u morpheme rclone lsf b2:morpheme-backups/db/       # confirm off-box copy
```

## 9. Monitoring

- `systemctl status morpheme` / `journalctl -u morpheme` for app logs.
- Optional: set `SENTRY_DSN` in `.env` for error tracking.
- External uptime check against `https://morphemestudios.com/health` and `https://morphemestudios.com/ready` (Nginx exact-match locations proxy these to Django; `/ready` returns 200 only when DB + Redis are reachable).

## Security checklist (already enforced in code)

- Argon2 hashing · JWT access in body + HttpOnly/Secure/SameSite refresh cookie (rotation + blacklist) · django-axes lockout.
- DRF throttling (Redis-cache backed) · CSP/HSTS/nosniff/frame-deny in `prod.py` + Nginx snippet · CORS locked to known origins.
- Uploads: PDF-only, size cap, magic-byte sniff; private files on a non-public root, served only via signed `/protected/<token>` → internal `/_protected/` X-Accel-Redirect.
- Run `ufw allow 22,80,443`, fail2ban, SSH key-only.
