#!/bin/sh
# The PUBLIC copy of Archway's backend, run on this Mac for the deployed site (https://archway-beta-five.vercel.app).
#
#   sh deploy/mac/start-public.sh
#
# What makes it different from the local development backend (port 8000):
#   - its own database (backend/data-public.nosync): the public site's accounts and projects are kept apart
#   - HTTPS rules: Secure "__Host-" cookies, HSTS, the API docs switched off
#   - only the deployed site may send changes (ALLOWED_ORIGINS); localhost is NOT allowed
#   - it listens on 127.0.0.1:8200 only: the internet reaches it solely through Tailscale Funnel (HTTPS)
#   - the keys stay where they are, in backend/.env: nothing secret is copied anywhere
# `caffeinate -i` keeps the Mac from going to sleep while this runs (closing the lid can still sleep it).
# Laya must be running too (backend/services/laya/run.sh).
set -eu
cd "$(dirname "$0")/../../backend"

export ARCHWAY_DATA_DIR="$PWD/data-public.nosync"
export AUTH_ENABLED=true
export COOKIE_SECURE=true
export ALLOWED_ORIGINS="https://archway-beta-five.vercel.app,https://archway-tarun-sreenivas-projects.vercel.app"
export LOG_LEVEL=INFO

# --proxy-headers / --forwarded-allow-ips '*': the visitor's real address arrives in X-Forwarded-For from Vercel and
# Tailscale. Safe to trust because this port is bound to 127.0.0.1: only Tailscale on this Mac can reach it.
exec caffeinate -i .venv/bin/python -m uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8200 --proxy-headers --forwarded-allow-ips '*' --timeout-graceful-shutdown 2
