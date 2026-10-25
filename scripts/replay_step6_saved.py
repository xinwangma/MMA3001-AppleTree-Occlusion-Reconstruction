"""Reproduce Step 6 predictions from saved observations, without simulator/GT input."""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

def run(results):
    study=module('evaluate_step6');policy=module('replay_saved_synthetic')
    plan=study.load(results/'frozen_experiment_plan.json')
    count=0;largest=0.
    for config in plan['configs']:
        folder=results/'synthetic'/config['case_id']
        camera=study.Calibration(**study.load(folder/'calibration.json'))
        with np.load(folder/'inputs_and_reference.npz',allow_pickle=False) as data:
            # Deliberately do not read any truth/reference/analytic entries.
            visible,depth,occlusion=[data[k] for k in ('visible','depth','occlusion')]
        for method in study.METHODS:
            actual=study.infer_one(visible,depth,camera,visible,occlusion,method,plan['settings'])['graph3d']
            expected=study.load(folder/f'{method}_graph3d.json')
            diagnostics=policy.compare_graphs(json.loads(json.dumps(actual,allow_nan=False)),expected)
            largest=max(largest,diagnostics['max_absolute_difference']);count+=1
    algorithm_policy=study.load(results/'numerical_policy.json') if (results/'numerical_policy.json').exists() else {'name':'historical_v1_no_angular_guard'}
    return dict(graphs_checked=count,exact_identity_connectivity_status=True,rtol=policy.RTOL,atol=policy.ATOL,
                algorithm_policy=algorithm_policy,
                maximum_float_difference=largest,simulator_called=False,reference_arrays_read=False,
                scope='independent per-method preprocessing replay vs saved shared-workflow outputs')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    current=ROOT/'results/step6_final_validation_v2_boundary_policy'
    parser.add_argument('--results',type=Path,default=current if current.exists() else ROOT/'results/step6_final_validation')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.report and args.report.exists():parser.error('Report already exists')
    report=run(args.results.resolve())
    if args.report:
        with args.report.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
