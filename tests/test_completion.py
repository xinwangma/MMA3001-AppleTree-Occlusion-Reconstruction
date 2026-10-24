"""Synthetic geometry tests; no real hidden-branch accuracy claims."""
import numpy as np
import pytest
from apple_tree_project.completion import complete_gaps, fit_quadratic, detect_candidate_gaps


def fixture():
    s=np.zeros((40,50),bool)
    s[20,3:16]=True;s[20,29:45]=True
    gaps=[dict(id='gap',branch='trunk',start=[15,20],end=[29,20])]
    o=np.zeros_like(s);o[20,16:29]=True
    return s,gaps,o


@pytest.mark.parametrize('method',['linear','quadratic'])
def test_bridge_preservation_and_inferred_graph(method):
    s,g,o=fixture();before=s.copy()
    r=complete_gaps(s,g,o,method)
    assert len(r['accepted'])==1 and not r['rejected']
    assert len(r['graph']['components'])==1
    assert np.array_equal(s,before) and np.all(r['skeleton'][s])
    assert r['inferred_mask'].sum()==13
    assert sum(n['inferred'] for n in r['graph']['nodes'])==13
    assert any(e['inferred'] for e in r['graph']['edges'])


def test_quadratic_improves_curved_analytic_gap_and_exact_endpoints():
    # x(t)=20+20t, y(t)=20+8t(t-1). Visible points lie outside gap.
    def curve(t):
        t=np.asarray(t);return np.c_[20+20*t,20+8*t*(t-1)]
    first=curve(np.linspace(0,-.3,8));second=curve(np.linspace(1,1.3,8))
    a,b,c=fit_quadratic(first,second,tangent_weight=.1)
    t=np.linspace(0,1,101)
    linear=a+t[:,None]*(b-a)
    quadratic=linear+(t*(t-1))[:,None]*c
    truth=curve(t)
    assert np.array_equal(quadratic[0],a) and np.array_equal(quadratic[-1],b)
    assert np.mean((quadratic-truth)**2)<np.mean((linear-truth)**2)
    # Rotation invariance: no y=f(x) assumption.
    rotation=np.array([[0,-1],[1,0]])
    assert np.allclose(fit_quadratic(first@rotation,second@rotation,.1)[2],c@rotation)


@pytest.mark.parametrize('change,reason',[
    ('occlusion','occlusion'),('distance','length'),('role','identity'),
    ('coordinate','integer'),('same','different'),('support','support')])
def test_ineligible_gaps_remain_unchanged(change,reason):
    s,g,o=fixture();kwargs={}
    if change=='occlusion':o[:]=False
    if change=='distance':kwargs['max_gap_px']=10
    if change=='role':g[0]['branch']='twig'
    if change=='coordinate':g[0]['start']=[15.5,20]
    if change=='same':g[0]['end']=[3,20]
    if change=='support':s[20,3:14]=False
    r=complete_gaps(s,g,o,**kwargs)
    assert not r['accepted'] and reason in r['rejected'][0]['reason']
    assert np.array_equal(r['skeleton'],s)


def test_endpoint_reuse_and_unrelated_crossing_rejected():
    s,g,o=fixture()
    repeated=dict(g[0],id='repeat')
    r=complete_gaps(s,g+[repeated],o)
    assert len(r['accepted'])==1 and len(r['rejected'])==1
    s[10:30,22]=True
    r=complete_gaps(s,g,np.ones_like(s))
    assert not r['accepted'] and 'topology' in r['rejected'][0]['reason']


def test_empty_and_invalid_inputs():
    s,g,o=fixture()
    assert np.array_equal(complete_gaps(s,[],o)['skeleton'],s)
    with pytest.raises(ValueError):complete_gaps(s,g,o[:2])
    with pytest.raises(ValueError):complete_gaps(s,g,o,method='cubic')
    with pytest.raises(ValueError):complete_gaps(s,g,o,tangent_weight=-1)


