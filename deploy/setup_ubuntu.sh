#!/usr/bin/env bash
# setup_ubuntu.sh
# Initial server setup for Contabo VPS (Ubuntu 22.04 or 24.04).
# Run this as root.

set -e

echo "=> Updating system packages..."
apt update && apt upgrade -y

echo "=> Installing core dependencies (PostgreSQL, Redis, Nginx, Certbot)..."
apt install -y \
    python3 python3-venv python3-pip python3-dev \
    postgresql postgresql-contrib libpq-dev \
    redis-server \
    nginx \
    certbot python3-certbot-nginx \
    curl git build-essential

echo "=> Installing Node.js (LTS)..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
apt install -y nodejs

echo "=> Creating application user 'morpheme'..."
if ! id -u morpheme > /dev/null 2>&1; then
    useradd -m -s /bin/bash morpheme
    usermod -aG www-data morpheme
fi

echo "=> Creating directory structure..."
mkdir -p /srv/morpheme/backend/media
mkdir -p /srv/morpheme/backend/private-media
mkdir -p /srv/morpheme/backend/staticfiles
mkdir -p /srv/morpheme/frontend/dist

chown -R morpheme:www-data /srv/morpheme
chmod -R 775 /srv/morpheme

echo "=> Configuring PostgreSQL (Interactive)..."
echo "Please set a strong password for the 'morpheme' database user when prompted."
sudo -u postgres psql -c "CREATE DATABASE morpheme;" || true
sudo -u postgres psql -c "CREATE USER morpheme WITH ENCRYPTED PASSWORD 'changeme';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE morpheme TO morpheme;" || true
sudo -u postgres psql -c "ALTER DATABASE morpheme OWNER TO morpheme;" || true

echo "========================================================================="
echo "Setup Complete!"
echo "Next steps:"
echo "1. Switch to user: su - morpheme"
echo "2. Clone your repositories into /srv/morpheme/backend and /srv/morpheme/frontend"
echo "3. Copy .env.example to .env in both directories and fill in the secrets"
echo "4. Copy deploy/nginx-morphemestudios.conf to /etc/nginx/sites-available/ and symlink it to sites-enabled"
echo "5. Run: certbot --nginx -d morphemestudios.com -d www.morphemestudios.com"
echo "6. Run the deploy.sh script!"
echo "========================================================================="
