#!/bin/zsh
set -euo pipefail

cd /Users/ethanjmathew/macro-tracker

export FLASK_DEBUG=0
export HOST=127.0.0.1
export PORT=5001
export DATABASE_PATH=/Users/ethanjmathew/macro-tracker/macro_tracker.db

exec /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 app.py
