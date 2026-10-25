"""Step 6: paired synthetic validation, read-only evidence reuse and profiling.

Run from the repository root. Never writes raw data or an existing output tree.
No whole-reference arrays are accepted by inference functions.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import html
import importlib.util
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc
import uuid
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from apple_tree_project.baseline import pixel_graph, thin_visible
from apple_tree_project.completion import complete_gaps, detect_candidate_gaps
from apple_tree_project.reconstruction3d import Calibration, backproject, lift_skeleton

ROOT = Path(__file__).resolve().parents[1]
METHODS = ('visible_only', 'linear', 'quadratic')
SETTINGS = dict(max_gap_px=80., max_angle_deg=65., max_curvature_deg=45., support_points=8)
SEED = 60261025


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if load(path) != data:
            raise ValueError('Preserving different existing JSON: '+str(path))
        return
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)


def write(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding='utf-8') != text:
            raise ValueError('Preserving different existing text: '+str(path))
        return
    with path.open('x', encoding='utf-8') as stream:
        stream.write(text)


def table(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v
                     for k, v in row.items()} for row in rows)
    content = stream.getvalue().encode('utf-8-sig')
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('Preserving different existing CSV: '+str(path))
        return
    with path.open('xb') as destination:
        destination.write(content)


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    stat = Path(path).stat()
    return dict(sha256=digest.hexdigest(), size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def nearest(a, b):
    """Unsquared nearest Euclidean distances; empty target gives +infinity."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if not len(a):
        return np.empty(0)
    if not len(b):
        return np.full(len(a), np.inf)
    return np.concatenate([np.sqrt(np.min(np.sum((part[:, None]-b[None, :])**2, axis=2), axis=1))
                           for part in np.array_split(a, max(1, math.ceil(len(a)/256)))])


def chamfer(a, b):
    if not len(a) or not len(b):
        return None
    return float((nearest(a, b).mean()+nearest(b, a).mean())/2)


def baseline_result(skeleton):
    return dict(skeleton=skeleton.copy(), inferred_mask=np.zeros_like(skeleton),
                graph=pixel_graph(skeleton), accepted=[], rejected=[])


def infer_one(visible_mask, depth, camera, support, occlusion, method, settings=None):
    """Original workflow baseline: each requested method repeats preprocessing."""
    settings = SETTINGS if settings is None else settings
    skeleton = thin_visible(visible_mask)
    if method == 'visible_only':
        result = baseline_result(skeleton)
        detection = dict(candidates=[], rejected=[])
    else:
        detection = detect_candidate_gaps(skeleton, **settings)
        result = complete_gaps(skeleton, detection['candidates'], occlusion, method,
                               **{k: settings[k] for k in ('max_gap_px', 'max_angle_deg', 'support_points')})
    result['graph3d'] = lift_skeleton(result['graph'], depth, camera, support,
                                      infer_hidden_depth=method != 'visible_only')
    result['detection'] = detection
    return result


def infer_all(visible_mask, depth, camera, support, occlusion, settings=None):
    """Comparison workflow only: share identical thinning/detection, no method changes."""
    settings = SETTINGS if settings is None else settings
    skeleton = thin_visible(visible_mask)
    detection = detect_candidate_gaps(skeleton, **settings)
    results = {}
    for method in METHODS:
        result = (baseline_result(skeleton) if method == 'visible_only' else
                  complete_gaps(skeleton, detection['candidates'], occlusion, method,
                                **{k: settings[k] for k in ('max_gap_px', 'max_angle_deg', 'support_points')}))
        result['graph3d'] = lift_skeleton(result['graph'], depth, camera, support,
                                          infer_hidden_depth=method != 'visible_only')
        result['detection'] = dict(candidates=[], rejected=[]) if method == 'visible_only' else detection
        results[method] = result
    return results


def raster(curve, size):
    image = Image.new('1', size)
    ImageDraw.Draw(image).line([tuple(p) for p in np.rint(curve).astype(int)], fill=1)
    return np.array(image, bool)


def make_scene(config):
    """Analytic 3D curves -> projection -> noisy observations; GT stays evaluator-side.

    The experiment simulator defines visible surface depth from the known scene;
    algorithms receive only that observation, camera, support and occluder region.
    """
    rng = np.random.default_rng(config['seed'])
    width, height = config.get('width', 192), config.get('height', 192)
    camera = Calibration(width, height, 140*width/192, 140*height/192, width/2, height/2,
                         1., 'axial_z', (0.,), True, True, 'CALIBRATED SYNTHETIC Step 6 simulator')
    t = np.linspace(0, 1, 1001)
    junction = np.array([rng.uniform(-.09, .09), rng.uniform(-.1, .05), 3.])
    a0 = junction + [rng.uniform(-.12, .12), .95, config.get('trunk_z', .15)]
    angles = config.get('angles_deg', [float(rng.uniform(25, 60)), float(rng.uniform(25, 60))])
    length = config.get('branch_length_m', 1.3)
    ends = [junction+[-length*np.sin(np.deg2rad(angles[0])), -length*np.cos(np.deg2rad(angles[0])), -.2],
            junction+[length*np.sin(np.deg2rad(angles[1])), -length*np.cos(np.deg2rad(angles[1])), .2]]
    curvature = config.get('curvature', float(rng.uniform(-.7, .7)))
    defs = [(a0, junction, np.array([.12, 0, .1])),
            (junction, ends[0], np.array([.15*curvature, curvature, .1])),
            (junction, ends[1], np.array([-.1*curvature, -.8*curvature, -.1]))]
    truths, projections, noisy_projections, masks = [], [], [], []
    profile = config.get('depth_profile', 'linear')
    for role, (a, b, coefficient) in enumerate(defs):
        xyz = a+t[:, None]*(b-a)+(t*(t-1))[:, None]*coefficient
        if profile == 'constant':
            xyz[:, 2] = 3.
        elif profile == 'nonlinear':
            xyz[:, 2] += (.45 if role == 1 else -.25)*np.sin(np.pi*t)
        elif profile == 'steep':
            xyz[:, 2] += (1.3 if role == 1 else .25)*t
        uv = np.c_[camera.fx*xyz[:, 0]/xyz[:, 2]+camera.cx,
                   camera.fy*xyz[:, 1]/xyz[:, 2]+camera.cy]
        direction = uv[-1]-uv[0]
        normal = np.array([-direction[1], direction[0]])/np.linalg.norm(direction)
        phase = rng.uniform(0, 2*np.pi)
        noise = config.get('observation_noise_px', 0.)*np.sin(5*np.pi*t+phase)*np.sin(np.pi*t)
        observed = uv+noise[:, None]*normal
        truths.append(xyz); projections.append(uv); noisy_projections.append(observed)
        masks.append(raster(uv, (width, height)))
    full = thin_visible(np.logical_or.reduce(masks))
    observed = thin_visible(np.logical_or.reduce([raster(p, (width, height)) for p in noisy_projections]))
    role_index = ('trunk', 'left_primary', 'right_primary').index(config.get('occluded_role', 'left_primary'))
    centre = projections[role_index][int(config.get('occlusion_t', .5)*1000)]
    yy, xx = np.indices(full.shape)
    half = config.get('gap_width_px', 20)/2
    occlusion = (abs(xx-centre[0]) <= half) & (abs(yy-centre[1]) <= half)
    visible = observed & ~occlusion
    xyz, uv = np.vstack(truths), np.vstack(projections)
    labels = np.repeat(np.arange(3), len(t))
    depth = np.full(full.shape, .4)
    for y, x in np.argwhere(visible):
        i = int(np.argmin(np.sum((uv-[x, y])**2, axis=1)))
        depth[y, x] = xyz[i, 2]+rng.normal(0, config.get('depth_noise_m', 0.))
    # Reference samples are one analytic point for each thinned clean reference pixel.
    reference_pixels = np.argwhere(full)[:, ::-1]
    index = np.array([np.argmin(np.sum((uv-p)**2, axis=1)) for p in reference_pixels])
    return dict(camera=camera, visible=visible, occlusion=occlusion, depth=depth, truth=full,
                reference_xyz=xyz[index], reference_pixels=reference_pixels, analytic_xyz=xyz,
                analytic_uv=uv, analytic_role=labels, config=config)


def metric_2d(result, truth, occlusion):
    predicted = np.argwhere(result['skeleton'])[:, ::-1]
    target = np.argwhere(truth)[:, ::-1]
    inferred = np.argwhere(result['inferred_mask'])[:, ::-1]
    hidden = np.argwhere(truth & occlusion)[:, ::-1]
    count = len(hidden)
    graph = result['graph']
    return dict(predicted_2d_points=len(predicted), reference_2d_points=len(target), hidden_reference_points=count,
                full_chamfer_px=chamfer(predicted, target), inferred_chamfer_px=chamfer(inferred, hidden),
                hidden_added_recall_2px=float(np.mean(nearest(hidden, inferred) <= 2)) if count else None,
                hidden_full_recall_2px=float(np.mean(nearest(hidden, predicted) <= 2)) if count else None,
                false_inferred_pixels_over_3px=int(np.sum(nearest(inferred, hidden) > 3)),
                inferred_points=len(inferred), components_2d=len(graph['components']),
                cycle_rank_2d=len(graph['edges'])-len(graph['nodes'])+len(graph['components']),
                accepted_requests=len(result['accepted']), completion_rejected_requests=len(result['rejected']))


