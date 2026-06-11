# Morpheme Studios — Backup & Disaster Recovery

Off-box backups so that **total VPS loss ≠ data loss**. Backups live in an
object store (Backblaze B2 by default — ~$6/TB/mo, free egress to restore;
swap the rclone remote for S3/Wasabi without changing the script).

## What is backed up
| Asset | Source | In backup |
|---|---|---|
| PostgreSQL | `pg_dump $DATABASE_URL` | `db/db-<stamp>.sql.gz` |
| Public media | `/srv/morpheme/backend/media` | `media/media-<stamp>.tar.gz` |
| Private media (CVs) | `/srv/morpheme/backend/private-media` | (same tar) |
| Environment / secrets | `/srv/morpheme/backend/.env` | **NOT** backed up by the script (secrets) — store in a password manager / secrets vault separately |

## Schedule & retention
- `deploy/backup.sh` runs daily 03:15 via `deploy/backup.cron`.
- **Local** copies kept 7 days (`LOCAL_RETENTION_DAYS`); **remote** copies kept 30 days (`REMOTE_RETENTION_DAYS`). Tune via env.

## One-time setup
The backup job runs as the `morpheme` user (cron), so the backup dir and the
rclone remote must belong to that user.
```bash
sudo apt install -y rclone postgresql-client
sudo mkdir -p /srv/backups && sudo chown morpheme:morpheme /srv/backups   # morpheme can't mkdir under /srv
sudo -u morpheme rclone config            # create remote "b2" as the morpheme user
sudo chmod +x /srv/morpheme/backend/deploy/backup.sh
sudo crontab -u morpheme /srv/morpheme/backend/deploy/backup.cron
sudo -u morpheme /srv/morpheme/backend/deploy/backup.sh   # run once; confirm files land in B2
```

---

# Restore Runbook (VPS destroyed → new VPS → full recovery)

Executable by any engineer. Assumes a fresh Ubuntu VPS and access to the B2 bucket + the saved `.env`.

### 0. Provision base (same as a fresh deploy — see docs/08 §1–2)
```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv postgresql redis-server nginx certbot python3-certbot-nginx git rclone postgresql-client nodejs
sudo systemctl enable --now postgresql redis-server
rclone config        # re-add the "b2" remote (read the app key from your vault)
```

### 1. Restore the database
```bash
sudo -u postgres psql -c "CREATE DATABASE morpheme_studios;"
sudo -u postgres psql -c "CREATE USER morpheme WITH PASSWORD '<from-vault>';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE morpheme_studios TO morpheme;"
rclone lsf b2:morpheme-backups/db/ | sort | tail -1        # newest dump
rclone copy b2:morpheme-backups/db/db-<stamp>.sql.gz /tmp/
gunzip -c /tmp/db-<stamp>.sql.gz | psql "postgres://morpheme:<pw>@127.0.0.1:5432/morpheme_studios"
```

### 2 & 3. Restore media + private media
```bash
sudo mkdir -p /srv/morpheme/backend && sudo chown morpheme:www-data /srv/morpheme/backend
rclone copy b2:morpheme-backups/media/media-<stamp>.tar.gz /tmp/
tar -xzf /tmp/media-<stamp>.tar.gz -C /srv/morpheme/backend   # recreates media/ + private-media/
```

### 4. Restore environment
```bash
# Recreate /srv/morpheme/backend/.env from your password manager (DATABASE_URL,
# DJANGO_SECRET_KEY, REDIS_URL, CELERY_*, EMAIL_*, TURNSTILE_*). chmod 600.
# NB: reusing the SAME DJANGO_SECRET_KEY keeps existing sessions/tokens valid;
# rotating it (recommended after a breach) invalidates them — expected.
```

### 5. Restore code + services
```bash
git clone <repo> /srv/morpheme/backend   # or rsync; then:
cd /srv/morpheme/backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements/prod.txt
.venv/bin/python manage.py migrate          # no-op if dump already current; safe
.venv/bin/python manage.py collectstatic --noinput
sudo cp deploy/gunicorn.service /etc/systemd/system/morpheme.service
sudo cp deploy/celery.service   /etc/systemd/system/morpheme-celery.service
sudo mkdir -p /etc/nginx/snippets
sudo cp deploy/nginx-security-headers.conf /etc/nginx/snippets/morpheme-security-headers.conf
sudo cp deploy/nginx-morphemestudios.conf /etc/nginx/sites-available/morphemestudios
sudo ln -sf /etc/nginx/sites-available/morphemestudios /etc/nginx/sites-enabled/
# frontend
cd /srv/morpheme/frontend && npm ci && VITE_API_URL=https://morphemestudios.com npm run build
sudo systemctl daemon-reload && sudo systemctl enable --now morpheme morpheme-celery
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d morphemestudios.com -d www.morphemestudios.com
# Re-arm backups (same as "One-time setup": backup dir + rclone must belong to morpheme)
sudo mkdir -p /srv/backups && sudo chown morpheme:morpheme /srv/backups
sudo -u morpheme rclone config                # re-add remote "b2" as morpheme
sudo chmod +x deploy/backup.sh
sudo crontab -u morpheme /srv/morpheme/backend/deploy/backup.cron
```

### 6. Verify application health
```bash
curl -fsS https://morphemestudios.com/ready        # {"status":"ready","checks":{"database":true,"cache":true}}
curl -fsS https://morphemestudios.com/api/v1/projects | head -c 200   # DB-backed data
journalctl -u morpheme-celery -n 20                # worker up, tasks registered
# Browser: load the site, open a project, submit a test contact form, confirm email arrives.
```

### Recovery objectives
- **RPO:** ≤ 24h (daily backups; tighten the cron for less).
- **RTO:** ~30–60 min on a prepared VPS (most time is `pip install` + `npm build` + certbot).
