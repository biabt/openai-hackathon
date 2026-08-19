# CityOS demo and release runbook

This runbook is the evidence checklist for the offline release candidate. Do not replace an
unchecked item with an assumed result: record the machine, commit, command, duration, and exact
summary produced by the command.

## Prepare once while dependencies are available

Requirements are Python 3.12, `uv`, Node.js, npm, and GNU Make. On Windows, use Git Bash or WSL
for `make`; the underlying `scripts/demo_*.py` entry points also run directly in PowerShell.

```sh
make install
make artifacts
```

`make install` uses the committed `backend/uv.lock` and `frontend/package-lock.json`.
`make artifacts` performs no download: it checks the schema, contract fixtures, artifact files,
and every SHA-256 listed by the bundled flow manifest.

## Automated verification

Run from a clean checkout:

```sh
make test
make smoke
```

`make smoke` owns the API and portal child processes, waits for `/healthz` and the portal, submits
seed `42`, reads the WebSocket, requires 72 five-minute frames for both `baseline` and `optimized`,
and stops both services even on failure.

### Release evidence

No complete release run has been recorded yet. Paste exact output only after running it:

| Machine | Commit | `make test` exact summary | `make smoke` result | Six-hour duration |
|---|---|---|---|---|
| Developer A | — | Not run | Not run | Not measured |
| Developer B | — | Not run | Not run | Not measured |
| Developer C | — | Not run | Not run | Not measured |

The release gate is complete only when the three machines produce an identical call tape and
metrics equal within absolute tolerance `1e-6`, and the slowest six-hour run takes no more than
60 seconds.

## Offline rehearsal

Disconnect networking after installation, then run:

```sh
make demo
```

Open `http://127.0.0.1:3000`. In browser developer tools, confirm that every request targets
localhost and that no external font, tile, telemetry, or API request occurs.

Check the following behaviors:

- roads, local basemap, aggregate camera flow, H3 density, and ambulances render;
- flood, event, and blocked-road cards change demand or travel cost and trigger reoptimization;
- changing fleet size changes the submitted request, with the same size used by both policies;
- baseline and optimized runs use the same seed `42` call IDs;
- the map stays responsive through minute 360 and the two terminal p90 values update.

## Five-minute narrative

1. **Before:** establish the static baseline and its p90 response time.
2. **Sensor observation:** show directional aggregate counts and their confidence/provenance.
3. **Flow and density:** follow those counts into inferred network flow and H3 activity.
4. **Allocation:** activate a scenario and show dynamic ambulance repositioning.
5. **After:** compare optimized p90 against the baseline under the same seeded calls.

## Final hygiene gate

```sh
rg -n "TODO|FIXME|placeholder|lorem|example\.com" backend frontend scripts README.md
```

Review every match; a test that intentionally asserts rejection may be legitimate, while visible
copy, silent fallback behavior, or unfinished implementation is not. Then apply the privacy audit
in [privacy-and-data.md](privacy-and-data.md).

To stop an interactive demo, press `Ctrl+C`; the launcher terminates both child services.