def metric_3d(graph, reference_xyz, analytic_xyz, analytic_uv):
    supported = [n for n in graph['nodes'] if n['xyz_m'] is not None]
    points = np.array([n['xyz_m'] for n in supported]).reshape(-1, 3)
    errors, measured, inferred = [], [], []
    for node in supported:
        i = int(np.argmin(np.sum((analytic_uv-[node['x'], node['y']])**2, axis=1)))
        error = float(np.linalg.norm(np.asarray(node['xyz_m'])-analytic_xyz[i]))
        errors.append(error)
        (measured if node['status_3d'] == 'measured' else inferred).append(error)
    rms = lambda a: float(np.sqrt(np.mean(np.square(a)))) if len(a) else None
    edges = sum(e['status_3d'] != 'unsupported' for e in graph['edges'])
    components = len(graph['supported_3d_components'])
    return dict(supported_points=len(points), measured_points=len(measured), inferred_3d_points=len(inferred),
                unsupported_points=graph['status_counts']['unsupported'], reference_3d_points=len(reference_xyz),
                rmse_3d_m=rms(errors), measured_rmse_m=rms(measured), inferred_rmse_m=rms(inferred),
                max_position_error_m=max(errors) if errors else None,
                chamfer_3d_m=chamfer(points, reference_xyz),
                coverage_3cm=float(np.mean(nearest(reference_xyz, points) <= .03)),
                components_3d=components, cycle_rank_3d=edges-len(points)+components,
                depth_rejected_chains=len(graph['hidden_depth_rejections']))


def evaluate_scene(scene, results, case_id, cohort):
    rows = []
    decisions = []
    roles = ('trunk', 'left_primary', 'right_primary')
    for method, result in results.items():
        wrong_connections, wrong_labels = 0, 0
        for record in result['accepted']:
            endpoint_labels = []
            for p in (record['start'], record['end']):
                i = np.argmin(np.sum((scene['analytic_uv']-p)**2, axis=1))
                endpoint_labels.append(roles[scene['analytic_role'][i]])
            wrong_connections += endpoint_labels[0] != endpoint_labels[1]
            wrong_labels += any(label != record['branch'] for label in endpoint_labels)
        row = dict(case_id=case_id, cohort=cohort, method=method, classification='CALIBRATED SYNTHETIC',
                   completed=bool(result['accepted']), incorrect_connections=int(wrong_connections),
                   incorrect_role_labels=int(wrong_labels), detector_candidates=len(result['detection']['candidates']),
                   detector_rejected_pairs=len(result['detection']['rejected']),
                   **{k:v for k,v in scene['config'].items() if k not in ('case_id','cohort')},
                   **metric_2d(result, scene['truth'], scene['occlusion']),
                   **metric_3d(result['graph3d'], scene['reference_xyz'], scene['analytic_xyz'], scene['analytic_uv']))
        rows.append(row)
        decisions.append(dict(case_id=case_id, method=method, detection=result['detection'],
                              accepted=result['accepted'], rejected=result['rejected'],
                              depth_rejections=result['graph3d']['hidden_depth_rejections']))
    return rows, decisions


def summaries(rows):
    output = []
    numeric = ('full_chamfer_px', 'inferred_chamfer_px', 'hidden_added_recall_2px', 'hidden_full_recall_2px',
               'rmse_3d_m', 'measured_rmse_m', 'inferred_rmse_m', 'chamfer_3d_m', 'coverage_3cm',
               'components_2d', 'components_3d', 'cycle_rank_3d')
    for cohort in dict.fromkeys(r['cohort'] for r in rows):
        subset = [r for r in rows if r['cohort'] == cohort]
        paired_ids = sorted({r['case_id'] for r in subset if r['method'] == 'linear' and r['completed']} &
                            {r['case_id'] for r in subset if r['method'] == 'quadratic' and r['completed']})
        for method in METHODS:
            all_rows = [r for r in subset if r['method'] == method]
            for scope in ('all_cases', 'own_accepted_cases', 'paired_both_completion_accepted'):
                selected = (all_rows if scope == 'all_cases' else
                            [r for r in all_rows if r['completed']] if scope == 'own_accepted_cases' else
                            [r for r in all_rows if r['case_id'] in paired_ids])
                record = dict(cohort=cohort, method=method, scope=scope, cases=len(selected),
                              all_case_denominator=len(all_rows), accepted_cases=sum(r['completed'] for r in all_rows),
                              rejected_or_no_completion_cases=sum(not r['completed'] for r in all_rows),
                              case_acceptance_rate=(sum(r['completed'] for r in all_rows)/len(all_rows)
                                                    if all_rows and method != 'visible_only' else None),
                              incorrect_connections=sum(r['incorrect_connections'] for r in selected),
                              incorrect_role_labels=sum(r['incorrect_role_labels'] for r in selected))
                for field in numeric:
                    values = [r[field] for r in selected if r[field] is not None]
                    record['mean_'+field] = float(np.mean(values)) if values else None
                    record['n_'+field] = len(values)
                output.append(record)
    return output


def panels(scene, results, path, title):
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 3, figsize=(13, 4))
    for axis, method in zip(axes, METHODS):
        axis.imshow(scene['truth'], cmap='gray_r', alpha=.22)
        result = results[method]
        for mask, color, name in [(scene['visible'], '#008b9a', 'observed'),
                                  (result['inferred_mask'], '#ce1689', 'inferred')]:
            y, x = np.where(mask)
            axis.scatter(x, y, s=4, c=color, label=name)
        axis.set(title=f'{method}: accepted={len(result["accepted"])}', xlabel='u (px)', ylabel='v (px)')
        axis.legend(fontsize=6)
    figure.suptitle(title); figure.tight_layout(); figure.savefig(path, dpi=130); plt.close(figure)


def reuse_existing(output):
    """Recompute summaries/distances from saved values; no old sweeps repeated."""
    old4 = load(ROOT/'results/step4_occlusion_completion/synthetic_metrics.json')
    existing_summary = load(ROOT/'results/step4_occlusion_completion/summary.json')
    for method in ('linear', 'quadratic'):
        selected = [r for r in old4 if r['method'] == method]
        assert len(selected) == existing_summary[method]['cases']
        assert sum(bool(r['accepted']) for r in selected) == existing_summary[method]['completed_cases']
        assert np.isclose(np.mean([r['hidden_recall_2px'] for r in selected]), existing_summary[method]['mean_hidden_recall_2px'])
    table(output/'reuse/step4_2d_cases.csv', old4); save(output/'reuse/step4_2d_cases.json', old4)
    save(output/'reuse/step4_summary.json', existing_summary)
    old5 = load(ROOT/'results/step5_3d_reconstruction/sensitivity.json')
    table(output/'reuse/step5_depth_camera_sensitivity.csv', old5)
    save(output/'reuse/step5_depth_camera_sensitivity.json', old5)
    # Recompute all 15 saved graphs' 3D distance/coverage metrics and paired 2D metrics.
    saved_metrics = load(ROOT/'results/step5_3d_reconstruction/synthetic_metrics.json')
    rows, measured_only = [], []
    for kind in ('constant_z', 'varying_z', 'curved_z'):
        folder = ROOT/'results/step5_3d_reconstruction/synthetic'
        ref = load(folder/f'{kind}_reference.json')
        truth = np.array(Image.open(folder/f'{kind}_whole_reference.png')) > 0
        visible = np.array(Image.open(folder/f'{kind}_visible.png')) > 0
        occlusion = np.array(Image.open(folder/f'{kind}_occlusion.png')) > 0
        reference = np.array([p['xyz_m'] for p in ref['raster_reference']])
        for method in METHODS:
            suffix = 'measured_only' if method == 'visible_only' else 'inferred_z'
            for state in (['measured_only'] if method == 'visible_only' else ['measured_only', 'inferred_z']):
                graph = load(folder/f'{kind}_{method}_{state}.json')
                values = metric_3d(graph, reference, np.array(ref['analytic_xyz_m']), np.array(ref['projected_uv']))
                original = next(r for r in saved_metrics if r['scene'] == kind and r['method'] == method
                                and r['hidden_z_inference'] == (state == 'inferred_z'))
                assert np.isclose(values['rmse_3d_m'], original['supported_rmse_m'])
                assert np.isclose(values['coverage_3cm'], original['reference_coverage_3cm'])
                measured_only.append(dict(scene=kind, method=method, state=state, **values))
                if state != suffix:
                    continue
                mask = np.zeros_like(visible); inferred = np.zeros_like(visible)
                for n in graph['nodes']:
                    mask[n['y'], n['x']] = True
                    inferred[n['y'], n['x']] = n['inferred']
                decision = load(folder/f'{kind}_{method}_2d_decisions.json')
                graph2d = pixel_graph(mask)
                result = dict(skeleton=mask, inferred_mask=inferred, graph=graph2d,
                              accepted=decision['accepted'], rejected=decision['rejected'])
                rows.append(dict(case_id=kind, cohort='step5_saved', method=method,
                                 classification='CALIBRATED SYNTHETIC', completed=bool(decision['accepted']),
                                 incorrect_connections=0, incorrect_role_labels=0,
                                 **metric_2d(result, truth, occlusion), **values))
    table(output/'reuse/step5_all_15_graphs.csv', measured_only)
    save(output/'reuse/verification.json', dict(step4_rows_checked=len(old4), step5_graph_metrics_checked=len(measured_only),
        step5_sensitivity_rows=len(old5), policy='Recomputed aggregates/metrics from saved data; original runtime retained without relabelling'))
    return rows, old4, old5


