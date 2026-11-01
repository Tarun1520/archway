#!/bin/sh
# Ship Archway to the server and (re)start it.  From the repository root:
#   sh deploy/deploy.sh ubuntu@<server-ip> <domain>
# With Laya (needs a server with 4 GB):  COMPOSE_PROFILES=laya sh deploy/deploy.sh ...   Without it, Laya is stopped.
# <domain> is the server's HTTPS name, e.g. 152-67-1-2.sslip.io (sslip.io maps that name to the IP, for free).
set -eu
TARGET="$1"
DOMAIN="$2"
KEY="${ARCHWAY_SSH_KEY:-$HOME/.ssh/archway_oracle}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new"

echo "== Building the frontend"
npm --prefix frontend run build >/dev/null
rm -rf deploy/site && cp -R frontend/dist deploy/site
# The raw source clips in public/ are not used by the app; leave them out of the server copy.
rm -f "deploy/site/space transition.mp4" deploy/site/gemini_generated_video_*.mp4 deploy/site/Final_transition.mp4

echo "== Copying the code (never .env, databases or virtual environments)"
rsync -az --delete -e "$SSH" \
  --exclude '.env' --exclude '.env.*' --exclude '*.db*' --exclude 'data.nosync' --exclude '.venv*' \
  --exclude '__pycache__' --exclude 'tests' --exclude 'learning' --exclude 'services' \
  backend/app backend/fixtures backend/scripts backend/requirements.txt "$TARGET:archway/backend/"
rsync -az --delete -e "$SSH" --exclude '*.env' deploy/ "$TARGET:archway/deploy/"
rsync -az -e "$SSH" .dockerignore "$TARGET:archway/"

echo "== Starting it"
$SSH "$TARGET" "cd archway/deploy && test -f backend.env || { echo 'backend.env is missing on the server (see deploy/README.md)'; exit 1; }; \
  if [ '${COMPOSE_PROFILES:-}' = laya ]; then export COMPOSE_PROFILES=laya; else docker compose --profile laya rm -sf laya >/dev/null 2>&1 || true; fi; \
  ARCHWAY_DOMAIN='$DOMAIN' docker compose up -d --build && docker compose ps"

echo "== Done: https://$DOMAIN"
