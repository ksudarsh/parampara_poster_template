#!/usr/bin/env bash
set -euo pipefail

cd /app

# Optional overrides: user can mount a folder at /overrides to replace defaults
if [ -d /overrides ]; then
  echo "Applying overrides from /overrides ..."
  cp -rf /overrides/* /app/ || true
fi

python generate_parampara_poster.py --output-dir /out
