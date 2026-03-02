#!/usr/bin/env bash
# Senryaku build steps — called by julianit.me deploy orchestrator.
# Runs from repo root.
set -euo pipefail

python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -e /home/agent/projects/dojo/dojo-auth -q
./venv/bin/pip install -e . -q
./venv/bin/alembic upgrade head
