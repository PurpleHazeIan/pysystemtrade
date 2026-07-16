"""Hierarchical Risk Parity optimiser."""
from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

from sysquant.estimators.estimates import Estimates
from sysquant.optimisation.weights import (
    estimatesWithPortfolioWeights,
    portfolioWeights,
)
from sysquant.optimisation.optimisers.equal_weights import (
    equal_weights_optimisation,
)


def hrp_optimisation(
    estimates: Estimates,
    linkage_method: str = "single",
    **_ignored_weighting_args,
) -> estimatesWithPortfolioWeights:
    """Compute portfolio weights using the Hierarchical Risk Parity algorithm."""
    asset_names = estimates.asset_names
    asset_count = len(asset_names)
    if asset_count == 0:
        empty_weights = portfolioWeights.allzeros([])
        return estimatesWithPortfolioWeights(weights=empty_weights, estimates=estimates)
    if asset_count == 1:
        single_weight = portfolioWeights.from_weights_and_keys([1.0], asset_names)
        return estimatesWithPortfolioWeights(weights=single_weight, estimates=estimates)

    corr_df = estimates.correlation.as_pd()
    stdev_array = np.asarray(estimates.stdev_list)

    if np.any(np.isnan(corr_df.values)) or np.any(np.isnan(stdev_array)):
        return equal_weights_optimisation(estimates)

    cov_matrix = _correlation_to_covariance(corr_df.values, stdev_array)
    if np.any(~np.isfinite(cov_matrix)):
        return equal_weights_optimisation(estimates)

    order = _quasi_diagonalise(cov_matrix, method=linkage_method)
    ordered_cov = cov_matrix[np.ix_(order, order)]
    ordered_weights = _recursive_bisection(ordered_cov)

    weights_array = np.zeros(asset_count, dtype=float)
    for position, asset_idx in enumerate(order):
        weights_array[asset_idx] = ordered_weights[position]

    weight_sum = weights_array.sum()
    if weight_sum <= 0 or not np.isfinite(weight_sum):
        return equal_weights_optimisation(estimates)

    weights_array /= weight_sum
    weights = portfolioWeights.from_weights_and_keys(
        list_of_weights=list(weights_array), list_of_keys=asset_names
    )

    return estimatesWithPortfolioWeights(weights=weights, estimates=estimates)


def _correlation_to_covariance(corr: np.ndarray, stdev: np.ndarray) -> np.ndarray:
    diag = np.array(stdev, dtype=float)
    outer = np.outer(diag, diag)
    return corr * outer


def _quasi_diagonalise(cov: np.ndarray, method: str = "single") -> list[int]:
    corr = _covariance_to_correlation(cov)
    distance = np.sqrt(np.clip(1.0 - corr, 0.0, 2.0) / 2.0)
    condensed = squareform(distance, checks=False)
    link = linkage(condensed, method=method)
    order = leaves_list(link).astype(int)
    return order.tolist()


def _covariance_to_correlation(cov: np.ndarray) -> np.ndarray:
    diag = np.sqrt(np.diag(cov))
    diag[diag == 0.0] = 0.0
    outer = np.outer(diag, diag)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.divide(cov, outer, out=np.zeros_like(cov), where=outer != 0)
    np.fill_diagonal(corr, 1.0)
    return corr


def _recursive_bisection(cov: np.ndarray) -> np.ndarray:
    n_assets = cov.shape[0]
    weights = np.ones(n_assets, dtype=float)
    clusters = [np.arange(n_assets)]

    while clusters:
        cluster = clusters.pop(0)
        if len(cluster) <= 1:
            continue
        left, right = _split_cluster(cluster)
        var_left = _cluster_variance(cov, left)
        var_right = _cluster_variance(cov, right)
        total_var = var_left + var_right
        if total_var == 0.0:
            alloc_left = alloc_right = 0.5
        else:
            alloc_left = 1.0 - var_left / total_var
            alloc_right = 1.0 - alloc_left
        weights[left] *= alloc_left
        weights[right] *= alloc_right
        clusters.extend([left, right])

    return weights


def _split_cluster(cluster: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    midpoint = len(cluster) // 2
    return cluster[:midpoint], cluster[midpoint:]


def _cluster_variance(cov: np.ndarray, cluster: np.ndarray) -> float:
    sub_cov = cov[np.ix_(cluster, cluster)]
    diag = np.diag(sub_cov)
    if np.any(diag <= 0):
        return 0.0
    inv_diag = 1.0 / diag
    inv_diag_sum = inv_diag.sum()
    if inv_diag_sum == 0.0:
        return 0.0
    weights = inv_diag / inv_diag_sum
    variance = float(weights @ sub_cov @ weights)
    return variance
