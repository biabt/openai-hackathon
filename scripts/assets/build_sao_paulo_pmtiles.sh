#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_url="https://build.protomaps.com/20231023.pmtiles"
boundary="$repo_root/data/demo/spatial/source/sao_paulo_ibge_boundary.geojson"
output="$repo_root/data/demo/map/sao-paulo.pmtiles"

command -v pmtiles >/dev/null || {
  echo "pmtiles CLI is required (pinned/tested: v1.31.2; macOS: brew install pmtiles)" >&2
  exit 1
}
[[ -f "$boundary" ]] || { echo "missing municipal boundary: $boundary" >&2; exit 1; }
mkdir -p "$(dirname "$output")"

temporary_output="$(mktemp "${TMPDIR:-/tmp}/sao-paulo.XXXXXX.pmtiles")"
trap 'rm -f -- "$temporary_output"' EXIT
pmtiles extract "$source_url" "$temporary_output" \
  --region "$boundary" --minzoom 0 --maxzoom 14 --download-threads 4
pmtiles verify "$temporary_output"

bounds="$(pmtiles show "$temporary_output" | sed -n 's/^bounds: (long: \([^,]*\), lat: \([^)]*\)) (long: \([^,]*\), lat: \([^)]*\)).*/\1 \2 \3 \4/p')"
python3 - $bounds <<'PY'
import sys

west, south, east, north = map(float, sys.argv[1:])
lon, lat = -46.6333, -23.5505
if not (west <= lon <= east and south <= lat <= north):
    raise SystemExit("archive bounds do not contain the São Paulo municipal centroid")
PY

mv "$temporary_output" "$output"
shasum -a 256 "$output"
echo "wrote $output"