def test_detection_requires_main_identity_and_reports_geometry_uncertainty():
    s,g,o=fixture()
    roles={(15,20):'left_primary',(29,20):'left_primary',(3,20):'left_primary',(44,20):'left_primary'}
    r=detect_candidate_gaps(s,endpoint_roles=roles,max_gap_px=20)
    assert len(r['candidates'])==1
    assert r['candidates'][0]['occlusion_status']=='unverified'
    assert r['candidates'][0]['branch']=='left_primary'
    assert np.array_equal(s,fixture()[0])
    roles[(29,20)]='right_primary'
    r=detect_candidate_gaps(s,endpoint_roles=roles,max_gap_px=20)
    assert not r['candidates']
    assert any('identity' in d['reason'] for d in r['rejected'])


def test_ambiguous_matches_are_rejected_instead_of_nearest_neighbor():
    s=np.zeros((60,65),bool)
    s[30,3:20]=1;s[25,36:55]=1;s[35,36:55]=1
    roles={tuple([n['x'],n['y']]):'left_primary' for n in __import__('apple_tree_project.baseline',fromlist=['pixel_graph']).pixel_graph(s)['nodes']}
    r=detect_candidate_gaps(s,endpoint_roles=roles,max_gap_px=30)
    assert any(d['reason']=='ambiguous_multiple_compatible_matches' for d in r['rejected'])
    assert not r['candidates']


def test_synthetic_y_known_truth_both_methods():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).parents[1]/'scripts/evaluate_step4.py'
    spec=importlib.util.spec_from_file_location('study',path)
    study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
    counts={'linear':0,'quadratic':0}
    for role in ('trunk','left_primary','right_primary'):
        visible,occlusion,truth,_=study.synthetic_y(role)
        candidates=detect_candidate_gaps(visible,max_gap_px=100)['candidates']
        assert len(candidates)==1
        for method in ('linear','quadratic'):
            r=complete_gaps(visible,candidates,occlusion,method,max_gap_px=100)
            if not r['accepted']:
                # A rounded connector can leave the exact synthetic occluder
                # by one pixel. Conservative abstention is intentional.
                assert 'occlusion' in r['rejected'][0]['reason']
                assert np.array_equal(r['skeleton'],visible)
                continue
            counts[method]+=1
            m=study.measure(visible,occlusion,truth,r)
            assert m['connected'] and m['cycle_rank']==0
            assert m['visible_preserved'] and m['max_endpoint_error_px']==0
    assert min(counts.values())>=2


def test_curvature_threshold_and_invalid_detector_settings():
    s,g,o=fixture()
    s[20,3:16]=False
    s[20,10:16]=True;s[14:20,10]=True
    roles={(15,20):'left_primary',(29,20):'left_primary'}
    r=detect_candidate_gaps(s,endpoint_roles=roles,max_curvature_deg=5,max_angle_deg=80)
    assert any(d['reason']=='local_curvature_unstable' for d in r['rejected'])
    with pytest.raises(ValueError):detect_candidate_gaps(s,max_angle_deg=100)


def test_comparison_runner_outputs_and_protects_existing_directory(tmp_path,monkeypatch):
    import importlib.util,json
    from pathlib import Path
    from PIL import Image
    path=Path(__file__).parents[1]/'scripts/run_branch_completion.py'
    spec=importlib.util.spec_from_file_location('completion_cli',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Runner uses its location to establish the permitted project output root.
    monkeypatch.setattr(module,'__file__',str(tmp_path/'scripts/run_branch_completion.py'))
    s,g,o=fixture()
    sp,op,gp=tmp_path/'s.png',tmp_path/'o.png',tmp_path/'g.json'
    Image.fromarray(s.astype('uint8')*255).save(sp)
    Image.fromarray(o.astype('uint8')*255).save(op)
    gp.write_text(json.dumps({'gaps':g}))
    out=tmp_path/'results/run'
    summary=module.run(sp,op,gp,out)
    assert summary['linear']['accepted']==summary['quadratic']['accepted']==1
    assert (out/'quadratic/completion.json').exists()
    with pytest.raises(ValueError):module.run(sp,op,gp,out)
