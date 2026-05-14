#!/bin/zsh
set -euo pipefail

cd /Users/ethanjmathew/macro-tracker

exec /Users/ethanjmathew/macro-tracker/bin/cloudflared tunnel \
  --url http://127.0.0.1:5001 \
  --no-autoupdate
