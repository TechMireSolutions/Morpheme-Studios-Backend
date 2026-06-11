#!/usr/bin/env bash
#
# Off-box backup for Morpheme Studios (DB + media) — survives total VPS loss.
#
# Strategy: dump Postgres + tar the media trees locally, then push to an
# off-box object store via rclone (Backblaze B2 by default — cheapest for a
# small site; works unchanged with S3/Wasabi/any rclone remote). Local + remote
# copies are pruned by age (retention policy below).
#
# One-time setup on the VPS:
#   sudo apt install -y rclone postgresql-client
#   rclone config         # create a remote named "b2" -> Backblaze B2 bucket
#   chmod +x deploy/backup.sh
#   # add to crontab (root or morpheme):  see deploy/backup.cron
#
# Restore: see docs/09-backup-and-restore.md
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/morpheme/backend}"
BACKUP_DIR="${BACKUP_DIR:-/srv/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-b2:morpheme-backups}"   # rclone remote:bucket
LOCAL_RETENTION_DAYS="${LOCAL_RETENTION_DAYS:-7}"
REMOTE_RETENTION_DAYS="${REMOTE_RETENTION_DAYS:-30}"
STAMP="$(date +%F_%H%M%S)"

# $BACKUP_DIR must be pre-created and owned by the user this script runs as
# (see docs) — `morpheme` cannot mkdir under root-owned /srv.
mkdir -p "$BACKUP_DIR" 2>/dev/null || true
if [ ! -w "$BACKUP_DIR" ]; then
  echo "[backup] ERROR: $BACKUP_DIR is missing or not writable. Create it once:" >&2
  echo "          sudo mkdir -p $BACKUP_DIR && sudo chown \$(id -un):\$(id -gn) $BACKUP_DIR" >&2
  exit 1
fi

# Read ONLY DATABASE_URL from the app's .env, literally — do NOT `source` the
# file: values can contain spaces, <, >, $, !, () etc. which the shell would
# mis-parse or expand and corrupt the connection string.
DATABASE_URL="$(grep -E '^[[:space:]]*DATABASE_URL=' "$APP_DIR/.env" | head -n1 | cut -d= -f2-)"
if [ -z "${DATABASE_URL:-}" ]; then
  echo "[backup] ERROR: DATABASE_URL not found in $APP_DIR/.env" >&2
  exit 1
fi

DB_FILE="$BACKUP_DIR/db-$STAMP.sql.gz"
MEDIA_FILE="$BACKUP_DIR/media-$STAMP.tar.gz"

echo "[backup] dumping database…"
pg_dump "$DATABASE_URL" | gzip -9 > "$DB_FILE"

echo "[backup] archiving media + private-media…"
tar -czf "$MEDIA_FILE" -C "$APP_DIR" media private-media

echo "[backup] pushing off-box to $RCLONE_REMOTE…"
rclone copy "$DB_FILE"    "$RCLONE_REMOTE/db/"    --no-traverse
rclone copy "$MEDIA_FILE" "$RCLONE_REMOTE/media/" --no-traverse

echo "[backup] pruning local (> ${LOCAL_RETENTION_DAYS}d) and remote (> ${REMOTE_RETENTION_DAYS}d)…"
find "$BACKUP_DIR" -name 'db-*.sql.gz'    -mtime +"$LOCAL_RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name 'media-*.tar.gz' -mtime +"$LOCAL_RETENTION_DAYS" -delete
rclone delete --min-age "${REMOTE_RETENTION_DAYS}d" "$RCLONE_REMOTE/db/"    || true
rclone delete --min-age "${REMOTE_RETENTION_DAYS}d" "$RCLONE_REMOTE/media/" || true

echo "[backup] done: $(basename "$DB_FILE"), $(basename "$MEDIA_FILE")"
