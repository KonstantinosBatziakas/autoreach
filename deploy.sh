#!/bin/bash
# AutoReach one-line deploy script
# Run this on the server every time you push new code:  bash deploy.sh

set -e

APP_DIR="/home/ubuntu/autoreach"

echo "==> Pulling latest code..."
cd "$APP_DIR"
git pull

echo "==> Installing any new dependencies..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

echo "==> Restarting app..."
sudo systemctl restart autoreach
sudo systemctl status autoreach --no-pager

echo "==> Done! AutoReach is live."
