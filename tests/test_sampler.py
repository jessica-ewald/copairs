'''Test functions for sampler'''
import numpy as np
import pandas as pd
import pytest

from copairs.sampler import Sampler, SamplerMultilabel
from tests.helpers import create_dframe, simulate_plates

SEED = 0


def run_stress_sample_null(dframe, num_pairs):
    '''Assert every null pair from a sampler does not match any column'''
    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    for _ in range(num_pairs):
        id1, id2 = sampler.sample_null_pair(dframe.columns)
        row1 = dframe.loc[id1]
        row2 = dframe.loc[id2]
        assert (row1 != row2).all()


def test_null_sample_large():
    '''Test Sampler guarantees elements with different values'''
    dframe = create_dframe(32, 10000)
    run_stress_sample_null(dframe, 5000)


def test_null_sample_small():
    '''Test Sample with small set'''
    dframe = create_dframe(3, 10)
    run_stress_sample_null(dframe, 100)


def test_null_sample_nan_vals():
    '''Test the sampler ignores NaN values'''
    dframe = create_dframe(4, 15)
    rng = np.random.default_rng(SEED)
    nan_mask = rng.random(dframe.shape) < 0.5
    dframe[nan_mask] = np.nan
    run_stress_sample_null(dframe, 1000)


def get_naive_pairs(dframe: pd.DataFrame, groupby, diffby):
    '''Compute valid pairs using cross product from pandas'''
    cross = dframe.reset_index().merge(dframe.reset_index(),
                                       how='cross',
                                       suffixes=('_x', '_y'))
    index = True
    for col in groupby:
        index = (cross[f'{col}_x'] == cross[f'{col}_y']) & index
    for col in diffby:
        index = (cross[f'{col}_x'] != cross[f'{col}_y']) & index

    pairs = cross.loc[index, ['index_x', 'index_y']]
    pairs = pairs.sort_values(['index_x', 'index_y']).reset_index(drop=True)
    return pairs


def check_naive(dframe, sampler, groupby, diffby):
    '''Check sampler and naive generate same pairs'''
    gt_pairs = get_naive_pairs(dframe, groupby, diffby)
    vals = sampler.get_all_pairs(groupby, diffby)
    vals = sum(vals.values(), [])
    vals = pd.DataFrame(vals, columns=['index_x', 'index_y'])
    vals = vals.sort_values(['index_x', 'index_y']).reset_index(drop=True)
    vals = set(vals.apply(frozenset, axis=1))
    gt_pairs = set(gt_pairs.apply(frozenset, axis=1))
    assert gt_pairs == vals


def test_replicate_pairs():
    '''Test sample of valid pairs from a random generator'''
    dframe = create_dframe(32, 1000)
    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    check_naive(dframe, sampler, groupby=['c'], diffby=['p', 'w'])


def test_replicate_pairs_multi():
    '''Test sample of valid pairs from a random generator'''
    dframe = create_dframe(32, 1000)
    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    check_naive(dframe, sampler, groupby=['c', 'w'], diffby=['p'])


def test_simulate_plates_single_groupby():
    '''Test sample of valid pairs from a simulated dataset'''
    dframe = simulate_plates(n_compounds=306, n_replicates=20, plate_size=384)
    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    check_naive(dframe, sampler, ['c'], ['p', 'w'])


def test_simulate_plates_mult_groupby():
    '''Test sample of valid pairs from a simulated dataset'''
    dframe = simulate_plates(n_compounds=306, n_replicates=20, plate_size=384)
    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    check_naive(dframe, sampler, ['c', 'w'], ['p'])


def test_raise_distjoint():
    '''Test check for disjoint groupby and diffby'''
    dframe = create_dframe(3, 10)
    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    with pytest.raises(ValueError, match='must be disjoint lists'):
        sampler.get_all_pairs('c', ['w', 'c'])


def assert_groupby_diffby(dframe: pd.DataFrame, pairs_dict: dict, groupby,
                          diffby):
    '''Assert the pairs are valid'''
    for _, pairs in pairs_dict.items():
        for id1, id2 in pairs:
            for col in groupby:
                assert dframe.loc[id1, col] == dframe.loc[id2, col]
            for col in diffby:
                assert dframe.loc[id1, col] != dframe.loc[id2, col]


