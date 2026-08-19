#!/usr/bin/env python3
"""Exercise the complete local demo with seed 42 and validate its stream."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any

import websockets

from demo_start import API_PORT, WEB_PORT, start_services, stop, wait_for


def request_json(url: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            value = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise RuntimeError(f"request failed at {url}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object at {url}")
    return value


async def collect_frames(simulation_id: str) -> list[dict[str, Any]]:
    url = f"ws://127.0.0.1:{API_PORT}/api/simulations/{simulation_id}/stream"
    frames: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(60), websockets.connect(url) as socket:
            async for message in socket:
                value = json.loads(message)
                if not isinstance(value, dict):
                    raise RuntimeError("simulation stream emitted a non-object message")
                frames.append(value)
                counts = defaultdict(int)
                for frame in frames:
                    counts[str(frame.get("policy"))] += 1
                if counts["baseline"] >= 72 and counts["optimized"] >= 72:
                    return frames
    except TimeoutError as error:
        raise RuntimeError("timed out waiting for 72 frames per policy") from error
    raise RuntimeError("simulation stream closed before 72 frames per policy")


def validate_frames(frames: list[dict[str, Any]]) -> None:
    by_policy: dict[str, list[int]] = {"baseline": [], "optimized": []}
    for frame in frames:
        policy = frame.get("policy")
        minute = frame.get("minute")
        if policy not in by_policy or not isinstance(minute, int):
            raise RuntimeError("stream frame has an invalid policy or minute")
        if minute % 5 != 0 or not 0 <= minute <= 360:
            raise RuntimeError(f"stream minute is not a valid five-minute bucket: {minute}")
        by_policy[policy].append(minute)
    for policy, minutes in by_policy.items():
        if len(minutes) < 72:
            raise RuntimeError(f"{policy} emitted only {len(minutes)} frames")
        if minutes != sorted(minutes) or len(minutes) != len(set(minutes)):
            raise RuntimeError(f"{policy} frame minutes are duplicated or out of order")


def main() -> None:
    processes = start_services()
    started = time.monotonic()
    try:
        wait_for(f"http://127.0.0.1:{API_PORT}/healthz", processes[0])
        wait_for(f"http://127.0.0.1:{WEB_PORT}", processes[1])
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("a newly started demo service exited during readiness checks")
        bootstrap = request_json(f"http://127.0.0.1:{API_PORT}/api/bootstrap")
        scenarios = bootstrap.get("scenarios")
        fleet = bootstrap.get("fleet_size_bounds")
        if not isinstance(scenarios, list) or not scenarios or not isinstance(fleet, dict):
            raise RuntimeError("bootstrap has no scenario or fleet bounds")
        scenario_id = scenarios[0].get("id") if isinstance(scenarios[0], dict) else None
        fleet_size = fleet.get("default")
        if not isinstance(scenario_id, str) or not isinstance(fleet_size, int):
            raise RuntimeError("bootstrap scenario ID or default fleet size is invalid")
        created = request_json(
            f"http://127.0.0.1:{API_PORT}/api/simulations",
            payload={"scenario_id": scenario_id, "fleet_size": fleet_size, "seed": 42},
        )
        simulation_id = created.get("simulation_id")
        if not isinstance(simulation_id, str) or not simulation_id:
            raise RuntimeError("simulation creation returned no simulation_id")
        frames = asyncio.run(collect_frames(simulation_id))
        validate_frames(frames)
        elapsed = time.monotonic() - started
        print(
            "smoke passed: seed 42, "
            f"{len(frames)} validated five-minute frames, {elapsed:.2f}s wall time"
        )
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"demo smoke failed: {error}") from error
