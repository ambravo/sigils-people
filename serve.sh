#!/bin/sh
# The gallery, locally, exactly as GitHub Pages serves it.
#
#   ./serve.sh            → http://localhost:8000
#   ./serve.sh 9000       → another port
#
# No build step: the page, its two assets and the data are all static and
# reference each other by relative path, so the repository root *is* the site.
set -eu
port="${1:-8000}"
cd "$(dirname "$0")"
test -f people/index.json || {
  echo "people/index.json is missing — this working copy has no cast in it." >&2
  exit 1
}
echo "sigils people → http://localhost:${port}/"
echo "  $(python3 -c 'import json;print(json.load(open("people/index.json"))["count"])') people · $(ls portraits/s | wc -l | tr -d ' ') portraits"
exec python3 -m http.server "$port" --bind 127.0.0.1
