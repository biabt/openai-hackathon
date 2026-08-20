import json

import pytest

from city_os.demand import load_demand_profile


def test_bundled_cet_profile_is_aggregate_and_privacy_safe() -> None:
    profile = load_demand_profile()
    assert len(profile.points) == 70
    assert profile.coverage["retained_occurrences"] == 352
    assert sum(point.historical_occurrences for point in profile.points) == 352
    assert sum(point.weight for point in profile.points) == pytest.approx(1.0)
    assert all(len(point.hourly_occurrences) == 24 for point in profile.points)

    serialized = json.dumps(profile.layer_records()).lower()
    for prohibited in (
        "cd_identificador",
        "nm_logradouro",
        "nr_logradouro",
        "dt_acidente",
        "ho_acidente",
        "ge_ponto",
    ):
        assert prohibited not in serialized


def test_layer_records_do_not_expose_per_incident_time_or_location() -> None:
    profile = load_demand_profile()
    record = profile.layer_records()[0]
    assert set(record) == {
        "id",
        "node_id",
        "h3_cell",
        "longitude",
        "latitude",
        "historical_occurrences",
        "injured",
        "fatalities",
        "weight",
    }
