"""Additional boundary checks, independent of the supplied public examples."""
import numpy as np
import pytest
from avsim import core, space
from lab11 import metrics, modes, search
from test_todos import fake_rollout


def test_ttc_batch_without_leader_and_with_added_bicycle():
    r = fake_rollout(K=2)
    bike = core.Actor('H0', 'bike', 'bike', core.BIKE, 'E2', 0, 0, 'bike')
    r.actors = core.ACTORS + [bike]
    extra = np.zeros((2, core.NF, 1, 7), dtype=np.float32)
    r.F = np.concatenate([r.F, extra], axis=2)
    r.F[:, :, core.EGO, :5] = [0, 0, 1, 0, 10]
    r.F[:, :, core.N, :5] = [15.2, 0, 1, 0, 6]
    r.EGO[1, :, 3] = core.N
    assert metrics.min_ttc(r).tolist() == pytest.approx([10, 3], abs=1e-6)


def test_mode_precedence_pedestrian_before_rear_and_bus_boundaries():
    r = fake_rollout()
    r.F[0, 0, core.EGO, :4] = [100, 0, 1, 0]
    r.F[0, 0, core.P1, :4] = [95, 0, 1, 0]
    assert modes.label_mode(r, 0, dict(a='P1', b='ego', f=0), metrics.contact_type) == 'crosswalk_block'
    r.F[0, 0, core.C2, :5] = [112, 0, 1, 0, 5]
    event = dict(a='C2', b='ego', f=0)
    assert modes.label_mode(r, 0, event, metrics.contact_type) == 'cut_in'
    r.F[0, 0, core.C2, :5] = [105, 0, 1, 0, 6]
    assert modes.label_mode(r, 0, event, metrics.contact_type) == 'cut_in'


def test_cem_equal_scores_preserve_first_rows_and_do_not_mutate_prior():
    z = np.tile(np.arange(6.0)[:, None], (1, space.D))
    b = np.zeros((6, space.B))
    prior = search.natural_proposal(space.Natural())
    mean_before = prior['mean'].copy()
    result = search.cem_update(z, b, np.ones(6), prior, rho=0.1, smooth=1)
    assert np.allclose(result['mean'], 0.5)
    assert np.array_equal(prior['mean'], mean_before)
