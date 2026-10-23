"""Meaningful synthetic QA, review gates, geometry and coordinate regression tests."""
import copy
import importlib.util
from pathlib import Path
import numpy as np
import pytest
from apple_tree_project.baseline import visible_only_baseline,pixel_graph
from apple_tree_project.visible_annotation import rasterize,quality_checks,reset_review
from test_visible_annotation import annotation
from test_visible_annotation import load_validation


def script(name):
    path=Path(__file__).parents[1]/'scripts'/name
    spec=importlib.util.spec_from_file_location(path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_checkpoint_detects_missing_trunk_without_filling_gap():
    mask=np.zeros((30,30),np.uint8);mask[2:12,12:16]=255;mask[19:28,12:16]=255
    before=mask.copy();result=visible_only_baseline(mask)
    qa=quality_checks(mask,result['graph'],[
        dict(id='missing_trunk',point=[14,15],kind='visible_required',role='trunk'),
        dict(id='occluded_gap',point=[14,17],kind='occluded_excluded',role='trunk')])
    assert len(qa['failed_checkpoints'])==1
    assert qa['failed_checkpoints'][0]['id']=='missing_trunk'
    assert len(result['graph']['components'])==2
    assert np.array_equal(mask,before) and not result['skeleton'][12:19].any()


def test_occluded_checkpoint_flags_accidental_annotation():
    mask=np.ones((8,8),bool);graph=visible_only_baseline(mask)['graph']
    qa=quality_checks(mask,graph,[dict(id='leaf',point=[4,4],kind='occluded_excluded')])
    assert qa['failed_checkpoints'][0]['covered']


@pytest.mark.parametrize('point,kind',[([-1,0],'visible_required'),([1.2,2],'visible_required'),([2,2],'unknown')])
def test_invalid_checkpoint_rejected(point,kind):
    mask=np.zeros((8,8));graph=pixel_graph(mask)
    with pytest.raises(ValueError):quality_checks(mask,graph,[dict(id='bad',point=point,kind=kind)])


def test_no_checkpoints_does_not_claim_coverage_verified():
    mask=np.zeros((8,8));qa=quality_checks(mask,pixel_graph(mask))
    assert not qa['coverage_check_available'] and not qa['failed_checkpoints']


def test_short_spur_small_fragment_and_near_endpoints_are_prompts_only():
    skeleton=np.zeros((40,40),bool)
    skeleton[4:30,15]=True;skeleton[15,15:19]=True
    skeleton[32:35,15]=True
    graph=pixel_graph(skeleton);original=copy.deepcopy(graph)
    qa=quality_checks(skeleton,graph)
    assert any(p['short_spur_candidate'] for p in qa['terminal_paths'])
    assert qa['small_component_candidates'] and qa['near_disconnected_endpoints']
    assert len(qa['endpoint_coordinates'])==len(graph['endpoint_ids'])
    assert graph==original and len(graph['components'])==2


def test_crossing_polygon_is_rejected_even_with_nonzero_area():
    a=annotation();a['polygons'][0]['points']=[[1,1],[15,15],[1,15],[13,1]]
    with pytest.raises(ValueError,match='intersect'):rasterize(a,(20,20))


def test_zoom_and_scrolled_native_mapping():
    editor=script('annotate_visible_branches.py')
    assert editor.native_point(800,600,4,(640,480))==[200,150]
    assert editor.native_point(2559,100,4,(640,480)) is None
    assert editor.native_point(-4,0,2,(640,480)) is None


def test_draft_review_approval_are_separate_and_edits_reset_review():
    review=script('review_visible_annotation.py');a=annotation()
    with pytest.raises(ValueError,match='reviewed'):review.transition(a,'accepted','approver','checked')
    reviewed=review.transition(a,'reviewed','human A','Checked RGB coverage; no hidden wood')
    assert reviewed['review_status']=='reviewed' and reviewed['parent_provenance']=='ai_rgb_only_draft'
    assert a['review_status']=='pending' and a['provenance']=='ai_rgb_only_draft'
    with pytest.raises(ValueError,match='separate'):review.transition(reviewed,'accepted','human A','checked')
    approved=review.transition(reviewed,'accepted','human B','Approve scope with exclusions')
    assert approved['review_status']=='accepted' and approved['approved_by']=='human B'
    reset_review(approved)
    assert approved['review_status']=='pending' and not approved['reviewer']
    assert 'approved_by' not in approved and 'reviewed_utc' not in approved


def test_ai_metadata_cannot_claim_reviewed_or_approved():
    a=annotation();a.update(review_status='reviewed',reviewer='name',reviewed_utc='date',review_notes='notes')
    with pytest.raises(ValueError,match='AI draft'):rasterize(a,(20,20))


def test_geometry_review_requires_dates_and_notes():
    a=annotation();a.update(provenance='human_rgb_only',review_status='reviewed',reviewer='name')
    with pytest.raises(ValueError,match='date'):rasterize(a,(20,20))
    a.update(review_status='accepted',reviewed_utc='date',review_notes='notes')
    with pytest.raises(ValueError,match='approver'):rasterize(a,(20,20))


def test_editor_single_json_runs_qa_without_a_bundle(tmp_path,monkeypatch):
    import json
    import hashlib
    from PIL import Image
    runner=load_validation();monkeypatch.setattr(runner,'ROOT',tmp_path)
    rgb=tmp_path/'rgb.png';Image.new('RGB',(20,20),'gray').save(rgb)
    a=annotation();a.update(sample_id='single',rgb_path='rgb.png',rgb_sha256=hashlib.sha256(rgb.read_bytes()).hexdigest(),
        checkpoints=[dict(id='trunk',point=[5,10],kind='visible_required',role='trunk')])
    path=tmp_path/'annotation.json';path.write_text(json.dumps(a))
    result=runner.run(path,tmp_path/'results'/'single_run',True,1)
    qa=json.loads((tmp_path/'results'/'single_run'/'single'/'quality_checks.json').read_text())
    assert result['draft_count']==1 and result['manually_reviewed_count']==0
    assert result['accepted_human_review_count']==0 and qa['coverage_check_available']
    assert not qa['failed_checkpoints']
