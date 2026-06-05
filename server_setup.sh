#!/bin/bash
# AutoReach Server Setup Script
# Run this on a fresh Oracle Cloud Ubuntu 22.04 VM as the ubuntu user
# Usage: bash server_setup.sh

set -e  # stop on any error

DOMAIN="autoreach.dev"
APP_DIR="/home/ubuntu/autoreach"
REPO="https://github.com/KonstantinosBatziakas/autoreach"

echo "==> [1/9] Updating system packages..."
sudo apt update && sudo apt upgrade -y

echo "==> [2/9] Installing dependencies..."
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git ufw

echo "==> [3/9] Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

echo "==> [4/9] Cloning AutoReach repo..."
if [ -d "$APP_DIR" ]; then
  echo "    Directory exists, pulling latest..."
  cd "$APP_DIR" && git pull
else
  git clone "$REPO" "$APP_DIR"
  cd "$APP_DIR"
fi

echo "==> [5/9] Setting up Python virtual environment..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "==> [6/9] Creating data directory..."
sudo mkdir -p /data
sudo chown ubuntu:ubuntu /data

echo "==> [7/9] Writing systemd service..."
sudo tee /etc/systemd/system/autoreach.service > /dev/null <<EOF
[Unit]
Description=AutoReach Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
Environment="DATA_DIR=/data"
EnvironmentFile=/etc/autoreach.env
ExecStart=$APP_DIR/venv/bin/gunicorn app:app --bind 127.0.0.1:8080 --workers 2 --timeout 60
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> [8/9] Writing nginx config..."
sudo tee /etc/nginx/sites-available/autoreach > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60;
    }

    location /static {
        alias $APP_DIR/static;
        expires 30d;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/autoreach /etc/nginx/sites-enabled/autoreach
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "==> [9/9] Enabling and starting AutoReach service..."
sudo systemctl daemon-reload
sudo systemctl enable autoreach

echo ""
echo "============================================================"
echo "  Setup complete! Two things left to do manually:"
echo ""
echo "  1. Create /etc/autoreach.env with your secrets:"
echo "     sudo nano /etc/autoreach.env"
echo ""
echo "  2. Run certbot to get SSL:"
echo "     sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "  Then start the app:"
echo "     sudo systemctl start autoreach"
echo "     sudo systemctl status autoreach"
echo "============================================================"
