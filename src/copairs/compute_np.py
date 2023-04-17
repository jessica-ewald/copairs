from collections.abc import Callable
import numpy as np
from tqdm.auto import tqdm


def pairwise_indexed(feats: np.ndarray, pair_ix: np.ndarray,
                     batch_pairwise_op: Callable[[np.ndarray, np.ndarray],
                                                 np.ndarray], batch_size):
    '''Get pairwise correlation using a list of paired indices'''
    num_pairs = len(pair_ix)

    corrs = []
    for i in tqdm(range(0, num_pairs, batch_size), leave=False):
        x_sample = feats[pair_ix[i:i + batch_size, 0]]
        y_sample = feats[pair_ix[i:i + batch_size, 1]]
        corr = batch_pairwise_op(x_sample, y_sample)
        corrs.append(corr)

    corrs = np.concatenate(corrs)
    assert len(corrs) == num_pairs
    return corrs


def pairwise_corr(x_sample: np.ndarray, y_sample: np.ndarray) -> np.ndarray:
    '''
    Compute pearson correlation between two matrices in a paired row-wise
    fashion. `x_sample` and `y_sample` must be of the same shape.
    '''
    x_mean = x_sample.mean(axis=1, keepdims=True)
    y_mean = y_sample.mean(axis=1, keepdims=True)

    x_center = x_sample - x_mean
    y_center = y_sample - y_mean

    numer = (x_center * y_center).sum(axis=1)

    denom = (x_center**2).sum(axis=1) * (y_center**2).sum(axis=1)
    denom = np.sqrt(denom)

    corrs = numer / denom
    return corrs


def pairwise_cosine(x_sample: np.ndarray, y_sample: np.ndarray) -> np.ndarray:
    x_norm = x_sample / np.linalg.norm(x_sample, axis=1)[:, np.newaxis]
    y_norm = y_sample / np.linalg.norm(y_sample, axis=1)[:, np.newaxis]
    c_dist = np.sum(x_norm * y_norm, axis=1)
    return c_dist
