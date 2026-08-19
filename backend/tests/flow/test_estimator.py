import numpy as np
from scipy import sparse

from city_os.flow.estimator import estimate_edge_flows


def test_chain_branch_fits_observations_and_conserves_flow() -> None:
    incidence = np.array([[-1, 0, 0], [1, -1, -1], [0, 1, 0], [0, 0, 1]], dtype=float)
    laplacian = np.array([[2, -1, -1], [-1, 1, 0], [-1, 0, 1]], dtype=float)
    observation = np.array([[1, 0, 0], [0, 1, 0]], dtype=float)
    boundary = np.array([-10, 0, 6, 4], dtype=float)

    flow = estimate_edge_flows(
        incidence,
        laplacian,
        observation,
        [10, 6],
        [9, 5, 4],
        boundary=boundary,
        lambda_spatial=0.01,
        lambda_temporal=0.01,
        lambda_conservation=20,
    )

    assert np.all(flow >= 0)
    np.testing.assert_allclose(observation @ flow, [10, 6], atol=0.01)
    np.testing.assert_allclose(incidence @ flow, boundary, atol=0.01)


def test_no_observations_uses_temporal_prior() -> None:
    flow = estimate_edge_flows(
        sparse.csr_matrix((0, 2)),
        sparse.csr_matrix((2, 2)),
        sparse.csr_matrix((0, 2)),
        [],
        [3, -1],
        lambda_spatial=0,
        lambda_temporal=1,
        lambda_conservation=0,
    )
    np.testing.assert_allclose(flow, [3, 0], atol=1e-7)


def test_low_confidence_observation_has_less_influence() -> None:
    flow = estimate_edge_flows(
        np.zeros((0, 1)),
        np.zeros((1, 1)),
        [[1], [1]],
        [20, 100],
        [0],
        weights=[1.0, 0.05],
        lambda_spatial=0,
        lambda_temporal=0,
        lambda_conservation=0,
    )
    assert abs(flow[0] - 20) < abs(flow[0] - 100)


def test_disconnected_sparse_problem_is_deterministic() -> None:
    incidence = sparse.csr_matrix([[-1, 0], [1, 0], [0, -1], [0, 1]])
    laplacian = sparse.csr_matrix((2, 2))
    observation = sparse.csr_matrix([[1, 0]])
    kwargs = dict(
        weights=[0.8],
        lambda_spatial=0.5,
        lambda_temporal=1,
        lambda_conservation=0,
    )
    first = estimate_edge_flows(incidence, laplacian, observation, [12], [10, 7], **kwargs)
    second = estimate_edge_flows(incidence, laplacian, observation, [12], [10, 7], **kwargs)
    np.testing.assert_array_equal(first, second)
    assert first[1] == 7
