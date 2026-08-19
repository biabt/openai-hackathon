"""Graph-regularized inference of directional edge flows."""

from __future__ import annotations

from typing import Any

import numpy as np


def _as_vector(value: Any, length: int, name: str, default: float = 0.0) -> np.ndarray:
    if value is None:
        result = np.full(length, default, dtype=float)
    else:
        result = np.asarray(value, dtype=float).reshape(-1)
    if result.shape != (length,):
        raise ValueError(f"{name} must contain {length} values")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _laplacian_factor(matrix: Any, size: int, sparse: Any) -> Any:
    """Return R such that R.T @ R approximates a graph Laplacian exactly.

    The common sparse graph-Laplacian case is converted to a weighted edge
    incidence matrix without densifying. A generic symmetric PSD matrix uses a
    deterministic eigendecomposition, which is useful for small custom priors.
    """
    lap = sparse.csr_matrix(matrix, dtype=float)
    if lap.shape != (size, size):
        raise ValueError(f"L_E must have shape ({size}, {size})")
    if lap.nnz and not np.all(np.isfinite(lap.data)):
        raise ValueError("L_E must contain only finite values")
    difference = lap - lap.T
    if difference.nnz and np.max(np.abs(difference.data)) > 1e-10:
        raise ValueError("L_E must be symmetric")

    upper = sparse.triu(lap, k=1).tocoo()
    if upper.nnz == 0 or np.all(upper.data <= 1e-12):
        weights = np.maximum(-upper.data, 0.0)
        keep = weights > 0.0
        rows = np.arange(int(np.count_nonzero(keep)))
        columns_i = upper.row[keep]
        columns_j = upper.col[keep]
        roots = np.sqrt(weights[keep])
        incidence = sparse.coo_matrix(
            (
                np.concatenate((roots, -roots)),
                (np.concatenate((rows, rows)), np.concatenate((columns_i, columns_j))),
            ),
            shape=(len(rows), size),
        ).tocsr()
        represented_diagonal = np.asarray(incidence.power(2).sum(axis=0)).ravel()
        remainder = lap.diagonal() - represented_diagonal
        if np.min(remainder, initial=0.0) < -1e-8:
            raise ValueError("L_E is not a valid positive-semidefinite Laplacian")
        indices = np.flatnonzero(remainder > 1e-12)
        if len(indices):
            diagonal_rows = sparse.coo_matrix(
                (np.sqrt(remainder[indices]), (np.arange(len(indices)), indices)),
                shape=(len(indices), size),
            ).tocsr()
            incidence = sparse.vstack((incidence, diagonal_rows), format="csr")
        return incidence

    dense = lap.toarray()
    eigenvalues, eigenvectors = np.linalg.eigh((dense + dense.T) * 0.5)
    tolerance = max(1.0, float(np.max(np.abs(eigenvalues), initial=0.0))) * 1e-10
    if np.min(eigenvalues, initial=0.0) < -tolerance:
        raise ValueError("L_E must be positive semidefinite")
    keep = eigenvalues > tolerance
    return sparse.csr_matrix(np.sqrt(eigenvalues[keep])[:, None] * eigenvectors[:, keep].T)


def estimate_edge_flows(
    B: Any,
    L_E: Any,
    H: Any,
    y: Any,
    f_prev: Any,
    *,
    weights: Any | None = None,
    W: Any | None = None,
    boundary: Any | None = None,
    b: Any | None = None,
    lambda_spatial: float = 1.0,
    lambda_temporal: float = 1.0,
    lambda_conservation: float = 1.0,
) -> np.ndarray:
    """Estimate non-negative edge flow using deterministic bounded least squares.

    ``weights`` (or its equation-friendly alias ``W``) contains observation
    confidence multipliers in ``[0, 1]``. ``boundary``/``b`` is the node source
    and sink vector; it defaults to zero. Dense arrays and SciPy sparse matrices
    are accepted. Empty observation matrices are valid.
    """
    try:
        from scipy import sparse
        from scipy.optimize import lsq_linear
    except ImportError as exc:  # pragma: no cover - depends on installation
        raise ImportError("estimate_edge_flows requires scipy") from exc

    penalties = (lambda_spatial, lambda_temporal, lambda_conservation)
    if any(not np.isfinite(value) or value < 0 for value in penalties):
        raise ValueError("regularization parameters must be finite and non-negative")

    previous = np.asarray(f_prev, dtype=float).reshape(-1)
    edge_count = len(previous)
    if not np.all(np.isfinite(previous)):
        raise ValueError("f_prev must contain only finite values")
    incidence = sparse.csr_matrix(B, dtype=float)
    observation = sparse.csr_matrix(H, dtype=float)
    if incidence.shape[1] != edge_count:
        raise ValueError("B column count must match f_prev")
    if observation.shape[1] != edge_count:
        raise ValueError("H column count must match f_prev")
    if (incidence.nnz and not np.all(np.isfinite(incidence.data))) or (
        observation.nnz and not np.all(np.isfinite(observation.data))
    ):
        raise ValueError("matrix inputs must contain only finite values")

    observed = _as_vector(y, observation.shape[0], "y")
    if weights is not None and W is not None:
        raise ValueError("pass only one of weights or W")
    confidence = _as_vector(weights if weights is not None else W, len(observed), "weights", 1.0)
    if np.any(confidence < 0) or np.any(confidence > 1):
        raise ValueError("weights must lie in [0, 1]")
    if boundary is not None and b is not None:
        raise ValueError("pass only one of boundary or b")
    sources = _as_vector(boundary if boundary is not None else b, incidence.shape[0], "boundary")

    blocks: list[Any] = []
    targets: list[np.ndarray] = []
    if observation.shape[0]:
        weighted_observation = sparse.diags(confidence, format="csr") @ observation
        blocks.append(weighted_observation)
        targets.append(confidence * observed)
    if lambda_spatial:
        blocks.append(np.sqrt(lambda_spatial) * _laplacian_factor(L_E, edge_count, sparse))
        targets.append(np.zeros(blocks[-1].shape[0]))
    else:
        lap_shape = sparse.csr_matrix(L_E).shape
        if lap_shape != (edge_count, edge_count):
            raise ValueError(f"L_E must have shape ({edge_count}, {edge_count})")
    if lambda_temporal:
        blocks.append(np.sqrt(lambda_temporal) * sparse.eye(edge_count, format="csr"))
        targets.append(np.sqrt(lambda_temporal) * previous)
    if lambda_conservation:
        blocks.append(np.sqrt(lambda_conservation) * incidence)
        targets.append(np.sqrt(lambda_conservation) * sources)

    if edge_count == 0:
        return np.empty(0, dtype=float)
    if not blocks or sum(block.shape[0] for block in blocks) == 0:
        return np.maximum(previous, 0.0)
    design = sparse.vstack(blocks, format="csr")
    target = np.concatenate(targets)
    result = lsq_linear(design, target, bounds=(0.0, np.inf), method="trf", tol=1e-10, lsmr_tol=1e-10)
    if not result.success:
        raise RuntimeError(f"edge-flow estimation failed: {result.message}")
    flow = np.asarray(result.x, dtype=float)
    flow[np.abs(flow) < 1e-10] = 0.0
    return flow
