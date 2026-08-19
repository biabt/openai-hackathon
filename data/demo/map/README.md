# Offline São Paulo basemap

`sao-paulo.pmtiles` is a real OSM-derived vector basemap clipped to the São
Paulo municipal boundary. It contains 563 tiles through zoom 14 (18 MiB), so
the demo needs no map network access at runtime. `style.json` is a minimal dark
MapLibre style; applications must register the PMTiles protocol before loading
it.

## Rebuild and validate

Install the PMTiles CLI v1.31.2, then run from the repository root:

```sh
scripts/assets/build_sao_paulo_pmtiles.sh
pmtiles verify data/demo/map/sao-paulo.pmtiles
pmtiles show data/demo/map/sao-paulo.pmtiles
shasum -a 256 data/demo/map/sao-paulo.pmtiles
```

The build script uses the pinned Protomaps daily planet archive documented in
`metadata.json`, clips it with the checked-in IBGE municipal boundary, verifies
the archive, and rejects bounds that omit São Paulo's municipal centroid.

## Attribution and licenses

Map data is © OpenStreetMap contributors and available under the Open Database
License (ODbL): https://www.openstreetmap.org/copyright. Low-zoom Natural Earth
content in the Protomaps basemap is public domain. The source attribution must
remain visible in the map UI. Protomaps build details and schema are documented
at https://docs.protomaps.com/basemaps/downloads.
