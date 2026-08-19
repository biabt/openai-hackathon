from city_os.contracts.api import ScenarioType
from city_os.scenarios import parse_scenario_card


def test_parses_builtin_flood_language_offline_deterministically() -> None:
    text = "Flooding in Aricanduva from 17:30 to 19:00, edges 12345 and edge 12346 blocked"
    first = parse_scenario_card(text)
    assert first == parse_scenario_card(text)
    assert first.type is ScenarioType.FLOOD
    assert first.starts_at == "17:30"
    assert first.ends_at == "19:00"
    assert first.demand_multiplier == 1.25
    assert first.blocked_edges == (12345, 12346)


def test_recognizes_event_and_road_closure() -> None:
    event = parse_scenario_card("Stadium concert from 18:00 to 21:00")
    closure = parse_scenario_card("Avenue closed 09:00 to 10:30, edge 77 blocked")
    assert event.type is ScenarioType.EVENT
    assert event.demand_multiplier == 1.5
    assert closure.type is ScenarioType.TRANSIT_DISRUPTION
    assert closure.blocked_edges == (77,)


def test_malformed_or_failed_model_uses_lower_confidence_fallback() -> None:
    malformed = parse_scenario_card("Flood 17:30 to 19:00", lambda _text: "not-json")

    def timeout(_text: str) -> object:
        raise TimeoutError

    timed_out = parse_scenario_card("Flood 17:30 to 19:00", timeout)
    assert malformed == timed_out
    assert malformed.confidence == 0.6


def test_valid_structured_model_output_is_validated() -> None:
    fallback = parse_scenario_card("Stadium event 18:00 to 21:00")
    payload = fallback.model_dump(mode="json") | {"confidence": 0.95}
    assert parse_scenario_card("anything", lambda _text: payload).confidence == 0.95
