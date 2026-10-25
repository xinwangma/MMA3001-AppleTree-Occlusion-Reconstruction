"""Fork-anchored matching safety, numerical boundaries and evidence separation."""
import inspect
import math
import numpy as np
import pytest
from PIL import Image, ImageDraw
from apple_tree_project.baseline import thin_visible
from apple_tree_project.completion import complete_gaps
from apple_tree_project.matching import detect_anchored_gaps, continuity_state


def fixture():
    image=Image.new('1',(128,128));draw=ImageDraw.Draw(image)
    for end in ((20,26),(108,26),(64,116)):
        draw.line([(64,70),end],fill=1)
    full=thin_visible(np.asarray(image,dtype=bool))
    mask=np.zeros_like(full);mask[38:53,32:49]=True
    return full & ~mask,mask


def test_anchored_bridge_and_input_preservation():
    visible,mask=fixture();before=visible.copy()
    detection=detect_anchored_gaps(visible)
    assert len(detection['candidates'])==1
    assert detection['candidates'][0]['branch']=='left_primary'
    for method in ('linear','quadratic'):
        result=complete_gaps(visible,detection['candidates'],mask,method,support_points=12)
        assert len(result['accepted'])==1
        assert len(result['graph']['components'])==1
        assert np.all(result['inferred_mask'] <= mask)
    assert np.array_equal(visible,before)


def test_missing_fork_never_connects_aligned_foreign_fragments():
    visible=np.zeros((80,80),bool);visible[40,5:25]=True;visible[40,40:65]=True
    result=detect_anchored_gaps(visible)
    assert not result['candidates']
    assert result['context_rejection']=='missing_visible_fork'


def test_no_occlusion_evidence_rejects_otherwise_valid_match():
    visible,mask=fixture();requests=detect_anchored_gaps(visible)['candidates']
    result=complete_gaps(visible,requests,np.zeros_like(mask),'quadratic',support_points=12)
    assert not result['accepted'] and result['rejected']
    assert np.array_equal(result['skeleton'],visible)


@pytest.mark.parametrize('delta',[-1e-12,0.,1e-12])
def test_direction_equality_and_roundoff_remain_rejected(delta):
    angle=math.radians(45.+delta);v=np.array([math.cos(angle),math.sin(angle)])
    first=-np.arange(12)[:,None]*v
    second=np.array([20.,0.])+np.arange(12)[:,None]*np.array([1.,0.])
    reason,_,_=continuity_state(first,second,np.array([1.,0.]),45.,45.)
    assert reason=='direction_ambiguous'


def test_reflection_swaps_roles_without_changing_acceptance():
    visible,_=fixture()
    result=detect_anchored_gaps(visible[:,::-1])
    assert len(result['candidates'])==1
    assert result['candidates'][0]['branch']=='right_primary'


def test_multifork_scope_and_gt_free_interface():
    visible,_=fixture();wide=np.concatenate([visible,visible],axis=1)
    result=detect_anchored_gaps(wide)
    assert not result['candidates']
    assert result['context_rejection']=='multiple_or_extended_visible_forks'
    assert set(inspect.signature(detect_anchored_gaps).parameters)=={
        'skeleton','max_gap_px','max_angle_deg','max_curvature_deg','support_points','fork_margin_px'}


@pytest.mark.parametrize('kwargs',[{'max_angle_deg':90},{'support_points':5},{'fork_margin_px':0}])
def test_invalid_policy_rejected(kwargs):
    visible,_=fixture()
    with pytest.raises(ValueError):detect_anchored_gaps(visible,**kwargs)
