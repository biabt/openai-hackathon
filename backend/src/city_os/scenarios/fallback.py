"""Offline scenario-card rules used when structured model output is unavailable."""

from __future__ import annotations

import hashlib
import re
import unicodedata

from city_os.contracts.api import ScenarioObservation, ScenarioSource, ScenarioType

DEFAULT_H3 = "88a8100c05fffff"


def _plain(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(character)
    )


def _times(text: str) -> tuple[str, str]:
    found = re.findall(r"(?<!\d)([01]?\d|2[0-3])(?::([0-5]\d))?(?!\d)", text)
    values = [f"{int(hour):02d}:{minute or '00'}" for hour, minute in found]
    if len(values) >= 2 and values[0] < values[1]:
        return values[0], values[1]
    if len(values) == 1:
        hour, minute = map(int, values[0].split(":"))
        end_minutes = min(hour * 60 + minute + 90, 23 * 60 + 59)
        return values[0], f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
    return "17:30", "19:00"


def fallback_scenario(text: str) -> ScenarioObservation:
    """Convert common demo language to a stable, conservative observation."""
    normalized = _plain(text)
    starts_at, ends_at = _times(normalized)
    edge_ids = tuple(
        sorted(
            {
                int(value)
                for value in re.findall(r"(?:edges?|arestas?)\s*#?(\d+)", normalized)
            }
        )
    )
    if edge_ids and ("blocked" in normalized or "bloque" in normalized):
        tail = normalized[normalized.find(str(edge_ids[0])) :]
        trailing_ids = {int(value) for value in re.findall(r"\d{2,}", tail)}
        edge_ids = tuple(sorted(set(edge_ids) | trailing_ids))
    if any(word in normalized for word in ("flood", "flooding", "alag", "enchent")):
        kind = ScenarioType.FLOOD
        demand_multiplier, travel_penalty = 1.25, 2.0
        label = "flood"
    elif any(
        word in normalized
        for word in ("stadium", "estadio", "allianz", "concert", "show", "event")
    ):
        kind = ScenarioType.EVENT
        demand_multiplier, travel_penalty = 1.5, 1.25
        label = "event"
    elif any(word in normalized for word in ("blocked", "closed", "closure", "bloque", "interdit")):
        kind = ScenarioType.TRANSIT_DISRUPTION
        demand_multiplier, travel_penalty = 1.0, 3.0
        label = "road-block"
    else:
        kind = ScenarioType.TRANSIT_DISRUPTION
        demand_multiplier, travel_penalty = 1.0, 1.5
        label = "disruption"
    digest = hashlib.sha256(normalized.strip().encode()).hexdigest()[:10]
    return ScenarioObservation(
        id=f"{label}-{starts_at.replace(':', '')}-{digest}",
        type=kind,
        starts_at=starts_at,
        ends_at=ends_at,
        affected_h3=(DEFAULT_H3,),
        demand_multiplier=float(demand_multiplier),
        travel_penalty=float(travel_penalty),
        blocked_edges=edge_ids,
        confidence=0.6,
        source=ScenarioSource.SIMULATED,
    )
