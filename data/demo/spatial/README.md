# Sao Paulo spatial demo assets

This MVP bundle uses real road topology and an official municipality boundary. The
checked-in GraphML is the immutable input for normal demo builds; rebuilding does
not contact the network.

## Coverage and limitations

The IBGE file covers municipality code `3550308` (Sao Paulo). The drivable graph
and H3 artifacts cover a fixed central-city bounding box
`(-46.67, -23.585, -46.60, -23.515)`: 6,075 nodes, 11,895 directed arcs and 74
resolution-8 H3 cells. Full-municipality graph generation was intentionally not
checked in because the current edge-to-cell overlay is quadratic and a full-city
source PBF/derived bundle is too large for this MVP repository.

## Rebuild artifacts (offline)

From `backend/`:

```bash
uv run python ../scripts/build_sao_paulo_demo_spatial.py \
  --graphml ../data/demo/spatial/source/sao_paulo_central_drive.graphml \
  --boundary ../data/demo/spatial/source/sao_paulo_ibge_boundary.geojson \
  --output ../data/demo/spatial/artifacts \
  --subset-boundary-output ../data/demo/spatial/source/sao_paulo_central_subset.geojson
```

## Original retrieval

The exact retrieval commands, URLs, licenses, timestamps and SHA-256 values are
recorded in `source/provenance.json`. OpenStreetMap data is © OpenStreetMap
contributors and licensed under ODbL 1.0. The boundary is from the official IBGE
Localidades/Malhas API.

