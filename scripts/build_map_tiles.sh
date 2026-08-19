#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 CLIPPED_OSM_PBF TILEMAKER_CONFIG OUTPUT_PMTILES" >&2
  exit 2
fi

pbf_path="$(realpath "$1")"
config_path="$(realpath "$2")"
output_path="$(realpath -m "$3")"
[[ -f "$pbf_path" ]] || { echo "missing PBF: $pbf_path" >&2; exit 1; }
[[ -f "$config_path" ]] || { echo "missing tilemaker config: $config_path" >&2; exit 1; }
mkdir -p "$(dirname "$output_path")"

tilemaker_image="ghcr.io/systemed/tilemaker:3.0.0"
pmtiles_image="protomaps/go-pmtiles:v1.28.0"
work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT
cp "$pbf_path" "$work_dir/input.osm.pbf"
cp "$config_path" "$work_dir/config.json"

docker run --rm -v "$work_dir:/data" "$tilemaker_image" \
  --input /data/input.osm.pbf --output /data/sao-paulo.pmtiles --config /data/config.json
docker run --rm -v "$work_dir:/data" "$pmtiles_image" verify /data/sao-paulo.pmtiles
docker run --rm -v "$work_dir:/data" "$pmtiles_image" show /data/sao-paulo.pmtiles --metadata > "$work_dir/metadata.json"

python3 - "$work_dir/metadata.json" <<'PY'
import json
import sys

metadata = json.load(open(sys.argv[1], encoding="utf-8"))
bounds = metadata.get("bounds") or metadata.get("header", {}).get("bounds")
if isinstance(bounds, str):
    bounds = [float(value) for value in bounds.split(",")]
if not bounds or len(bounds) != 4:
    raise SystemExit("PMTiles metadata has no valid bounds")
west, south, east, north = map(float, bounds)
centroid = (-46.6333, -23.5505)
if not (west <= centroid[0] <= east and south <= centroid[1] <= north):
    raise SystemExit("PMTiles bounds do not contain the São Paulo municipal centroid")
region = (-47.2, -24.2, -45.8, -23.0)
if west < region[0] or south < region[1] or east > region[2] or north > region[3]:
    raise SystemExit("PMTiles bounds extend outside the configured São Paulo region")
PY

mv "$work_dir/sao-paulo.pmtiles" "$output_path"
echo "wrote $output_path using $tilemaker_image and $pmtiles_image"
