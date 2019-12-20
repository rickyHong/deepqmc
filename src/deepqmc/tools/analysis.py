import numpy as np
import torch

from ..physics import pairwise_distance, pairwise_self_distance
from ..utils import batch_eval, shuffle_tensor

__all__ = ()


class GaussianKDEstimator:
    def __init__(self, xs, max_memory=1.0, weights=None, *, bw):
        assert len(xs.shape) == 2
        self._xs = xs
        self._weights = weights if weights is not None else None
        self._width = np.sqrt(2) * bw
        self._bs = int(2 ** 30 * max_memory) // (xs.nelement() * xs.element_size() or 1)

    def __call__(self, xs):
        assert len(xs.shape) == 2
        if len(xs) > self._bs:
            return batch_eval(self, xs.split(self._bs))
        kernel = ((xs[:, None] - self._xs) ** 2).sum(dim=-1) / self._width ** 2
        norm = 1 / (len(self._xs) * (np.sqrt(np.pi) * self._width) ** xs.shape[1])
        basis = torch.exp(-kernel)
        if self._weights is not None:
            basis = self._weights * basis
        return norm * basis.sum(dim=-1)


def blocking(xs, max_B=None):
    N = xs.shape[1]
    x_sigma = xs.std()
    max_B = max_B or int(np.log2(N))
    sigmas_B = []
    for log_B in range(0, max_B):
        B = 2 ** log_B
        sigmas_B.append(
            xs[:, -(N // B * B) :]
            .view(xs.shape[0], -1, B)
            .mean(dim=-1)
            .std(dim=-1)
            .mean()
            * np.sqrt(B)
            / x_sigma
        )
    return torch.tensor(sigmas_B)


def autocorr_coeff(ks, xs):
    x_mean = xs.mean()
    x_var = xs.var()
    Cs = []
    for k in ks:
        end = -k or xs.shape[1]
        x_autocov = ((xs[:, :end] - x_mean) * (xs[:, k:] - x_mean)).mean()
        Cs.append(x_autocov / x_var)
    return torch.tensor(Cs)


def pair_correlations_from_samples(rs, n_up, bw=0.1):
    R_uu = pairwise_self_distance(rs[:, :n_up]).flatten()
    R_dd = pairwise_self_distance(rs[:, n_up:]).flatten()
    R_ud = pairwise_distance(rs[:, :n_up], rs[:, n_up:]).flatten()
    rs_decorr = shuffle_tensor(rs.view(-1, 3)).view(-1, 2, 3)
    R_decorr = pairwise_self_distance(rs_decorr)[:, 0]
    return {
        'uu': GaussianKDEstimator(R_uu[:, None], bw=bw),
        'dd': GaussianKDEstimator(R_dd[:, None], bw=bw),
        'ud': GaussianKDEstimator(R_ud[:, None], bw=bw),
        'decorr': GaussianKDEstimator(R_decorr[:, None], bw=bw),
    }
