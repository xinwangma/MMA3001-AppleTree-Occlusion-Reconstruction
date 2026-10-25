"""Step 6 metric, denominator, leakage-boundary and workflow regressions."""
import copy
import importlib.util
import inspect
from pathlib import Path
import json
import numpy as np
import pytest


@pytest.fixture(scope='module')
def study():
    path = Path(__file__).parents[1]/'scripts/evaluate_step6.py'
    spec = importlib.util.spec_from_file_location('step6_study', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_unsquared_chamfer_with_unequal_sample_counts(study):
    # forward mean 0, backward mean 1 -> symmetric average .5, not RMS/squared.
    assert study.chamfer([[0., 0.]], [[0., 0.], [2., 0.]]) == pytest.approx(.5)
    assert study.chamfer([[0., 0., 0.]], [[0., 0., 2.]]) == pytest.approx(2.)
    assert study.chamfer([], [[0., 0.]]) is None
    assert np.isinf(study.nearest([[0, 0]], [])).all()


def test_hidden_recall_denominator_and_baseline_no_fake_zero_error(study):
    skeleton = np.zeros((5, 9), bool); skeleton[2, 1:3] = True
    truth = skeleton.copy(); truth[2, 3:7] = True
    occlusion = np.zeros_like(truth); occlusion[2, 3:7] = True
    baseline = study.baseline_result(skeleton)
    score = study.metric_2d(baseline, truth, occlusion)
    assert score['hidden_reference_points'] == 4
    assert score['hidden_added_recall_2px'] == 0.
    assert score['inferred_chamfer_px'] is None
    assert score['full_chamfer_px'] > 0
    assert score['hidden_full_recall_2px'] > 0  # endpoints within tolerance are distinct from recovery


def test_3d_coverage_uses_fixed_reference_not_prediction_fraction(study):
    graph = dict(nodes=[dict(x=0,y=0,xyz_m=[0.,0.,1.],status_3d='measured')],
                 edges=[],supported_3d_components=[[0]],status_counts=dict(unsupported=0),hidden_depth_rejections=[])
    xyz = np.array([[0.,0.,1.],[2.,0.,1.]])
    metric = study.metric_3d(graph, xyz, xyz, np.array([[0.,0.],[2.,0.]]))
    assert metric['rmse_3d_m'] == 0
    assert metric['chamfer_3d_m'] == pytest.approx(.5)
    assert metric['coverage_3cm'] == .5
    assert metric['reference_3d_points'] == 2 and metric['supported_points'] == 1
    graph['nodes'][0]['xyz_m'][2] += .1
    assert study.metric_3d(graph, xyz, xyz, np.array([[0.,0.],[2.,0.]]))['rmse_3d_m'] == pytest.approx(.1)


def test_summary_keeps_rejected_cases_and_uses_paired_ids(study):
    fields = ('full_chamfer_px','inferred_chamfer_px','hidden_added_recall_2px','hidden_full_recall_2px',
              'rmse_3d_m','measured_rmse_m','inferred_rmse_m','chamfer_3d_m','coverage_3cm',
              'components_2d','components_3d','cycle_rank_3d')
    rows=[]
    for case in ('a','b','c'):
        for method in study.METHODS:
            accepted = method == 'linear' and case != 'b' or method == 'quadratic' and case != 'a'
            rows.append(dict(case_id=case,cohort='test',method=method,completed=accepted,
                             incorrect_connections=0,incorrect_role_labels=0,**{k:0. for k in fields}))
    summary=study.summaries(rows)
    for method in study.METHODS:
        all_cases=next(r for r in summary if r['method']==method and r['scope']=='all_cases')
        paired=next(r for r in summary if r['method']==method and r['scope']=='paired_both_completion_accepted')
        assert all_cases['cases']==3 and paired['cases']==1
        if method!='visible_only':assert all_cases['accepted_cases']==2 and all_cases['case_acceptance_rate']==pytest.approx(2/3)
        else:assert all_cases['case_acceptance_rate'] is None


def test_inference_signature_excludes_ground_truth(study):
    for function in (study.infer_one,study.infer_all):
        assert not any('truth' in p or 'reference' in p or 'analytic' in p for p in inspect.signature(function).parameters)


def test_shared_workflow_matches_original_and_preserves_inputs(study):
    scene=study.make_scene(dict(seed=19191,gap_width_px=16,depth_profile='linear',occluded_role='left_primary'))
    inputs=[scene[k].copy() for k in ('visible','depth','occlusion')]
    before={m:study.infer_one(scene['visible'],scene['depth'],scene['camera'],scene['visible'],scene['occlusion'],m) for m in study.METHODS}
    after=study.infer_all(scene['visible'],scene['depth'],scene['camera'],scene['visible'],scene['occlusion'])
    for method in study.METHODS:
        assert np.array_equal(before[method]['skeleton'],after[method]['skeleton'])
        assert before[method]['graph3d']==after[method]['graph3d']
        assert before[method]['accepted']==after[method]['accepted']
    for key,original in zip(('visible','depth','occlusion'),inputs):assert np.array_equal(scene[key],original)
    # Evaluation-side GT can be replaced without changing inference results.
    scene['truth'][:]=False;scene['analytic_xyz'][:]=1000.
    again=study.infer_all(scene['visible'],scene['depth'],scene['camera'],scene['visible'],scene['occlusion'])
    assert again['linear']['graph3d']==after['linear']['graph3d']


def test_frozen_holdout_and_targeted_diagnostics_are_disjoint(study):
    configs=study.experiment_configs()
    assert len(configs)==78 and len({c['case_id'] for c in configs})==78
    holdout=[c for c in configs if c['cohort']=='independent_holdout']
    assert len(holdout)==48
    assert not {c['seed'] for c in holdout}&{c['seed'] for c in configs if c['cohort']!='independent_holdout'}


def test_existing_output_is_never_overwritten(study,tmp_path):
    path=tmp_path/'existing';path.mkdir();sentinel=path/'data.txt';sentinel.write_text('preserve')
    with pytest.raises(ValueError):study.run(path)
    assert sentinel.read_text()=='preserve'


def test_case_records_keep_config_identity_without_duplicate_fields(study):
    config=dict(seed=19818,case_id='record_test',cohort='unit',gap_width_px=16,
                depth_profile='linear',occluded_role='left_primary')
    scene=study.make_scene(config)
    results=study.infer_all(scene['visible'],scene['depth'],scene['camera'],scene['visible'],scene['occlusion'])
    rows,decisions=study.evaluate_scene(scene,results,config['case_id'],config['cohort'])
    assert len(rows)==3 and len(decisions)==3
    assert all(r['case_id']=='record_test' and r['cohort']=='unit' for r in rows)
    assert all(r['reference_3d_points']>0 for r in rows)


def test_resume_json_keeps_existing_bytes_and_mtime(study,tmp_path):
    path=tmp_path/'record.json';study.save(path,dict(value=1,flags=[True,None]))
    original=(path.read_bytes(),path.stat().st_mtime_ns)
    study.save(path,dict(value=1,flags=[True,None]))
    assert (path.read_bytes(),path.stat().st_mtime_ns)==original
    with pytest.raises(ValueError):study.save(path,dict(value=2))
    assert (path.read_bytes(),path.stat().st_mtime_ns)==original


def test_resume_csv_keeps_existing_bytes_and_mtime(study,tmp_path):
    path=tmp_path/'record.csv';rows=[dict(case_id='a',value=.1,nodes=[1,2])]
    study.table(path,rows);original=(path.read_bytes(),path.stat().st_mtime_ns)
    study.table(path,rows)
    assert (path.read_bytes(),path.stat().st_mtime_ns)==original
    with pytest.raises(ValueError):study.table(path,[dict(case_id='b',value=.1,nodes=[1,2])])
    assert (path.read_bytes(),path.stat().st_mtime_ns)==original


def test_resume_rejects_changed_frozen_plan(study,tmp_path,monkeypatch):
    monkeypatch.setattr(study,'ROOT',tmp_path)
    output=tmp_path/'results/interrupted';(output/'verification').mkdir(parents=True)
    study.save(output/'verification/preservation_before.json',{})
    study.save(output/'frozen_experiment_plan.json',dict(configs=[],settings=study.SETTINGS))
    with pytest.raises(ValueError,match='Frozen plan changed'):
        study.run_or_resume(output,resume=True)


def test_zip_closed_before_readback_and_historical_checksums_preserved(study,tmp_path,monkeypatch):
    import hashlib,zipfile
    monkeypatch.setattr(study,'ROOT',tmp_path)
    output=tmp_path/'results/step6_final_validation';output.mkdir(parents=True)
    (output/'payload.json').write_text('{"test":1}')
    historic=output/'SHA256SUMS.txt';historic.write_text('Interrupted build record\n')
    original=(historic.read_bytes(),historic.stat().st_mtime_ns)
    for name in ('README.md','pyproject.toml','LICENSE','.gitignore'):(tmp_path/name).write_text('fixture\n')
    result=study.package_review(output)
    assert (historic.read_bytes(),historic.stat().st_mtime_ns)==original
    with zipfile.ZipFile(result) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert all('\\' not in name for name in names)
        hashes=json.loads(archive.read('step6_review_package/ZIP_MEMBER_SHA256.json'))
        assert len(hashes)==len(names)-1
        for name,digest in hashes.items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
        assert 'step6_review_package/results/SHA256SUMS_final.txt' in names


def test_positive_runtime_benchmark_requires_real_accepted_work(study,monkeypatch):
    skeleton=np.zeros((40,50),bool);skeleton[20,3:16]=True;skeleton[20,29:45]=True
    region=np.zeros_like(skeleton);region[20,16:29]=True
    request=[dict(id='positive',branch='trunk',start=[15,20],end=[29,20])]
    monkeypatch.setattr(study,'benchmark',lambda function:dict(median_ms=0.,scope_test_only=True))
    rows=study.positive_completion_benchmark(skeleton,request,region)
    assert len(rows)==2 and all(r['accepted_requests']==1 and r['inferred_pixels']==13 for r in rows)
    with pytest.raises(ValueError,match='at least one'):study.positive_completion_benchmark(skeleton,[],region)
    with pytest.raises(ValueError,match='did not exercise'):study.positive_completion_benchmark(skeleton,request,np.zeros_like(region))