def test_simulate_plates_mult_groupby_large():
    '''Test sampler successfully complete analysis of a large dataset.'''
    dframe = simulate_plates(n_compounds=15000,
                             n_replicates=20,
                             plate_size=384)
    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    groupby = ['c', 'w']
    diffby = ['p']
    pairs_dict = sampler.get_all_pairs(groupby, diffby)
    assert_groupby_diffby(dframe, pairs_dict, groupby, diffby)


def test_multilabel_column_groupby():
    '''Check the index generated by multilabel implementation is same as Sampler'''
    rng = np.random.default_rng(SEED)

    dframe = simulate_plates(n_compounds=4, n_replicates=5, plate_size=5)
    dframe = dframe[['p', 'w', 'c']]
    groupby = ['c']
    diffby = ['p', 'w']
    # Shuffle values
    for col in dframe.columns:
        rng.shuffle(dframe[col].values)
    dframe.drop_duplicates(inplace=True)
    dframe = dframe.sort_values(['p', 'w', 'c']).reset_index(drop=True)

    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    pairs_dict = sampler.get_all_pairs(groupby, diffby)
    check_naive(dframe, sampler, groupby, diffby)
    assert_groupby_diffby(dframe, pairs_dict, groupby, diffby)

    dframe_multi = dframe.groupby(diffby)['c'].unique().reset_index()
    multisampler = SamplerMultilabel(dframe_multi,
                                     dframe_multi.columns,
                                     multilabel_col='c',
                                     seed=SEED)
    pairs_dict_multi = multisampler.get_all_pairs(groupby=groupby,
                                                  diffby=diffby)

    for pairs_id, pairs in pairs_dict.items():
        assert pairs_id in pairs_dict_multi
        pairs_multi = pairs_dict_multi[pairs_id].copy()

        values_multi = set()
        for i, j in pairs_multi:
            row_i = dframe_multi.iloc[i][diffby]
            row_j = dframe_multi.iloc[j][diffby]
            value_multi = row_i.tolist() + row_j.tolist()
            values_multi.add(tuple(sorted(value_multi)))

        values = set()
        for i, j in pairs:
            row_i = dframe.iloc[i][diffby]
            row_j = dframe.iloc[j][diffby]
            value = row_i.tolist() + row_j.tolist()
            values.add(tuple(sorted(value)))

        assert values_multi == values


def test_multilabel_column_diffby():
    '''Check the index generated by multilabel implementation is same as Sampler'''
    rng = np.random.default_rng(SEED)

    dframe = simulate_plates(n_compounds=4, n_replicates=5, plate_size=5)
    groupby = ['p', 'w']
    diffby = ['c']
    # Shuffle values
    for col in dframe.columns:
        rng.shuffle(dframe[col].values)
    dframe = dframe.sort_values(['c', 'p', 'w']).reset_index(drop=True)

    sampler = Sampler(dframe, dframe.columns, seed=SEED)
    pairs_dict = sampler.get_all_pairs(groupby, diffby)
    check_naive(dframe, sampler, groupby, diffby)
    assert_groupby_diffby(dframe, pairs_dict, groupby, diffby)

    dframe_multi = dframe.groupby(groupby)['c'].unique().reset_index()
    multisampler = SamplerMultilabel(dframe_multi,
                                     dframe_multi.columns,
                                     multilabel_col='c',
                                     seed=SEED)
    pairs_dict_multi = multisampler.get_all_pairs(groupby=groupby,
                                                  diffby=diffby)

    for pairs_id, pairs in pairs_dict.items():
        if pairs_id in pairs_dict_multi:
            pairs_multi = pairs_dict_multi[pairs_id].copy()
        if pairs_id[::-1] in pairs_dict_multi:
            pairs_multi = pairs_dict_multi[pairs_id[::-1]].copy()
        else:
            raise AssertionError('Missing pairs for {pairs_id}')

        values_multi = set()
        for i, j in pairs_multi:
            row_i = dframe_multi.iloc[i][groupby]
            row_j = dframe_multi.iloc[j][groupby]
            value_multi = row_i.tolist() + row_j.tolist()
            values_multi.add(tuple(sorted(value_multi)))

        values = set()
        for i, j in pairs:
            row_i = dframe.iloc[i][groupby]
            row_j = dframe.iloc[j][groupby]
            value = row_i.tolist() + row_j.tolist()
            values.add(tuple(sorted(value)))

        assert values_multi == values
