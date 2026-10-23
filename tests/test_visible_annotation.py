"""Provenance, coordinate and evaluation safeguards independent of raw data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from apple_tree_project.visible_annotation import POLICY,rasterize,verify_source
from apple_tree_project.baseline import visible_only_baseline


def annotation():
    return dict(policy=POLICY,image_size=[20,20],annotator='test annotator',
        provenance='ai_rgb_only_draft',review_status='pending',reviewer='',notes='Synthetic test only',
        polygons=[dict(id='wood',points=[[3,2],[7,2],[7,17],[3,17]])])


def load_validation():
    path=Path(__file__).parents[1]/'scripts/validate_visible_baseline.py'
    spec=importlib.util.spec_from_file_location('validation',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_polygon_native_geometry_and_reproducibility():
    a=annotation();mask=rasterize(a,(20,20))
    assert mask.dtype==np.uint8 and set(np.unique(mask))=={0,255}
    assert mask.sum()/255==5*16
    assert np.array_equal(mask,rasterize(json.loads(json.dumps(a)),(20,20)))
    assert mask[2,3]==255 and mask[1,3]==0


@pytest.mark.parametrize('change',[
    {'policy':'unknown'},{'image_size':[256,256]},{'provenance':'whole_gt'},
    {'annotator':''},{'review_status':'accepted','reviewer':''},{'polygons':[]},
    {'polygons':[{'id':'bad','points':[[0,0],[25,1],[1,3]]}]},
    {'polygons':[{'id':'bad','points':[[0,0],[1,1],[2,2]]}]},
    {'polygons':[{'id':'bad','points':[[.5,0],[1,1],[2,0]]}]}
])
def test_annotation_rejects_unsafe_or_untraceable_labels(change):
    a=annotation();a.update(change)
    with pytest.raises(ValueError):rasterize(a,(20,20))


def test_source_hash_binding(tmp_path):
    path=tmp_path/'rgb.png';Image.new('RGB',(20,20)).save(path)
    a=annotation();a['rgb_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    verify_source(a,path)
    Image.new('RGB',(20,20),'white').save(path)
    with pytest.raises(ValueError,match='hash'):verify_source(a,path)


def test_connectivity_diagnostics_detect_lost_component():
    m=load_validation();a=annotation()
    a['polygons'].append(dict(id='second',points=[[12,3],[15,3],[15,16],[12,16]]))
    mask=rasterize(a,(20,20));r=visible_only_baseline(mask)
    d=m.diagnostics(mask,r,a)
    assert d['components_preserved_one_to_one'] and d['input_components']==2
    assert d['patches_with_skeleton']==2
    damaged=visible_only_baseline(np.where(np.indices(mask.shape)[1]<10,mask,0))
    d=m.diagnostics(mask,damaged,a)
    assert not d['components_preserved_one_to_one'] and d['patches_with_skeleton']==1


def test_validation_draft_gate_outputs_and_source_preservation(tmp_path,monkeypatch):
    m=load_validation();monkeypatch.setattr(m,'ROOT',tmp_path)
    (tmp_path/'results').mkdir()
    rgb=tmp_path/'rgb.png';Image.new('RGB',(20,20),'gray').save(rgb)
    a=annotation();a.update(sample_id='test',rgb_path='rgb.png',rgb_sha256=hashlib.sha256(rgb.read_bytes()).hexdigest())
    bundle=tmp_path/'annotations.json';bundle.write_text(json.dumps(dict(samples=[a])))
    before=(rgb.read_bytes(),rgb.stat().st_mtime_ns)
    out=tmp_path/'results'/'run'
    with pytest.raises(ValueError,match='include-drafts'):m.run(bundle,out)
    assert not out.exists()
    summary=m.run(bundle,out,True,1)
    assert summary['accepted_human_review_count']==0
    assert summary['all_components_preserved'] and summary['changed_sources']==[]
    assert (out/'test'/'comparison.png').is_file() and (out/'contact_sheet.png').is_file()
    assert before==(rgb.read_bytes(),rgb.stat().st_mtime_ns)
    with pytest.raises(ValueError,match='preserve'):m.run(bundle,out,True,1)
    with pytest.raises(ValueError,match='below results'):m.run(bundle,tmp_path/'unsafe',True,1)


def test_real_draft_bundle_never_claims_human_truth():
    path=Path(__file__).parents[1]/'data/annotations/step3_rgb_only_drafts.json'
    samples=json.loads(path.read_text())['samples']
    assert len(samples)==12 and len({s['sample_id'] for s in samples})==12
    for a in samples:
        assert '_Summer_RGB-' in a['rgb_path'] and a['review_status']=='pending'
        assert a['provenance']=='ai_rgb_only_draft' and not a['reviewer']
        assert rasterize(a,(640,480)).any()