def experiment_configs():
    configs = []
    for index in range(48):
        configs.append(dict(case_id=f'holdout_{index:02d}', cohort='independent_holdout', seed=SEED+index,
                            occluded_role=('trunk', 'left_primary', 'right_primary')[index % 3],
                            occlusion_t=(.22, .45, .72, .9)[index % 4], gap_width_px=(10, 20, 32, 48)[(index//4) % 4],
                            depth_profile=('constant', 'linear', 'nonlinear', 'steep')[(index//3) % 4],
                            observation_noise_px=(0., .35, .8, 1.5)[(index//12) % 4],
                            depth_noise_m=(0., .003, .015)[index % 3]))
    for role in ('left_primary', 'right_primary'):
        for profile in ('linear', 'nonlinear'):
            for width in (8, 16, 24, 40, 64):
                configs.append(dict(case_id=f'gap_{role}_{profile}_{width}', cohort='targeted_3d_gap',
                                    seed=SEED+1000, occluded_role=role, occlusion_t=.5,
                                    gap_width_px=width, depth_profile=profile, observation_noise_px=0., depth_noise_m=0.))
        for curve in (-.8, -.4, 0., .4, .8):
            configs.append(dict(case_id=f'curvature_{role}_{curve}', cohort='targeted_physical_curvature',
                                seed=SEED+2000, occluded_role=role, occlusion_t=.55,
                                gap_width_px=24, depth_profile='linear', curvature=curve,
                                observation_noise_px=0., depth_noise_m=0.))
    return configs


def new_experiments(output):
    configs = experiment_configs()
    save(output/'frozen_experiment_plan.json', dict(seed=SEED, settings=SETTINGS,
         holdout_count=48, targeted_count=30, configs=configs,
         rule='Frozen defaults; no parameter selection on holdout; targeted cases are separate diagnostic cohorts'))
    rows, decisions = [], []
    for index, config in enumerate(configs):
        folder = output/'synthetic'/config['case_id']
        if (folder/'case_metrics.json').exists() and (folder/'case_decisions.json').exists():
            rows.extend(load(folder/'case_metrics.json'))
            decisions.extend(load(folder/'case_decisions.json'))
            continue
        scene = make_scene(config)
        results = infer_all(scene['visible'], scene['depth'], scene['camera'], scene['visible'], scene['occlusion'])
        measured, logs = evaluate_scene(scene, results, config['case_id'], config['cohort'])
        rows.extend(measured); decisions.extend(logs)
        # Save compact complete reference/observation/graph evidence for every new case.
        folder.mkdir(parents=True, exist_ok=True)
        arrays=dict(visible=scene['visible'], depth=scene['depth'], occlusion=scene['occlusion'], truth=scene['truth'],
                    reference_xyz=scene['reference_xyz'], analytic_xyz=scene['analytic_xyz'],
                    analytic_uv=scene['analytic_uv'], analytic_role=scene['analytic_role'])
        npz=folder/'inputs_and_reference.npz'
        if npz.exists():
            with np.load(npz,allow_pickle=False) as old:
                if set(old.files)!=set(arrays) or any(not np.array_equal(old[k],v) for k,v in arrays.items()):
                    raise ValueError('Preserving different existing synthetic inputs')
        else:
            np.savez_compressed(npz, **arrays)
        save(folder/'calibration.json', asdict(scene['camera']))
        for method, result in results.items():
            save(folder/f'{method}_graph3d.json', result['graph3d'])
        # Include representative examples and every case where either completion declines.
        if index < 6 or (config['cohort'] == 'independent_holdout' and not all(results[m]['accepted'] for m in METHODS[1:])):
            if not (folder/'comparison.png').exists():
                panels(scene, results, folder/'comparison.png', config['case_id']+' | CALIBRATED SYNTHETIC')
        save(folder/'case_metrics.json', measured)
        save(folder/'case_decisions.json', logs)
        if (index+1)%12==0:
            print(f'Step 6: completed {index+1}/{len(configs)} frozen configurations',flush=True)
    save(output/'decisions.json', decisions)
    return rows


def negative_experiments(output):
    rows, evidence = [], []
    for kind in ('no_occlusion_evidence', 'unrelated_crossing', 'ambiguous_targets', 'unknown_identity',
                 'gap_too_long', 'wrong_direction', 'foreign_aligned_fragment', 'missing_depth_anchor'):
        s = np.zeros((60, 70), bool); s[30, 4:21] = True; s[30, 36:58] = True
        region = np.zeros_like(s); region[30, 21:36] = True
        request = [dict(id='negative_gap', branch='left_primary', start=[20, 30], end=[36, 30])]
        if kind == 'no_occlusion_evidence': region[:] = False
        if kind == 'unrelated_crossing': s[18:43, 28] = True; region[:] = True
        if kind == 'ambiguous_targets':
            s[:] = False; s[30, 4:21] = True; s[25, 36:58] = True; s[35, 36:58] = True; region[:] = True
        if kind == 'wrong_direction':
            s[:] = False; s[14:31, 20] = True; s[30, 36:58] = True; region[:] = True
        roles = {tuple([n['x'], n['y']]): 'left_primary' for n in pixel_graph(s)['nodes']}
        detection = detect_candidate_gaps(s, endpoint_roles={} if kind == 'unknown_identity' else roles, max_gap_px=30)
        requests = detection['candidates'] if kind in ('ambiguous_targets', 'unknown_identity') else request
        for method in METHODS[1:]:
            result = complete_gaps(s, requests, region, method, max_gap_px=10 if kind == 'gap_too_long' else 80)
            camera = Calibration(70, 60, 50., 50., 35., 30., 1., 'axial_z', (0.,), True, True, 'Synthetic negative fixture')
            depth = np.full(s.shape, 3.)
            if kind == 'missing_depth_anchor': depth[30, 20] = 0
            graph = lift_skeleton(result['graph'], depth, camera, s, infer_hidden_depth=True)
            semantically_wrong = kind == 'foreign_aligned_fragment' and bool(result['accepted'])
            row = dict(case_id=kind, method=method, completion_accepted=len(result['accepted']),
                       detector_rejections=len(detection['rejected']), completion_rejections=len(result['rejected']),
                       depth_rejected_chains=len(graph['hidden_depth_rejections']),
                       incorrect_object_connection=int(semantically_wrong),
                       expected='2D may connect but hidden 3D must stay unsupported' if kind == 'missing_depth_anchor' else
                                'Known geometric method cannot identify foreign wood from aligned pixels' if kind == 'foreign_aligned_fragment' else 'reject',
                       reason=[r['reason'] for r in result['rejected']]+[r['reason'] for r in detection['rejected']])
            rows.append(row)
            evidence.append(dict(**row, requests=requests, detection=detection, graph3d=graph))
            path = output/'negative'/f'{kind}_{method}.png'; path.parent.mkdir(exist_ok=True)
            image = np.zeros((*s.shape, 3), np.uint8); image[s] = [0, 190, 210]
            image[result['inferred_mask']] = [255, 30, 150]
            if not path.exists(): Image.fromarray(image).resize((560, 480)).save(path)
    table(output/'negative_cases.csv', rows); save(output/'negative_cases.json', evidence)
    return rows


def real_review(output):
    import matplotlib.pyplot as plt
    rows, decision_records = [], []
    flagged = {'R06N02', 'R08N02', 'R09N02', 'R10N02'}
    source = ROOT/'results/step3_real_validation/coverage_revision_v4/run'
    for prior_path in sorted((ROOT/'results/step4_occlusion_completion/real').glob('R*.json')):
        prior = load(prior_path); sample = prior['sample_id']; annotation = load(source/sample/'annotation.json')
        assert annotation['provenance'] == 'ai_rgb_only_draft' and annotation['review_status'] == 'pending'
        assert fingerprint(ROOT/annotation['rgb_path'])['sha256'] == annotation['rgb_sha256']
        visible_graph = load(source/sample/'graph.json')
        visible = np.array(Image.open(source/sample/'skeleton.png')) > 0
        # Independently check existing candidate decisions once, not a new real accuracy study.
        detection = detect_candidate_gaps(visible, max_gap_px=100)
        assert detection == prior['candidate_detection']
        fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        for axis, method in zip(axes, METHODS):
            result = dict(graph=visible_graph, accepted=[], rejected=[]) if method == 'visible_only' else prior['methods'][method]
            graph = result['graph']
            if method != 'visible_only':
                replay = complete_gaps(visible, detection['candidates'], ~visible, method, max_gap_px=100)
                assert replay['graph'] == graph
            for state, color in ((False, '#008b9a'), (True, '#ce1689')):
                p = np.array([[n['x'], n['y']] for n in graph['nodes'] if n['inferred'] == state])
                if len(p): axis.scatter(*p.T, c=color, s=4, label='inferred hypothesis' if state else 'visible draft')
            axis.set(xlim=(0, 640), ylim=(480, 0), aspect='equal', title=method, xlabel='u image pixels', ylabel='v image pixels')
            axis.legend(fontsize=6)
            rows.append(dict(sample_id=sample, method=method, classification='UNCALIBRATED/QUALITATIVE',
                             annotation_status='AI DRAFT / pending', human_accepted=False,
                             independent_manual_review_required=sample in flagged, components=len(graph['components']),
                             nodes=len(graph['nodes']), edges=len(graph['edges']),
                             cycle_rank=len(graph['edges'])-len(graph['nodes'])+len(graph['components']),
                             accepted_hypotheses=len(result['accepted']), rejected_requests=len(result['rejected']),
                             candidate_rejections=len(detection['rejected']),
                             rejection_reasons=dict(Counter(r['reason'] for r in detection['rejected']+result['rejected'])),
                             occlusion_confirmed=False, real_metric_xyz_supported=False))
        fig.suptitle(sample+' | AI DRAFT | image pixels, NOT physical 3D'+(' | HUMAN REVIEW REQUIRED' if sample in flagged else ''))
        fig.tight_layout(); path = output/'real'/f'{sample}.png'; path.parent.mkdir(exist_ok=True)
        if not path.exists(): fig.savefig(path, dpi=135)
        plt.close(fig)
        decision_records.append(dict(sample_id=sample, independent_manual_review_required=sample in flagged,
                                     detection=detection, methods=prior['methods'], annotation_provenance=annotation))
    table(output/'real/qualitative_comparison.csv', rows); save(output/'real/qualitative_comparison.json', rows)
    save(output/'real/decisions_and_provenance.json', decision_records)
    return rows


def benchmark(function, warmup=3, repeats=15, memory=True):
    for _ in range(warmup): function()
    timings = []
    for _ in range(repeats):
        start = time.perf_counter_ns(); result = function(); timings.append((time.perf_counter_ns()-start)/1e6)
    peak = None
    if memory:
        tracemalloc.start(); result = function(); _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    return dict(median_ms=float(np.median(timings)), minimum_ms=min(timings), p90_ms=float(np.percentile(timings, 90)),
                mean_ms=float(np.mean(timings)), warmup=warmup, repeats=repeats, traced_peak_bytes=peak, samples_ms=timings)


def positive_completion_benchmark(skeleton, requests, occlusion):
    """Time actual successful completion, separately from empty-request screening.

    Requests must be supplied explicitly and both original methods must accept.
    This is a completion-only microbenchmark, not detection or full-pipeline time.
    """
    if not requests:
        raise ValueError('A positive benchmark requires at least one gap request')
    records=[]
    for method in METHODS[1:]:
        probe=complete_gaps(skeleton, requests, occlusion, method)
        if not probe['accepted']:
            raise ValueError('Positive benchmark did not exercise accepted '+method+' completion')
        result=benchmark(lambda method=method:complete_gaps(skeleton,requests,occlusion,method))
        records.append(dict(method=method,width=skeleton.shape[1],height=skeleton.shape[0],
                            supplied_requests=len(requests),accepted_requests=len(probe['accepted']),
                            rejected_requests=len(probe['rejected']),inferred_pixels=int(probe['inferred_mask'].sum()),
                            scope='successful completion-only with explicit saved gap request; no detection/lifting/I/O',**result))
    return records


def run_positive_completion_audit(output):
    """New successful-fit timing only; reuse saved Step 5 observations/requests."""
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results'):
        raise ValueError('Choose a new audit directory below results/')
    source=ROOT/'results/step5_3d_reconstruction/synthetic'
    paths=[source/'varying_z_visible.png',source/'varying_z_occlusion.png',source/'varying_z_linear_2d_decisions.json']
    skeleton=np.array(Image.open(paths[0]))>0
    occlusion=np.array(Image.open(paths[1]))>0
    requests=load(paths[2])['detection']['candidates']
    records=positive_completion_benchmark(skeleton,requests,occlusion)
    output.mkdir(parents=True)
    table(output/'successful_completion_runtime.csv',records)
    save(output/'successful_completion_runtime.json',records)
    save(output/'provided_gap_requests.json',requests)
    save(output/'provenance.json',dict(source='existing Step 5 varying_z observed skeleton and explicit request',
         original_files={p.relative_to(ROOT).as_posix():fingerprint(p) for p in paths},
         timer='perf_counter_ns',warmup=3,repeats=15,memory='one separate tracemalloc invocation',
         no_threshold_tuning=True,inference_ground_truth_input=False))
    np.savez_compressed(output/'observed_inputs.npz',visible=skeleton,occlusion=occlusion)
    return records


def performance(output):
    rows, optimisation = [], []
    replay_spec = importlib.util.spec_from_file_location('replay_policy', ROOT/'scripts/replay_saved_synthetic.py')
    policy = importlib.util.module_from_spec(replay_spec); replay_spec.loader.exec_module(policy)
    for width, height in ((192, 192), (640, 480)):
        config = dict(seed=SEED+3000, width=width, height=height, gap_width_px=18*width/192,
                      depth_profile='linear', observation_noise_px=0., occluded_role='left_primary')
        scene = make_scene(config)
        # Timed extraction starts from a thick branch mask, not from RGB or GT.
        mask = np.array(Image.fromarray(scene['visible'].astype('uint8')*255).filter(ImageFilter.MaxFilter(7))) > 0
        mask &= ~scene['occlusion']
        skeleton = thin_visible(mask)
        detection = detect_candidate_gaps(skeleton, **SETTINGS)
        completion = {m: complete_gaps(skeleton, detection['candidates'], scene['occlusion'], m) for m in METHODS[1:]}
        graph = pixel_graph(skeleton)
        # Supply valid synthetic observed depth at thick-mask-derived skeleton pixels.
        depth = scene['depth'].copy()
        for y, x in np.argwhere(skeleton):
            i = np.argmin(np.sum((scene['analytic_uv']-[x, y])**2, axis=1)); depth[y, x] = scene['analytic_xyz'][i, 2]
        support = skeleton.copy()
        pixels = np.array([[n['x'], n['y']] for n in graph['nodes']]).reshape(-1, 2)
        raw = np.array([depth[n['y'], n['x']] for n in graph['nodes']])
        stages = {'skeleton_extraction': lambda: thin_visible(mask), 'pixel_graph': lambda: pixel_graph(skeleton),
                  'candidate_detection': lambda: detect_candidate_gaps(skeleton, **SETTINGS),
                  'linear_completion': lambda: complete_gaps(skeleton, detection['candidates'], scene['occlusion'], 'linear'),
                  'quadratic_completion': lambda: complete_gaps(skeleton, detection['candidates'], scene['occlusion'], 'quadratic'),
                  'vector_backprojection_only': lambda: backproject(pixels, raw, scene['camera'])}
        for method in METHODS:
            g = graph if method == 'visible_only' else completion[method]['graph']
            stages[f'{method}_3d_lifting'] = lambda g=g, method=method: lift_skeleton(g, depth, scene['camera'], support, infer_hidden_depth=method != 'visible_only')
            stages[f'{method}_mask_to_3d_pipeline'] = lambda method=method: infer_one(mask, depth, scene['camera'], support, scene['occlusion'], method)
        for stage, function in stages.items():
            rows.append(dict(width=width, height=height, skeleton_nodes=len(graph['nodes']), stage=stage,
                             **benchmark(function)))
        before_function = lambda: {m: infer_one(mask, depth, scene['camera'], support, scene['occlusion'], m) for m in METHODS}
        after_function = lambda: infer_all(mask, depth, scene['camera'], support, scene['occlusion'])
        original, shared = before_function(), after_function()
        for method in METHODS:
            assert np.array_equal(original[method]['skeleton'], shared[method]['skeleton'])
            assert original[method]['accepted'] == shared[method]['accepted']
            assert original[method]['rejected'] == shared[method]['rejected']
            policy.compare_graphs(json.loads(json.dumps(original[method]['graph3d'])), json.loads(json.dumps(shared[method]['graph3d'])))
        # Alternate order to reduce first/second execution bias; retain every paired timing.
        for _ in range(3): before_function(); after_function()
        paired = []
        for repeat in range(15):
            times = {}
            order = (('before', before_function), ('after', after_function))
            for label, function in order if repeat % 2 == 0 else reversed(order):
                start = time.perf_counter_ns(); function(); times[label] = (time.perf_counter_ns()-start)/1e6
            paired.append(times)
        before = float(np.median([p['before'] for p in paired])); after = float(np.median([p['after'] for p in paired]))
        optimisation.append(dict(width=width, height=height, before_median_ms=before, after_median_ms=after,
                                 speedup=before/after, reduction_fraction=1-after/before, pairs=paired,
                                 equivalence_verified=True, scope='three-method comparison workflow only; original numerical algorithms unchanged',
                                 before_memory=benchmark(before_function, warmup=0, repeats=1)['traced_peak_bytes'],
                                 after_memory=benchmark(after_function, warmup=0, repeats=1)['traced_peak_bytes']))
    table(output/'performance/stage_runtime.csv', rows); save(output/'performance/stage_runtime.json', rows)
    table(output/'performance/comparison_workflow_optimisation.csv', optimisation)
    save(output/'performance/comparison_workflow_optimisation.json', optimisation)
    hardware = subprocess.run(['powershell', '-NoProfile', '-Command',
                              'Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress'],
                             capture_output=True, text=True)
    save(output/'performance/environment.json', dict(python=sys.version, platform=platform.platform(),
         processor=platform.processor(), logical_cpus=os.cpu_count(), hardware_query=hardware.stdout.strip(),
         hardware_query_exit=hardware.returncode, timer='time.perf_counter_ns', warmup=3, repeats=15,
         memory_scope='tracemalloc peak for one separate invocation; Python/NumPy tracked allocations, not process RSS or complete native memory',
         runtime_scope='mask+registered synthetic depth to graph; excludes RGB segmentation, calibration, I/O, metrics, plotting, and manual annotation',
         dependencies={name: importlib.metadata.version(name) for name in ('numpy', 'Pillow', 'matplotlib')}))
    return rows, optimisation


def plots(output, rows, old4, old5, runtimes):
    import matplotlib.pyplot as plt
    for name, records, factors, field, ylabel in (
            ('step4_existing', old4, list(dict.fromkeys(r['factor'] for r in old4)), 'hidden_recall_2px', 'Hidden added recall within 2 px'),
            ('step5_existing', old5, list(dict.fromkeys(r['factor'] for r in old5)), 'supported_rmse_m', 'Conditional supported RMSE (m)')):
        fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
        for axis, factor in zip(axes.flat, factors):
            selected = [r for r in records if r['factor'] == factor]
            values = sorted({r['value'] for r in selected})
            for method in METHODS[1:]:
                y = [np.mean([r[field] for r in selected if r['value'] == value and r['method'] == method]) for value in values]
                axis.plot(values, y, '-o', label=method)
            axis.set(title=factor, xlabel=factor, ylabel=ylabel); axis.grid(alpha=.3)
        for axis in list(axes.flat)[len(factors):]: axis.axis('off')
        axes.flat[0].legend(); fig.suptitle('REUSED existing evidence; repeated base settings are not independent trees')
        path=output/'figures'/f'{name}_sensitivity.png'
        if not path.exists():fig.savefig(path, dpi=140)
        plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), constrained_layout=True)
    for method in METHODS[1:]:
        selected = [r for r in old5 if r['method'] == method and r['factor'] == 'depth_dropout_fraction']
        values = sorted({r['value'] for r in selected})
        for axis, field in zip(axes, ('reference_coverage_3cm', 'supported_components', 'supported_rmse_m')):
            axis.plot(values, [np.mean([r[field] for r in selected if r['value'] == v]) for v in values], '-o', label=method)
            axis.set(xlabel='Depth dropout fraction', ylabel=field); axis.grid(alpha=.3)
    axes[0].legend(); fig.suptitle('Existing dropout evidence: low conditional error can hide missing geometry')
    if not (output/'figures/depth_dropout_coverage.png').exists():fig.savefig(output/'figures/depth_dropout_coverage.png', dpi=140)
    plt.close(fig)
    target_summary = []
    for cohort, field in [('targeted_3d_gap', 'gap_width_px'), ('targeted_physical_curvature', 'curvature')]:
        selected = [r for r in rows if r['cohort'] == cohort]
        fig, axes = plt.subplots(1, 3, figsize=(15, 4), constrained_layout=True)
        values = sorted({r[field] for r in selected})
        for method in METHODS:
            for value in values:
                group = [r for r in selected if r[field] == value and r['method'] == method]
                target_summary.append(dict(cohort=cohort, factor=field, value=value, method=method, cases=len(group),
                                           acceptance_rate=np.mean([r['completed'] for r in group]) if method != 'visible_only' else None,
                                           mean_hidden_recall=np.mean([r['hidden_added_recall_2px'] for r in group]),
                                           mean_rmse_m=np.mean([r['rmse_3d_m'] for r in group]),
                                           mean_coverage=np.mean([r['coverage_3cm'] for r in group])))
            for axis, metric in zip(axes, ('hidden_added_recall_2px', 'rmse_3d_m', 'coverage_3cm')):
                axis.plot(values, [np.mean([r[metric] for r in selected if r[field] == value and r['method'] == method]) for value in values], '-o', label=method)
                axis.set(xlabel=field+(' (m coefficient)' if field == 'curvature' else ' (square width in pixels)'), ylabel=metric); axis.grid(alpha=.3)
        axes[0].legend(); fig.suptitle('NEW targeted diagnostics — not holdout tuning')
        path=output/'figures'/f'{cohort}.png'
        if not path.exists():fig.savefig(path, dpi=140)
        plt.close(fig)
    table(output/'sensitivity/targeted_summary.csv', target_summary); save(output/'sensitivity/targeted_summary.json', target_summary)
    combined = []
    for factor in dict.fromkeys(r['factor'] for r in old4):
        values = sorted({r['value'] for r in old4 if r['factor'] == factor})
        for method in METHODS[1:]:
            for value in values:
                group = [r for r in old4 if r['factor'] == factor and r['value'] == value and r['method'] == method]
                combined.append(dict(source='Step 4 existing 2D', factor=factor, value=value, method=method, cases=len(group),
                                     acceptance_rate=float(np.mean([bool(r['accepted']) for r in group])),
                                     hidden_recall=float(np.mean([r['hidden_recall_2px'] for r in group]))))
    for factor in dict.fromkeys(r['factor'] for r in old5):
        values = sorted({r['value'] for r in old5 if r['factor'] == factor})
        for method in METHODS[1:]:
            for value in values:
                group = [r for r in old5 if r['factor'] == factor and r['value'] == value and r['method'] == method]
                combined.append(dict(source='Step 5 existing 3D', factor=factor, value=value, method=method, cases=len(group),
                                     supported_rmse_m=float(np.mean([r['supported_rmse_m'] for r in group])),
                                     reference_coverage_3cm=float(np.mean([r['reference_coverage_3cm'] for r in group])),
                                     supported_components=float(np.mean([r['supported_components'] for r in group]))))
    table(output/'sensitivity/combined_existing_summary.csv', combined); save(output/'sensitivity/combined_existing_summary.json', combined)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), constrained_layout=True)
    for axis, width in zip(axes, (192, 640)):
        selected = [r for r in runtimes if r['width'] == width]
        axis.barh([r['stage'] for r in selected], [r['median_ms'] for r in selected], color='#168b9a')
        axis.set(title=f'{width} pixel width: warmup=3, repeats=15', xlabel='Median milliseconds')
    if not (output/'figures/stage_runtime.png').exists():fig.savefig(output/'figures/stage_runtime.png', dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    selected = [r for r in summaries(rows) if r['cohort'] == 'independent_holdout' and r['scope'] == 'all_cases']
    for axis, field in zip(axes, ('mean_hidden_added_recall_2px', 'mean_chamfer_3d_m', 'mean_coverage_3cm')):
        axis.bar([r['method'] for r in selected], [r[field] for r in selected], color=['#aaa', '#168b9a', '#ce1689'])
        axis.set(title=field); axis.tick_params(axis='x', rotation=15)
    fig.suptitle('Independent holdout: every method evaluated on the same 48 cases')
    if not (output/'figures/holdout_comparison.png').exists():fig.savefig(output/'figures/holdout_comparison.png', dpi=140)
    plt.close(fig)


def failure_report(output, rows, negatives):
    decisions = load(output/'decisions.json')
    counts = Counter()
    for item in decisions:
        for stage, records in [('detection', item['detection']['rejected']), ('completion', item['rejected']), ('hidden_depth', item['depth_rejections'])]:
            for record in records:
                counts[(item['method'], stage, record['reason'])] += 1
    # Candidate rejection counts are endpoint pairs, not numbers of failed trees.
    table(output/'rejection_reason_counts.csv', [dict(method=m, stage=s, reason=r, rejected_records=n,
                                                      denominator='endpoint pairs / requests / hidden chains, not cases')
                                               for (m, s, r), n in sorted(counts.items())])
    failures = [r for r in rows if r['cohort'] != 'step5_saved' and r['method'] != 'visible_only'
                and (not r['completed'] or r['incorrect_connections'] or r['coverage_3cm'] < .9 or r['depth_rejected_chains'])]
    table(output/'failure_cases.csv', failures); save(output/'failure_cases.json', failures)
    save(output/'negative_summary.json', dict(rows=len(negatives),
         unsafe_foreign_connections=sum(r['incorrect_object_connection'] for r in negatives),
         note='Adversarial foreign-object fixture supplies erroneous identity and permissive region. These methods cannot authenticate wood identity. Not a natural-scene error rate.'))


def md_table(rows, fields):
    return '| '+' | '.join(fields)+' |\n|'+'|'.join('---' for _ in fields)+'|\n'+''.join(
        '| '+' | '.join(f'{r[k]:.6g}' if isinstance(r.get(k), float) else str(r.get(k, '')) for k in fields)+' |\n' for r in rows)


def documentation(output, rows, overall, negatives, runtimes, optimisations, real):
    independent = [r for r in overall if r['cohort'] == 'independent_holdout' and r['scope'] == 'all_cases']
    paired = [r for r in overall if r['cohort'] == 'independent_holdout' and r['scope'] == 'paired_both_completion_accepted']
    own = [r for r in overall if r['cohort'] == 'independent_holdout' and r['scope'] == 'own_accepted_cases']
    fields = ['method', 'cases', 'accepted_cases', 'mean_full_chamfer_px', 'mean_hidden_added_recall_2px',
              'mean_rmse_3d_m', 'mean_chamfer_3d_m', 'mean_coverage_3cm', 'mean_components_3d']
    recommended = []
    for m in METHODS:
        r = next(r for r in independent if r['method'] == m)
        recommended.append(dict(method=m, full_2d_chamfer_px=r['mean_full_chamfer_px'],
            hidden_added_recall_2px=r['mean_hidden_added_recall_2px'], coverage_3cm=r['mean_coverage_3cm'],
            chamfer_3d_m=r['mean_chamfer_3d_m'], accepted=f'{r["accepted_cases"]}/48' if m != 'visible_only' else 'N/A',
            complexity='thinning O(HW I), graph O(V+E)' if m == 'visible_only' else
                       'candidate O(K^2(V+E)) in current tracing; raster+graph checks per request; quadratic adds small least-squares fit',
            interpretability='observed input only; no hidden estimates' if m == 'visible_only' else
                             'straight bridge + explicit hidden Z' if m == 'linear' else 'soft tangent/support constrained quadratic + explicit hidden Z',
            suitability='conservative fallback and reference baseline' if m == 'visible_only' else
                        'simple interpretable completion hypothesis' if m == 'linear' else 'curved/tangent-consistent completion hypothesis',
            components_3d=r['mean_components_3d'],
            runtime_192_ms=next(x['median_ms'] for x in runtimes if x['width']==192 and x['stage']==m+'_mask_to_3d_pipeline'),
            runtime_640_ms=next(x['median_ms'] for x in runtimes if x['width']==640 and x['stage']==m+'_mask_to_3d_pipeline'),
            robustness='all-case and paired/own-accepted scopes; see targeted diagnostics and negative fixtures',
            limitation='incomplete by construction' if m == 'visible_only' else 'occlusion/identity must be trustworthy; single-view hidden geometry uncertain'))
    table(output/'final_method_comparison.csv', recommended); save(output/'final_method_comparison.json', recommended)
    primitives={'skeleton_extraction','pixel_graph','candidate_detection','linear_completion','quadratic_completion',
                'visible_only_3d_lifting','linear_3d_lifting','quadratic_3d_lifting'}
    bottlenecks=[max((r for r in runtimes if r['width']==width and r['stage'] in primitives),key=lambda r:r['median_ms']) for width in (192,640)]
    winner_counts=[]
    for field in ('full_chamfer_px','chamfer_3d_m','hidden_added_recall_2px'):
        pairs=[]
        for a in rows:
            if a['cohort']=='independent_holdout' and a['method']=='linear':
                b=next(x for x in rows if x['cohort']=='independent_holdout' and x['case_id']==a['case_id'] and x['method']=='quadratic')
                if a['completed'] and b['completed']:pairs.append((a[field],b[field]))
        larger=field=='hidden_added_recall_2px'
        winner_counts.append(dict(metric=field,paired_cases=len(pairs),quadratic_better=sum((b>a if larger else b<a) and not np.isclose(a,b,atol=1e-12,rtol=1e-10) for a,b in pairs),
                                  linear_better=sum((a>b if larger else a<b) and not np.isclose(a,b,atol=1e-12,rtol=1e-10) for a,b in pairs),
                                  tied=sum(np.isclose(a,b,atol=1e-12,rtol=1e-10) for a,b in pairs)))
    table(output/'paired_metric_win_counts.csv',winner_counts)
    text = '''# Step 6：最终验证、算法比较与性能优化

范围仅为 Y 树主干与两条主枝。三方法：visible-only、linear、quadratic least-squares。
本次不开始 Step 7、不提交或推送 Git。原 Step 3–5 数值算法完全保留。

## 实验依据与独立性

复用 Step 4 的 180 行（每补全方法 90 设置）和 Step 5 的 150 行深度/标定敏感性结果；独立重新汇总原 JSON，核对旧 summary。
从 Step 5 保存的 15 个图重新计算 3D RMSE、Chamfer、覆盖率；仅 9 个主要方法/场景组合用于三方法集成比较，另外 6 个 measured-only 版本单独保留。
未重新运行原有完整参数扫描。旧速度记录保留原测量范围，不冒充新端到端速度。

旧扫描反复使用少量树形，Step 5 仅三固定场景，无法支持对树形变化的泛化结论。
因此在运行前保存 frozen_experiment_plan.json：48 个新配置（种子 60261025..60261072），固定参数不调优；另有 20 个三维遮挡长度、10 个真实曲率系数诊断配置。
它们不参与方法/阈值调参。48 个配置是同一生成器的新配置，**不是 48 个真实树或统计独立的物理观测**。
树枝角度 25–60 度（相对竖直），三维曲率/姿态随机变化；遮挡位置 t=.22/.45/.72/.9、方形宽10/20/32/48px、主干/左右枝，四种 Z profile；
空间观测噪声0/.35/.8/1.5px、可见深度噪声0/.003/.015m。随机种子独立于旧实验，分组并非全因子设计，不能把因素混合作为单因素效应。
新补全使用原默认 max_gap=80px、angle=65deg、curvature screening=45deg、support=8、tangent_weight=1，未用结果选择参数。
所有新场景的输入、参考、标定与三个输出图均保存，拒绝案例不移除。

## 2D 与 3D 指标及分母

2D 全骨架对称 Chamfer 是预测点与干净栅格参考点双向最近**欧氏距离均值的平均**，单位 px；三方法在同一案例上可比较。
inferred Chamfer 只比较新增点与隐藏参考，未补全时 null。hidden_added_recall_2px 分母是 truth AND occlusion 的固定像素集合；无新增点为0。
另报告使用完整预测（包括可见端点邻域）的 hidden_full_recall_2px，不把它与新增补全召回混用。

3D 坐标为已知合成相机米制，X右/Y下/Z前。原解析三维曲线先投影/栅格化，生成器只将模拟可见深度提供给算法。
RMSE 使用每个有支持预测点到**投影2D最近解析采样点**的3D误差，不是3D最近邻RMSE，包含栅格量化及观测噪声。
3D Chamfer 是有支持预测点与逐栅格参考3D点的双向未平方距离均值平均；coverage 是参考点距预测<=.03m比例。
每例原始行保留预测/参考/隐藏/支持点数，缺失点不作零误差。RMSE对有支持点条件化，方法间点数不同；同时比较 measured RMSE、固定参考 Chamfer/coverage。
聚合为各案例指标的算术均值，不是把不同大小案例混池后算RMSE。每个聚合指标的有效案例数 n_* 明列。

all_cases 使用同一全部案例；own_accepted_cases 使用各自接受集合，因此**不能直接将两个各自接受均值作优劣结论**；
paired_both_completion_accepted 用二者共同接受的同一 case_id 子集，并保留该子集上的 visible-only。
baseline 不尝试补全，acceptance=N/A，而不是失败率100%。候选拒绝的分母是端点对，补全拒绝的分母是请求，案例未补全的分母是场景，三者分别报告。
incorrect_connections 用生成器真实枝条标签判定接受连接两端是否跨角色；incorrect_role_labels另计声明角色错误。
环秩 E-V+C 和分量验证图一致性，不等价于解剖学正确性。

## 独立48配置：全案例比较

'''+md_table(independent, fields)+'''
## 同时接受的配对集合

'''+md_table(paired, fields)+'''
## 各自接受集合（分母不同，仅描述）

'''+md_table(own, fields)+'''
## 负例、失败及工程限制

8 种负例 x 两补全方法，包括无遮挡证据、穿越其他结构、歧义对象、未知角色、超长缺口、错误方向、外国树体对齐片段、深度锚点缺失。
negative_cases.* 保存输入决策及输出，failure_cases.* 包含未补全、低覆盖、错误连接及三维链拒绝案例。
其他树体负例故意提供错误角色声明和可通行区域；几何方法可能连接两棵树的对齐碎片。这是明确的输入真实性/木质身份限制，不能从零环/连通成功推出语义正确。
缺深度锚点可使2D补全成功但隐藏3D仍 unsupported。靠近分叉的遮挡、长缺口、高曲率/噪声会出现检测或显式区域支持拒绝；保守拒绝不是完美重建。
负例不能作为自然果园错误率的估计，正常合成场景的正确连接计数也不能排除真实错误。

## 敏感性与鲁棒性

Step 4 复用方向阈值、支持点数、切向权重、局部切向变化筛选阈值、2D噪声和遮挡宽度扫描。
旧 max_curvature_deg 是**筛选阈值**，不是实际树枝曲率，所以另补三维多项式曲率系数 -.8/-.4/0/.4/.8m、两个枝条角色，共10个目标诊断。
三维遮挡宽度8/16/24/40/64px，两个角色 x 线性/非线性深度，共20个目标诊断，补齐 Step 5 缺少的3D遮挡长度证据。
方形宽度不等于隐藏曲线弧长。现有深度噪声、丢深度、焦距/主点/尺度误差150行仅在旧 varying_z 场景上，联合误差和真实相机误差分布仍未验证。
深度缺失时条件RMSE可很低而覆盖下降、分量上升；必须联合读图。不同单位因素的扫描范围不同，不能据最大值排行推导一般“显著性”。没有进行统计显著性或真实相机不确定性推断。

## 性能与有证据的优化

计时为 perf_counter_ns，预热3次、重复15次；记录每次样本、中位数、p90和最小值。两种合成输入分辨率192x192、640x480。
阶段包括细化、像素图、候选、两种补全、向量反投影、三种完整 lifting，以及每方法 mask+合成depth→3D图的计算流程。
该“计算流程”不包括RGB分割（项目没有自动分割器）、人工标注、校准、读写、绘图和评估；不是原始RGB到机器人模型的端到端系统。
计时与 tracemalloc 单次峰值分开运行；峰值仅为追踪分配，不是总RSS或所有原生库内存。CPU/Python/依赖信息见 performance/environment.json。

'''+md_table([dict(width=r['width'], height=r['height'], stage=r['stage'], median_ms=r['median_ms'], p90_ms=r['p90_ms'], traced_peak_bytes=r['traced_peak_bytes']) for r in runtimes],
            ['width', 'height', 'stage', 'median_ms', 'p90_ms', 'traced_peak_bytes'])+'''
原比较流程三次调用各自细化、两次调用相同候选检测。共享这些只读中间量是比较工作流优化，不改变任何阈值、拟合、像素图、补全或三维算法。
原 infer_one 仍保留作基线；infer_all 分享细化和检测。先记录原流程各阶段成本，再验证相同输入上三方法输出一致，按交替顺序做15对 before/after。
该速度收益只适用于一次比较三方法；不能声称单方法核心算法被加速，也没有实现自适应选择器或调参取胜。

'''+md_table(optimisations, ['width', 'height', 'before_median_ms', 'after_median_ms', 'speedup', 'reduction_fraction', 'equivalence_verified'])+'''
最大单阶段耗时（不包括复合流程，属于本基准而非一般结论）：

'''+md_table(bottlenecks,['width','height','stage','median_ms'])+'''
共享工作流相对原始逐方法流程的回归验证还覆盖全部78配置/234个图：读取保存的可见深度/掩膜/遮挡输入，以原逐方法 infer_one 重放；不调用模拟器，也不读取NPZ中的真值数组，精确检查结构/状态并按Step5容差检查几何。结果见 verification/saved_observation_replay.json。

## 真实12样本：只做定性复核

复用 Step 3 v4 可见草稿与 Step 4 两方法图，逐样本核验RGB哈希、重新检查候选决策及补全图一致性。
图示只有原生640x480像素坐标，非米制三维。所有12标注保持 AI DRAFT/pending，human accepted=0。
R06N02、R08N02、R09N02、R10N02 在表格/图库显式标为 independent manual review required。
R06的短刺/嫁接区、R08新增碎片、R09线材附近枝条、R10近端片段需人在RGB中确认；脚本不修改或批准标注。
没有将未标区域称为确认遮挡，没有使用未核验 Summer GT 对齐或真实3D准确率。因为再分发许可未核实，ZIP和图库不复制原始RGB/深度，仅包含骨架示意及来源/哈希。
木质表面、中轴及叶片/邻树身份仍是实际工程障碍。

## 最终方法选择与工程意义

不宣称普适胜者：visible-only 是保守的可观测参考和无法确认缺口时的回退；linear 简单透明，适合近直线连接假设；quadratic 能表示弯曲并提供软切向一致性，但可能离开受控区域或拟合错误局部方向。
是否改善必须根据上面的同分母配对结果；更高覆盖率可能伴随更大条件误差。不能为了降低误差而删去拒绝案例。
建议交付保留三方法及显式接受/拒绝记录，以 quadratic 作为需要曲率假设时的候选、linear 作为简单基线；未经人工确认的真实缺口不自动补全成事实。没有实现未验证的自动方法选择。
同案例同时接受集合的逐例优胜计数（无统计显著性声明）：

'''+md_table(winner_counts,['metric','paired_cases','quadratic_better','linear_better','tied'])+'''
工程上关键是“改善可解释的补全完整度并能拒绝不支持输入”，不是漂亮的连续图；没有真实校准不能用于毫米定位或机器人避障。

## 复现与验证

从仓库根：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python scripts/evaluate_step6.py --output results/step6_another_run
```

必须使用不存在的新 results 子目录。默认完整运行含所有生成、计时、复核、完整pytest、文档及包创建；若自定义输出，ZIP使用相应输出名加 _review_package.zip。
依赖为 pyproject.toml 的 numpy/Pillow，以及 study matplotlib 和 dev pytest；复用来源路径需存在，不包含在原始数据之外的假造备选值。
tests/ 的新单元测试覆盖距离定义、空预测、分母/配对、共享流程等价、负例、推断接口不接收真值及输出保护。
完整测试日志、JUnit、源码/结果保护清单、PNG和HTML链接检查、git diff --check、ZIP CRC与SHA256验证均保存在本次结果及ZIP旁的完整性记录。
独立重放：`python scripts/replay_step6_saved.py --results results/step6_final_validation`；在解压后的 project/ 运行时改用 `--results ../results`，无需原数据或旧结果。
真实度量校准缺口与 Step 5 最终文档一致；Step 6不修复深度解码或标注真实性。
'''
    write(output/'technical_report.md', text)
    return text


def gallery(output, overall, real, negatives):
    parts = ['<!doctype html><html lang="zh"><meta charset="utf-8"><title>Step 6 final validation</title>',
             '<style>body{font:16px system-ui;background:#101827;color:#eee;margin:25px;line-height:1.5}a{color:#84d5ff}img{max-width:100%;background:white}table{border-collapse:collapse}td,th{border:1px solid #526074;padding:6px}.flag{color:#ff9d9d}</style>',
             '<h1>Step 6：三方法最终验证 / Final validation</h1>',
             '<p>合成：CALIBRATED SYNTHETIC，米制相机坐标。真实：UNCALIBRATED/QUALITATIVE，AI DRAFT，图像像素；没有真实度量3D。</p>',
             '<p><a href="technical_report.md">技术报告</a> · <a href="overall_algorithm_comparison.csv">全案例/接受/配对表</a> · <a href="all_case_metrics.csv">逐案例2D/3D与分母</a> · <a href="performance/stage_runtime.csv">性能</a> · <a href="failure_cases.csv">失败</a> · <a href="negative_cases.csv">负例</a> · <a href="real/qualitative_comparison.csv">真实定性表</a></p>',
             '<h2>独立48配置；拒绝案例保留</h2><img src="figures/holdout_comparison.png" alt="48-case comparison">',
             '<h2>性能：mask/depth 到图，非原始 RGB 系统</h2><img src="figures/stage_runtime.png" alt="stage timing">',
             '<h2>敏感性</h2>']
    for name in ('step4_existing_sensitivity', 'step5_existing_sensitivity', 'depth_dropout_coverage',
                 'targeted_3d_gap', 'targeted_physical_curvature'):
        parts.append(f'<h3>{name}</h3><img src="figures/{name}.png" alt="{name}">')
    parts.append('<h2>独立合成示例与失败案例</h2>')
    for path in sorted((output/'synthetic').glob('*/comparison.png')):
        relative = path.relative_to(output).as_posix()
        parts.append(f'<details><summary>{html.escape(path.parent.name)}</summary><img src="{relative}" alt="synthetic comparison"></details>')
    parts.append('<h2>负例：含几何方法无法验证的外国树体身份</h2>')
    for path in sorted((output/'negative').glob('*.png')):
        parts.append(f'<details><summary>{path.stem}</summary><img src="{path.relative_to(output).as_posix()}" alt="negative fixture"></details>')
    parts.append('<h2>真实样本：全部 AI DRAFT / 无确认遮挡 / 无真实精度指标</h2>')
    for sample in dict.fromkeys(r['sample_id'] for r in real):
        flag = sample in {'R06N02', 'R08N02', 'R09N02', 'R10N02'}
        parts.append(f'<h3 class="{"flag" if flag else ""}">{sample}'+(' — 需独立人工复核' if flag else '')+
                     f'</h3><img src="real/{sample}.png" alt="{sample} qualitative image-pixel skeleton">')
    parts.append('</html>')
    write(output/'index.html', '\n'.join(parts))


def verify_artifacts(output):
    links = []
    for path in output.rglob('*.html'):
        for link in re.findall(r'(?:src|href)="([^"]+)"', path.read_text(encoding='utf-8')):
            if link.startswith(('http:', 'https:', '#')): continue
            if not (path.parent/link).is_file(): raise AssertionError('Missing HTML link: '+link)
            links.append(link)
    pngs = list(output.rglob('*.png'))
    for path in pngs:
        with Image.open(path) as image: image.verify()
    save(output/'verification/artifact_integrity.json', dict(local_html_links=len(links), pngs_decoded=len(pngs), broken_links=[]))


def complete_tests(output):
    environment = os.environ.copy(); environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['PYTHONPATH'] = str(ROOT/'results/test_dependencies')+os.pathsep+str(ROOT/'src')
    temp = Path(tempfile.gettempdir())/('mma3001_step6_tests_'+uuid.uuid4().hex)
    folder = output/'tests'; folder.mkdir()
    command = [sys.executable, '-m', 'pytest', '-v', '-p', 'no:cacheprovider', '--basetemp='+str(temp),
               '--junitxml='+str(folder/'pytest_junit.xml')]
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, encoding='utf-8', errors='replace')
    write(folder/'pytest_output.txt', result.stdout+'\nSTDERR:\n'+result.stderr)
    save(folder/'command.json', dict(command=command, exit_code=result.returncode))
    import xml.etree.ElementTree as ET
    suites = list(ET.parse(folder/'pytest_junit.xml').getroot().iter('testsuite'))
    totals = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    totals['passed'] = totals['tests']-totals['failures']-totals['errors']-totals['skipped']
    save(folder/'totals.json', totals)
    if result.returncode: raise RuntimeError('Full suite failed; see tests/pytest_output.txt')
    return totals


def update_project_docs(output, report, totals):
    # Record original editable project documentation before requested Step 6 updates.
    folder = output/'project_docs_before'; folder.mkdir()
    for name in ('README.md', 'docs/05_development_log.md'):
        target = folder/Path(name).name; shutil.copy2(ROOT/name, target)
    target = ROOT/'docs/16_step6_final_validation.md'
    if target.exists(): raise ValueError('Step 6 document already exists; refusing overwrite')
    final = report+'\n## 本次完整测试\n\n'+json.dumps(totals, ensure_ascii=False)+'\n'
    target.write_text(final, encoding='utf-8')
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    readme = re.sub(r'\*\*Development status:\*\*[^\n]*',
                    '**Development status:** Step 6 - paired synthetic validation and stage profiling; real metric 3D remains unsupported', readme)
    readme = readme.replace('| Occluded-branch completion | Planned |', '| Occluded-branch completion | Implemented: linear and quadratic; synthetic validation, real drafts only |')
    readme = readme.replace('| Full 3D skeleton reconstruction | Planned |', '| Full 3D skeleton reconstruction | Calibrated synthetic lifting implemented; real metric 3D unsupported |')
    readme = readme.replace('| Held-out quantitative model evaluation | Planned |', '| Held-out quantitative model evaluation | Step 6 independent synthetic configurations; human-validated real accuracy remains pending |')
    readme += '\n\n### Step 6 final validation\n\nPaired comparison of visible-only, linear and quadratic methods reuses Step 4/5 evidence and adds 48 independent synthetic configurations, 30 targeted diagnostics, negative cases, stage timings and a shared-preprocessing comparison workflow. All real annotations remain AI DRAFT. No real metric 3D accuracy is claimed. See [Step 6 report](docs/16_step6_final_validation.md), [HTML gallery](results/step6_final_validation/index.html) and [Step 5 calibration findings](docs/step5_calibration_followup.md). Run `python scripts/evaluate_step6.py --output results/step6_new_run` from the repository root using a new directory.\n'
    (ROOT/'README.md').write_text(readme, encoding='utf-8')
    log = ROOT/'docs/05_development_log.md'
    with log.open('a', encoding='utf-8') as stream:
        stream.write('\n\n## 2026-10-25 — Step 6 paired final validation and profiling\n\nReused and checked Step 4/5 numerical evidence. Added 48 frozen-seed synthetic holdout configurations, 30 targeted 3D gap/physical-curvature cases, 8 negative fixtures per completion method, and 192/640-width stage/runtime/memory benchmarks. Shared thinning and detection only across the three-method comparison; original methods retained. Real 12 drafts remain pending, with R06/R08/R09/R10 flagged for independent human review. Full-suite totals: '+json.dumps(totals)+'. See docs/16_step6_final_validation.md and results/step6_final_validation/. No raw/previous-results changes, Step 7, commit or push.\n')


def package_review(output):
    target = ROOT/'results'/('step6_review_package.zip' if output.name == 'step6_final_validation' else output.name+'_review_package.zip')
    if target.exists(): raise ValueError('Existing ZIP preserved; choose new output')
    hashes = {p.relative_to(output).as_posix(): fingerprint(p)['sha256'] for p in sorted(output.rglob('*')) if p.is_file()}
    checksum_path=output/'SHA256SUMS.txt'
    if checksum_path.exists():
        checksum_path=output/'SHA256SUMS_final.txt'
        version=2
        while checksum_path.exists():
            checksum_path=output/f'SHA256SUMS_final_{version}.txt';version+=1
    write(checksum_path, ''.join(h+'  '+name+'\n' for name, h in hashes.items()))
    members={}
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                name='step6_review_package/results/'+path.relative_to(output).as_posix()
                archive.write(path, name);members[name]=fingerprint(path)['sha256']
        for folder in ('src', 'scripts', 'tests', 'docs', 'data/demo', 'data/annotations'):
            for path in sorted((ROOT/folder).rglob('*')):
                if path.is_file() and not any(p in path.parts for p in ('__pycache__', '.pytest_cache')):
                    name='step6_review_package/project/'+path.relative_to(ROOT).as_posix()
                    archive.write(path, name);members[name]=fingerprint(path)['sha256']
        for name in ('README.md', 'pyproject.toml', 'LICENSE', '.gitignore'):
            member_name='step6_review_package/project/'+name
            archive.write(ROOT/name, member_name);members[member_name]=fingerprint(ROOT/name)['sha256']
        readme='# Step 6 review\n\nOpen results/index.html, results/recovery_validation.html, and results/runtime_audit.html when present. Read results/technical_report.md and results/final_verification_addendum.md plus results/performance/runtime_interpretation_audit.md. Source/tests are in project/. No raw RGB-D files included.\n\nFor package tests: install project[study,dev], cd project, PYTHONPATH=src, python -m pytest -p no:cacheprovider.\nReplay all saved new synthetic observations without original data: python scripts/replay_step6_saved.py --results ../results\nSynthetic input/reference and output graphs are self-contained for read-only metric/replay checks. Full evaluator additionally needs the separately preserved Step 3/4/5 result trees in their original project layout; they are not duplicated here.\nAll real examples are AI DRAFT/UNCALIBRATED; no real metric accuracy.\nFinal results checksum manifest: '+checksum_path.name+'. Earlier manifests are preserved historical build records. ZIP_MEMBER_SHA256.json covers all other members.\n'
        archive.writestr('step6_review_package/README.md',readme)
        members['step6_review_package/README.md']=hashlib.sha256(readme.encode('utf-8')).hexdigest()
        # Hash source bytes during writing; only read the archive AFTER closing.
        # On Windows a still-open writer may retain backslashes in ZipInfo.orig_filename.
        archive.writestr('step6_review_package/ZIP_MEMBER_SHA256.json', json.dumps(members, indent=2))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for name, digest in members.items(): assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        count = len(archive.infolist())
    save(target.with_suffix('.zip.integrity.json'), dict(sha256=fingerprint(target)['sha256'], bytes=target.stat().st_size,
         members=count, crc_ok=True, member_sha256_ok=True, results_checksum_manifest=checksum_path.name,
         note='SHA256 manifest excludes itself; no environments/caches/raw RGB-D'))
    return target


def run(output):
    return run_or_resume(output, resume=False)


def run_or_resume(output, resume=False):
    import matplotlib
    matplotlib.use('Agg')
    output = Path(output).resolve()
    if (output.exists() and not resume) or not output.is_relative_to(ROOT/'results'):
        raise ValueError('Choose a new output directory below repository results/')
    author_project_docs = not (ROOT/'docs/16_step6_final_validation.md').exists()
    if resume:
        if not (output/'verification/preservation_before.json').is_file() or not (output/'frozen_experiment_plan.json').is_file():
            raise ValueError('No compatible interrupted run to resume')
        manifest=load(output/'verification/preservation_before.json')
        old_plan=load(output/'frozen_experiment_plan.json')
        if old_plan['configs']!=experiment_configs() or old_plan['settings']!=SETTINGS:
            raise ValueError('Frozen plan changed; cannot resume')
    else:
        manifest = {}
        for base in (ROOT/'data', ROOT/'results', ROOT/'src', ROOT/'tests', ROOT/'scripts'):
            for path in sorted(base.rglob('*')):
                if path.is_file() and not any(part in path.parts for part in ('test_dependencies', '__pycache__', '.pytest_cache')):
                    manifest[path.relative_to(ROOT).as_posix()] = fingerprint(path)
        output.mkdir(parents=True); (output/'figures').mkdir()
        save(output/'verification/preservation_before.json', manifest)
    if not (output/'reproducibility.json').exists():
        save(output/'reproducibility.json', dict(executed_utc=datetime.now(timezone.utc).isoformat(), root=str(ROOT),
        command=sys.argv, git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        seed=SEED, inference_settings=SETTINGS, scope='main trunk and two primary branches only',
        gt_boundary='reference arrays used only in simulation and metric functions; inference signature excludes truth/reference'))
    print('Step 6: verifying/reusing existing evidence', flush=True)
    reused, old4, old5 = reuse_existing(output)
    print('Step 6: new frozen independent/targeted cases', flush=True)
    rows = load(output/'all_case_metrics.json') if (output/'all_case_metrics.json').exists() else reused+new_experiments(output)
    table(output/'all_case_metrics.csv', rows); save(output/'all_case_metrics.json', rows)
    table(output/'2d_accuracy_comparison.csv', [{k: v for k, v in r.items() if k in ('case_id', 'cohort', 'method', 'completed', 'hidden_reference_points', 'full_chamfer_px', 'inferred_chamfer_px', 'hidden_added_recall_2px', 'hidden_full_recall_2px', 'incorrect_connections', 'incorrect_role_labels', 'components_2d')} for r in rows])
    table(output/'3d_accuracy_coverage.csv', [{k: v for k, v in r.items() if k in ('case_id', 'cohort', 'method', 'completed', 'supported_points', 'reference_3d_points', 'rmse_3d_m', 'measured_rmse_m', 'inferred_rmse_m', 'chamfer_3d_m', 'coverage_3cm', 'components_3d', 'cycle_rank_3d', 'unsupported_points')} for r in rows])
    overall = summaries(rows); table(output/'overall_algorithm_comparison.csv', overall); save(output/'overall_algorithm_comparison.json', overall)
    negatives = ([{k:v for k,v in r.items() if k not in ('requests','detection','graph3d')} for r in load(output/'negative_cases.json')]
                 if (output/'negative_cases.json').exists() else negative_experiments(output))
    failure_report(output, rows, negatives)
    print('Step 6: read-only real draft replay', flush=True)
    real = load(output/'real/qualitative_comparison.json') if (output/'real/qualitative_comparison.json').exists() else real_review(output)
    print('Step 6: stage profiling and paired workflow benchmark', flush=True)
    if (output/'performance/stage_runtime.json').exists() and (output/'performance/comparison_workflow_optimisation.json').exists() and (output/'performance/environment.json').exists():
        runtimes=load(output/'performance/stage_runtime.json');optimisations=load(output/'performance/comparison_workflow_optimisation.json')
    else:
        runtimes, optimisations = performance(output)
    plots(output, rows, old4, old5, runtimes)
    report = documentation(output, rows, overall, negatives, runtimes, optimisations, real)
    gallery(output, overall, real, negatives)
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONPATH']=str(ROOT/'src')
    if not (output/'verification/saved_observation_replay.json').exists():
        replay=subprocess.run([sys.executable,str(ROOT/'scripts/replay_step6_saved.py'),'--results',str(output),
                           '--report',str(output/'verification/saved_observation_replay.json')],cwd=ROOT,env=env,
                          capture_output=True,text=True,encoding='utf-8',errors='replace')
        write(output/'verification/saved_observation_replay.txt',replay.stdout+'\nSTDERR:\n'+replay.stderr)
        if replay.returncode:raise RuntimeError('Saved observation replay failed')
    totals = load(output/'tests/totals.json') if (output/'tests/totals.json').exists() else complete_tests(output)
    allowed_changes={'scripts/evaluate_step6.py','tests/test_step6_evaluation.py'} if resume else set()
    changed = [name for name, value in manifest.items() if name not in allowed_changes and fingerprint(ROOT/name) != value]
    save(output/'verification/preservation_after.json', dict(protected_files=len(manifest)-len(allowed_changes), changed_files=changed,
         allowed_new_step6_source_updates=sorted(allowed_changes)))
    if changed: raise AssertionError('Protected files changed')
    if author_project_docs:
        update_project_docs(output, report, totals)
    result = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
    write(output/'verification/git_diff_check.txt', f'Exit code {result.returncode}\n'+result.stdout+result.stderr)
    if result.returncode: raise RuntimeError('git diff --check failed')
    verify_artifacts(output)
    target = package_review(output)
    print(json.dumps(dict(output=str(output), zip=str(target), tests=totals, protected_files=len(manifest)), indent=2), flush=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'results/step6_final_validation')
    parser.add_argument('--resume',action='store_true',help='Continue a matching interrupted output; equal existing files stay untouched')
    parser.add_argument('--positive-completion-benchmark',action='store_true',help='Only new successful-fit timings using saved Step 5 inputs')
    args=parser.parse_args()
    if args.positive_completion_benchmark:
        print(json.dumps(run_positive_completion_audit(args.output),indent=2))
    else:
        run_or_resume(args.output,args.resume)
