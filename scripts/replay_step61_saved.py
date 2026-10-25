"""Read-only Step 6.1 observation replay and saved-graph metric audit.

No simulation, algorithm tuning, experiment timing, or evidence overwrite.
Run: python scripts/replay_step61_saved.py --project . --results PATH_TO_SAVED_RESULTS
"""
import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
import sys
import numpy as np


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def matches_frozen_source(path, expected):
    """Accept frozen bytes or line-ending conversion only, never changed code."""
    import hashlib
    raw = path.read_bytes()
    lf = raw.replace(b'\r\n', b'\n')
    return any(hashlib.sha256(value).hexdigest() == expected
               for value in (raw, lf, lf.replace(b'\n', b'\r\n')))


def audit(root, evidence=None):
    root = Path(root).resolve()
    sys.path.insert(0, str(root/'src'))
    study = module(root/'scripts/evaluate_step61.py', 'handover_study')
    assert study.ROOT == root
    out = Path(evidence).resolve() if evidence is not None else study.OUT
    study.OUT = out
    plan = load(out/'frozen_plan.json')
    assert matches_frozen_source(root/'src/apple_tree_project/completion.py', plan['baseline_sha256'])
    assert matches_frozen_source(root/'src/apple_tree_project/matching.py', plan['matching_sha256'])
    assert load(out/'development_complete.json')['matching_sha256'] == plan['matching_sha256']
    assert load(out/'development_complete.json')['settings_changed'] is False
    assert plan['policy'] == study.POLICY
    maximum = 0.
    comparisons = 0

    def same(actual, expected):
        nonlocal maximum, comparisons
        if isinstance(expected, dict):
            assert actual.keys() == expected.keys()
            for k in expected:
                same(actual[k], expected[k])
        elif isinstance(expected, list):
            assert len(actual) == len(expected)
            for a,b in zip(actual,expected):
                same(a,b)
        elif type(expected) is float:
            assert math.isfinite(actual) and math.isfinite(expected)
            delta = abs(actual-expected)
            assert delta <= 1e-12 + 1e-10*abs(expected), (actual, expected)
            maximum = max(maximum,delta)
            comparisons += 1
        else:
            assert actual == expected, (actual, expected)

    metric_rows = 0
    for cohort in ('development', 'evaluation'):
        rows = load(out/cohort/'metrics.json')
        decisions = {(r['case_id'],r['method']):r for r in load(out/cohort/'decisions.json')}
        configs = {c['case_id']: c for c in plan[cohort]}
        assert len(rows) == len(configs)*len(study.METHODS)
        assert len({(r['case_id'],r['method']) for r in rows}) == len(rows)
        for case_id in configs:
            folder = out/cohort/case_id
            # References are evaluator-only, never passed to replay inference.
            with np.load(folder/'inputs_and_reference.npz',allow_pickle=False) as z:
                truth, occlusion, reference, xyz, uv, roles = [z[k] for k in
                    ('truth','occlusion','reference_xyz','analytic_xyz','analytic_uv','analytic_role')]
            for row in (r for r in rows if r['case_id']==case_id):
                graph = load(folder/f'{row["method"]}_graph3d.json')
                decision = decisions[case_id,row['method']]
                skeleton = np.zeros_like(truth)
                inferred = np.zeros_like(truth)
                for n in graph['nodes']:
                    skeleton[n['y'],n['x']] = True
                    inferred[n['y'],n['x']] = n['inferred']
                result = dict(skeleton=skeleton,inferred_mask=inferred,graph=graph,
                              accepted=decision['accepted'],rejected=decision['rejected'])
                metrics = study.s.metric_2d(result, truth, occlusion)
                metrics.update(study.s.metric_3d(graph, reference, xyz, uv))
                for key, value in metrics.items():
                    same(value, row[key])
                wrong = labels = 0
                for request in decision['accepted']:
                    actual_roles = [int(roles[np.argmin(np.sum((uv-p)**2,axis=1))])
                                    for p in (request['start'],request['end'])]
                    wrong += actual_roles[0] != actual_roles[1]
                    labels += any(('trunk','left_primary','right_primary')[r] != request['branch']
                                  for r in actual_roles)
                same(int(wrong),row['incorrect_connections'])
                same(int(labels),row['incorrect_role_labels'])
                same(bool(decision['accepted']),row['completed'])
                same(len(decision['detection']['candidates']),row['detector_candidates'])
                same(len(decision['detection']['rejected']),row['detector_rejected_pairs'])
                metric_rows += 1
        same(study.summarize(rows),load(out/cohort/'summary.json'))
        with (out/cohort/'metrics.csv').open(encoding='utf-8-sig',newline='') as f:
            csv_rows = list(csv.DictReader(f))
        assert len(csv_rows)==len(rows)
        for a,b in zip(csv_rows,rows):
            for k,v in b.items():
                assert a[k] == (json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict))
                                else '' if v is None else str(v))
    evaluation_rows = load(out/'evaluation/metrics.json')
    same(study.summarize(evaluation_rows),load(out/'comparison_summary.json'))
    same(load(out/'evaluation/summary.json'),load(out/'comparison_summary.json'))
    assert (out/'evaluation/summary.csv').read_bytes()==(out/'comparison_summary.csv').read_bytes()
    # This function reads visible/depth/occlusion only; it never calls the simulator.
    replay = study.replay(plan['evaluation'])
    same(replay,load(out/'saved_observation_replay.json'))
    print('Saved metrics and 480-graph replay verified', flush=True)
    return dict(metric_rows_recomputed=metric_rows,numeric_values_checked=comparisons,
                maximum_metric_absolute_difference=maximum,metrics_from_saved_graphs=True,
                reference_arrays_used_only_for_metric_evaluation=True,
                timing_records_preserved_not_rerun=True,source_hashes_match_frozen_plan=True,
                source_hash_policy="Frozen original bytes or CRLF/LF conversion only",
                saved_observation_replay=replay)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--results', type=Path, help='Saved Step 6.1 evidence directory; never overwritten')
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    report = audit(args.project, args.results)
    if args.report:
        with args.report.open('x',encoding='utf-8') as f:
            json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps(report,indent=2))
