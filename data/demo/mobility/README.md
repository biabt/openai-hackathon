# Real mobility observation sample

This directory contains a compact, offline-safe extract of real 2025 automatic
traffic sensor (SAT) counts published by ARTESP. The sample covers SP-280 at
kilometre 14 for 1–7 January 2025 and preserves each published direction and
mainline/marginal carriageway observation. `vehicle_total` is the sum of the
three source vehicle classes.

The source contains aggregate daily vehicle counts only: no image, plate,
person, device identifier, or individual trajectory is retained. The sample is
therefore suitable as a privacy-safe demo observation. It is not a live feed
and must not be represented as current traffic.

## Rebuild

From the repository root, with network access:

```bash
python3 scripts/build_demo_mobility_sample.py
sha256sum data/demo/mobility/artesp_sp280_km14_2025-01-01_07.csv
```

The script uses the official CKAN datastore API, selects the pinned road,
kilometre, and date interval, renames Portuguese fields, and computes the total.
It deliberately does not download or store the 35 MB source file.

## Limitations

- ARTESP describes this dataset as counts from sensors on state concession
  roads. It is a real São Paulo metropolitan road observation, not a CET city
  camera feed or SPTrans vehicle-position observation.
- The published table provides a route kilometre reference, not coordinates.
  No coordinate has been inferred or bundled, so map placement must use a
  separately sourced road linear reference.
- Daily totals are appropriate for coarse calibration or demo context only;
  they cannot provide within-day congestion or directional flow timing.
- The source can be revised. The bundled CSV and checksum are the reproducible
  offline snapshot; rebuilding later can legitimately produce a new checksum.

See `provenance.json` for source, license, timestamps, and integrity metadata.
