# Privacy and data handling

CityOS is a decision-support prototype based on regional, aggregate, and synthetic information.
It estimates operational pressure; it does not identify people or predict an individual's medical
emergency.

## Data classes

| Class | Stored in this repository | Retention and purpose |
|---|---|---|
| Road topology | Nodes, directed edges, H3 membership, local map assets | Bundled operational geography |
| Camera-derived observations | Object class, direction, count, confidence, edge, five-minute bucket | Aggregate flow estimation only |
| Derived mobility | Edge flow/speed/travel time/occupancy and H3 density | Reproducible simulation input |
| Scenario observations | Typed flood, event, and road-block impacts | Synthetic operational rehearsal |
| Emergency activity | Seeded synthetic calls, ambulance states, and metrics | Fair policy comparison |

The acceptance fixture is repository-authored synthetic data. Any source described as real refers
to authorized provenance or public geography, not to a live personal-data feed.

## Prohibited collection and persistence

The demo must not contain or persist:

- images or video frames;
- faces, face embeddings, or facial-recognition results;
- license plates or other direct identifiers;
- MAC addresses or device identifiers;
- cross-camera identities or persistent track identifiers;
- camera URLs, passwords, API keys, tokens, or other credentials;
- actual patient, incident, ambulance, or SAMU operational records.

Short-lived in-memory tracking may prevent double counting inside one processing window. Track IDs
must be discarded before an observation is written; only aggregate directional counts leave the
vision boundary.

## Processing boundaries

Camera processing is local. The offline demo does not contact camera systems, SPTrans, remote map
servers, telemetry services, or model providers. Optional source adapters are preparation tools,
are not part of the judged runtime, and take credentials only from environment variables.

Every artifact must carry provenance, schema version, and checksum information. Observed,
inferred, synthetic, and computed values remain distinguishable in the product and documentation.
Confidence represents data quality; it must not be presented as certainty about an individual.

## Release audit

Before release:

1. Run `make artifacts` and require all bundled checksums to match.
2. Inspect image/video extensions and unusually large files under `data/`.
3. Inspect Parquet and JSON column names for identifier, face, plate, device, MAC, credential, URL,
   token, or tracking fields.
4. Search tracked files for secrets with the team's approved secret scanner.
5. Run the demo without networking and verify browser requests remain on localhost.
6. Record the reviewer, commit SHA, date, and findings below.

| Reviewer | Commit | Date | Finding |
|---|---|---|---|
| — | — | — | Audit not yet recorded |

If prohibited data is found, stop the release, remove it from artifacts and history using the
team's incident procedure, rotate any exposed credential, rebuild manifests, and rerun the audit.
