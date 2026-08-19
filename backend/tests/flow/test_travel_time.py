import numpy as np
import pytest

from city_os.flow.travel_time import bpr_travel_seconds


def test_bpr_equals_free_flow_at_zero_and_increases_monotonically() -> None:
    result = bpr_travel_seconds(60.0, np.array([0.0, 500.0, 1_000.0]), 1_000.0)
    assert result[0] == 60.0
    assert np.all(np.diff(result) > 0)


def test_bpr_remains_finite_under_overload() -> None:
    result = bpr_travel_seconds(60.0, 100_000.0, 1_000.0)
    assert np.isfinite(result)
    assert result > 60.0


def test_blocked_edges_have_explicit_infinite_sentinel() -> None:
    result = bpr_travel_seconds([10.0, 20.0], [1.0, 1.0], [100.0, 100.0], blocked=[False, True])
    assert np.isfinite(result[0])
    assert result[1] == np.inf


@pytest.mark.parametrize("capacity", [0, -1, np.inf])
def test_invalid_capacity_is_rejected(capacity: float) -> None:
    with pytest.raises(ValueError, match="capacity"):
        bpr_travel_seconds(10, 1, capacity)
