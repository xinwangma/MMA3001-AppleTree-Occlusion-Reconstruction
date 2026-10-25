"""Angular decision policy: strict certified-below, conservative ambiguity."""
import importlib.util
import math
from pathlib import Path
import json
import numpy as np
import pytest
import apple_tree_project.completion as completion
from apple_tree_project.baseline import thin_visible
from apple_tree_project.reconstruction3d import Calibration,lift_skeleton


@pytest.mark.parametrize('value,expected',[
    (44.9999,'below'),(44.99999999999987,'ambiguous'),
    (math.nextafter(45.,-math.inf),'ambiguous'),(45.,'ambiguous'),
    (math.nextafter(45.,math.inf),'ambiguous'),(45.00000000000011,'ambiguous'),
    (45.0001,'above')])
def test_angular_boundary_below_exact_above(value,expected):
    assert completion._angular_threshold_state(value,45.)==expected


def test_band_endpoints_are_conservatively_rejected():
    guard=completion.ANGLE_BOUNDARY_GUARD_DEG
    assert completion._angular_threshold_state(45.-guard,45.)=='ambiguous'
    assert completion._angular_threshold_state(45.+guard,45.)=='ambiguous'
    assert completion._angular_threshold_state(45.-2*guard,45.)=='below'
    assert completion._angular_threshold_state(45.+2*guard,45.)=='above'


def test_guard_derived_from_float64_acos_conditioning_not_scores():
    envelope=math.degrees(math.acos(1-32*np.finfo(np.float64).eps))
    assert 0<envelope<=completion.ANGLE_BOUNDARY_GUARD_DEG==1e-5
    assert completion._angular_threshold_state(65.,65.)=='ambiguous'


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-float('inf')])
def test_nonfinite_angles_rejected(value):
    with pytest.raises(ValueError):completion._angular_threshold_state(value,45.)


@pytest.mark.parametrize('reported_angle',[44.99999999999987,45.,45.00000000000011])
@pytest.mark.parametrize('method',['linear','quadratic'])
def test_holdout_19_same_structure_under_reported_roundoff(monkeypatch,reported_angle,method):
    fixture=Path(__file__).parent/'fixtures/holdout_19_boundary_observations.npz'
    with np.load(fixture,allow_pickle=False) as arrays:
        visible,depth,occlusion=[arrays[k] for k in ('visible','depth','occlusion')]
    camera=Calibration(**json.loads((fixture.parent/'holdout_19_boundary_calibration.json').read_text()))
    skeleton=thin_visible(visible)  # Match the saved Step 6 infer_one preprocessing.
    original=completion._angular_threshold_state
    injected=[]
    def simulate(value,threshold):
        if threshold==45. and abs(value-threshold)<completion.ANGLE_BOUNDARY_GUARD_DEG:
            injected.append(value)
            return original(reported_angle,threshold)
        return original(value,threshold)
    monkeypatch.setattr(completion,'_angular_threshold_state',simulate)
    detection=completion.detect_candidate_gaps(skeleton,max_gap_px=80.,max_angle_deg=65.,max_curvature_deg=45.,support_points=8)
    assert injected and not detection['candidates']
    assert any(r['reason']=='local_curvature_threshold_numerically_ambiguous' for r in detection['rejected'])
    result=completion.complete_gaps(skeleton,detection['candidates'],occlusion,method)
    graph=lift_skeleton(result['graph'],depth,camera,visible,infer_hidden_depth=True)
    assert np.array_equal(result['skeleton'],skeleton)
    assert not result['accepted'] and not result['inferred_mask'].any()
    assert len(graph['nodes'])==int(skeleton.sum())==187
    assert graph['status_counts']==dict(measured=187,inferred=0,unsupported=0)
    assert all(not node['inferred'] for node in graph['nodes'])


def test_detector_direction_boundary_is_also_conservative(monkeypatch):
    skeleton=np.zeros((40,50),bool);skeleton[20,3:16]=True;skeleton[20,29:45]=True
    roles={(15,20):'left_primary',(29,20):'left_primary'}
    original=completion._angular_threshold_state
    def force_direction(value,threshold):
        return original(65.,threshold) if threshold==65. else original(value,threshold)
    monkeypatch.setattr(completion,'_angular_threshold_state',force_direction)
    result=completion.detect_candidate_gaps(skeleton,endpoint_roles=roles,max_gap_px=20)
    assert not result['candidates']
    assert any(r['reason']=='direction_threshold_numerically_ambiguous' for r in result['rejected'])
