#!/bin/sh
# Start the local Laya decision server for Archway's Phase 4 (see README.md in this folder).
cd "$(dirname "$0")/../.." || exit 1
LAYA_HOST=127.0.0.1 LAYA_PORT=8100 LAYA_MODELS=english,typed-decisions LAYA_AUTO_TASK=1 LAYA_LOG_LEVEL=warning \
  exec services/laya/.venv.nosync/bin/laya-serve
