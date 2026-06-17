#!/bin/sh
# Write the runtime API base from the API_BASE env var (if provided).
if [ -n "$API_BASE" ]; then
  echo "window.__API_BASE__ = \"$API_BASE\";" > /usr/share/nginx/html/config.js
  echo "[entrypoint] API_BASE set to $API_BASE"
fi
