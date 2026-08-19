"""Scenario-card structured parsing with an always-available offline fallback."""

from __future__ import annotations

import json
from typing import Protocol

from city_os.contracts.api import ScenarioObservation
from city_os.scenarios.fallback import fallback_scenario


class ScenarioClient(Protocol):
    def __call__(self, text: str) -> object: ...


def _invoke(client: object, text: str) -> object:
    if callable(client):
        return client(text)
    parse = getattr(client, "parse", None)
    if callable(parse):
        return parse(text)
    raise TypeError("llm_client must be callable or expose parse(text)")


def parse_scenario_card(
    text: str, llm_client: ScenarioClient | object | None = None
) -> ScenarioObservation:
    """Parse a card, falling back deterministically after any client failure.

    The return type intentionally remains the frozen public observation contract.
    API code may infer fallback use by comparing confidence or handling its client error.
    """
    if not text.strip():
        raise ValueError("scenario text must not be blank")
    if llm_client is None:
        return fallback_scenario(text)
    try:
        payload = _invoke(llm_client, text)
        if isinstance(payload, ScenarioObservation):
            return payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        return ScenarioObservation.model_validate(payload)
    except Exception:  # client timeouts and malformed structured output share the safe path
        return fallback_scenario(text)
