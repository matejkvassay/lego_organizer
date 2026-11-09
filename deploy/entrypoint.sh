#!/bin/sh
# Container entrypoint.
#  - LITESTREAM_BUCKET set (Cloud Run): restore the database from the bucket if there is no local copy, then run the
#    app as a child of `litestream replicate`, which streams every change back to the bucket.
#  - LITESTREAM_BUCKET unset (local docker compose): just run the app.
# Behind Cloud Run set FORWARDED_ALLOW_IPS='*' (uvicorn reads it); the default (127.0.0.1) ignores X-Forwarded-*
# headers from anyone else, which is what you want anywhere the port is reachable directly.
set -eu

# A command was given (`docker compose run app python -m app.seed`): run exactly that, not the web server.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

APP="uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

if [ -n "${LITESTREAM_BUCKET:-}" ]; then
  litestream restore -config /etc/litestream.yml -if-db-not-exists -if-replica-exists /data/lego.db
  exec litestream replicate -config /etc/litestream.yml -exec "$APP"
fi
exec $APP
