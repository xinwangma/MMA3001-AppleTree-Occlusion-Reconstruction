"""Step 6.1: development-first fork-anchored matching study with frozen evaluation.

All old evidence is read-only. New observations use the Step 6 simulator and
therefore test new configurations, not independent real trees or generators.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import numpy as np
from PIL import Image, ImageDraw
from apple_tree_project.baseline import thin_visible
from apple_tree_project.completion import complete_gaps
from apple_tree_project.matching import detect_anchored_gaps, POLICY
from apple_tree_project.reconstruction3d import lift_skeleton

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/step61_fork_matching'
OLD=ROOT/'results/step6_final_validation_v2_boundary_policy'
spec=importlib.util.spec_from_file_location('step6',ROOT/'scripts/evaluate_step6.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
METHODS=('visible_only','linear','quadratic','anchored_linear','anchored_quadratic')
FIELDS=('hidden_added_recall_2px','hidden_full_recall_2px','full_chamfer_px','chamfer_3d_m','coverage_3cm')


def digest(path):
    return hashlib.file_digest(Path(path).open('rb'),'sha256').hexdigest()


def protected():
    paths=list((ROOT/'data/raw').rglob('*'))+list((ROOT/'results').rglob('*'))
    return {str(p.relative_to(ROOT)):dict(sha256=digest(p),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns)
            for p in paths if p.is_file() and OUT not in p.parents and 'test_dependencies' not in p.parts}


def verify_protected():
    before=s.load(OUT/'protected_before.json')
    differences=[name for name,v in before.items() if not (ROOT/name).exists()
                 or dict(sha256=digest(ROOT/name),size=(ROOT/name).stat().st_size,
                         mtime_ns=(ROOT/name).stat().st_mtime_ns)!=v]
    if differences: raise AssertionError(differences)
    return dict(files_checked=len(before),sha256_size_mtime_unchanged=True)


def category(reason):
    low=reason.lower()
    if 'distance' in low or 'length outside' in low: return 'distance'
    if 'direction' in low or 'tangent' in low or 'vertical' in low or 'outward' in low: return 'direction'
    if 'curvature' in low: return 'curvature'
    if 'identity' in low or 'ambiguous_multiple' in low or 'roles' in low: return 'branch_identity'
    if 'occlusion' in low or 'image grid' in low: return 'occlusion_mask'
    if any(w in low for w in ('fork','topology','bridge','tree','anchor')): return 'topology'
    return 'visible_support_or_other'


def infer(visible,depth,camera,occlusion,method):
    if method in s.METHODS:
        return s.infer_one(visible,depth,camera,visible,occlusion,method)
    skeleton=thin_visible(visible)
    detection=detect_anchored_gaps(skeleton,**POLICY)
    result=complete_gaps(skeleton,detection['candidates'],occlusion,method.removeprefix('anchored_'),
                         max_gap_px=80.,max_angle_deg=65.,support_points=12)
    result['detection']=detection
    result['graph3d']=lift_skeleton(result['graph'],depth,camera,visible,infer_hidden_depth=True)
    return result


def config_list(prefix,seed,count):
    configs=[]
    for i in range(count):
        rng=np.random.default_rng(seed+10000+i)
        configs.append(dict(case_id=f'{prefix}_{i:03d}',cohort=prefix,seed=seed+i,
            occluded_role=('trunk','left_primary','right_primary')[i%3],
            occlusion_t=float(rng.choice([.22,.45,.72,.9])),gap_width_px=int(rng.choice([10,20,32,48])),
            depth_profile=str(rng.choice(['constant','linear','nonlinear','steep'])),
            observation_noise_px=float(rng.choice([0.,.35,.8,1.5])),
            depth_noise_m=float(rng.choice([0.,.003,.015]))))
    return configs


def figure(visible,truth,results,path,title,rgb=None):
    h,w=visible.shape; canvas=Image.new('RGB',(w*len(results),h+42),'#f8fafc')
    draw=ImageDraw.Draw(canvas)
    for j,(method,result) in enumerate(results.items()):
        base=np.zeros((h,w,3),dtype=np.uint8)+245
        if rgb is not None: base=np.asarray(rgb.convert('RGB')).copy()
        elif truth is not None: base[truth]=[160,160,160]
        base[visible]=[0,145,155];base[result['inferred_mask']]=[215,20,135]
        canvas.paste(Image.fromarray(base),(j*w,42))
        draw.text((j*w+3,20),f'{method}: {len(result["accepted"])} accepted',fill='black')
    draw.text((4,3),title,fill='black');canvas.save(path)


def summarize(rows):
    result=[]
    for cohort in dict.fromkeys(r['cohort'] for r in rows):
        for method in METHODS:
            group=[r for r in rows if r['cohort']==cohort and r['method']==method]
            if not group: continue
            item=dict(cohort=cohort,method=method,cases=len(group),accepted_cases=sum(r['completed'] for r in group),
                      correct_connections=sum(r['accepted_requests']-r['incorrect_connections'] for r in group),
                      incorrect_connections=sum(r['incorrect_connections'] for r in group),
                      incorrect_role_labels=sum(r['incorrect_role_labels'] for r in group),
                      median_runtime_ms=float(np.median([r['runtime_ms'] for r in group])),
                      median_detector_ms=float(np.median([r['detector_ms'] for r in group])))
            for field in FIELDS:
                values=[r[field] for r in group if r[field] is not None]
                item['mean_'+field]=float(np.mean(values)) if values else None
                item['n_'+field]=len(values)
            result.append(item)
    return result


def run_cases(configs,folder):
    rows=[];logs=[]
    folder.mkdir()
    for index,config in enumerate(configs):
        scene=s.make_scene(config);results={};times={};detector_times={}
        # Warm each method; cyclic timing order reduces fixed position bias.
        for method in METHODS:
            infer(scene['visible'],scene['depth'],scene['camera'],scene['occlusion'],method)
        samples={m:[] for m in METHODS}
        for repeat in range(3):
            order=list(METHODS);shift=(index+repeat)%len(order);order=order[shift:]+order[:shift]
            for method in order:
                start=time.perf_counter_ns()
                result=infer(scene['visible'],scene['depth'],scene['camera'],scene['occlusion'],method)
                samples[method].append((time.perf_counter_ns()-start)/1e6);results[method]=result
        skel=thin_visible(scene['visible'])
        for method in METHODS:
            detector_times[method]=[]
            if method=='visible_only': detector_times[method]=[0.]
            else:
                for _ in range(3):
                    start=time.perf_counter_ns()
                    (detect_anchored_gaps(skel,**POLICY) if method.startswith('anchored') else s.detect_candidate_gaps(skel,**s.SETTINGS))
                    detector_times[method].append((time.perf_counter_ns()-start)/1e6)
        measured,decisions=s.evaluate_scene(scene,results,config['case_id'],config['cohort'])
        for row in measured:
            row.update(runtime_ms=float(np.median(samples[row['method']])),runtime_samples_ms=samples[row['method']],
                       detector_ms=float(np.median(detector_times[row['method']])))
        rows.extend(measured);logs.extend(decisions)
        case=folder/config['case_id'];case.mkdir()
        np.savez_compressed(case/'inputs_and_reference.npz',**{k:scene[k] for k in
            ('visible','depth','occlusion','truth','reference_xyz','analytic_xyz','analytic_uv','analytic_role')})
        s.save(case/'calibration.json',asdict(scene['camera']))
        for method,result in results.items():
            s.save(case/f'{method}_graph3d.json',result['graph3d'])
        figure(scene['visible'],scene['truth'],results,case/'comparison.png',config['case_id'])
        if (index+1)%12==0: print(f'{config["cohort"]}: {index+1}/{len(configs)}',flush=True)
    s.save(folder/'metrics.json',rows);s.table(folder/'metrics.csv',rows);s.save(folder/'decisions.json',logs)
    s.save(folder/'summary.json',summarize(rows));s.table(folder/'summary.csv',summarize(rows))
    return rows,logs


def historical_audit():
    decisions=s.load(OLD/'decisions.json')
    metrics=s.load(OLD/'all_case_metrics.json')
    pairs=[];cases=[]
    for d in decisions:
        if not d['case_id'].startswith('holdout') or d['method'] not in ('linear','quadratic'): continue
        reasons=[r['reason'] for r in d['detection']['rejected']]+[r['reason'] for r in d['rejected']]
        counts=Counter(reasons)
        pairs.extend(dict(case_id=d['case_id'],method=d['method'],stage=stage,category=category(r['reason']),**r)
                     for stage,records in [('detection',d['detection']['rejected']),('completion',d['rejected'])] for r in records)
        cases.append(dict(case_id=d['case_id'],method=d['method'],accepted=bool(d['accepted']),
                          rejected_pair_reasons=dict(counts),categories_present=sorted({category(r) for r in reasons}),
                          note='Multiple categories per case; pair reasons are ordered first failures, not causal case attribution'))
    s.save(OUT/'historical_case_audit.json',cases);s.table(OUT/'historical_pair_rejections.csv',pairs)
    s.save(OUT/'historical_rejection_totals.json',dict(
        pairs_per_method={m:dict(Counter(r['category'] for r in pairs if r['method']==m)) for m in ('linear','quadratic')},
        cases_with_category_per_method={m:dict(Counter(c for r in cases if r['method']==m for c in r['categories_present'])) for m in ('linear','quadratic')},
        accepted_per_method={m:sum(r['accepted'] for r in cases if r['method']==m) for m in ('linear','quadratic')}))
    wrong=[r for r in metrics if r['incorrect_connections']]
    folder=OLD/'synthetic/holdout_39'
    with np.load(folder/'inputs_and_reference.npz') as z: arrays={k:z[k] for k in z.files}
    camera=s.Calibration(**s.load(folder/'calibration.json'))
    results={m:infer(arrays['visible'],arrays['depth'],camera,arrays['occlusion'],m) for m in METHODS}
    labels=[]
    for d in decisions:
        if d['case_id']=='holdout_39' and d['accepted']:
            for r in d['accepted']:
                endpoint_labels=[int(arrays['analytic_role'][np.argmin(np.sum((arrays['analytic_uv']-p)**2,axis=1))]) for p in (r['start'],r['end'])]
                labels.append(dict(method=d['method'],start=r['start'],end=r['end'],declared_branch=r['branch'],true_role_indices=endpoint_labels))
    s.save(OUT/'holdout39_investigation.json',dict(old_metrics=wrong,endpoint_labels=labels,
        improved_detection=results['anchored_quadratic']['detection'],
        improved_accepted=results['anchored_quadratic']['accepted'],
        interpretation='Occlusion near the fork removes identity evidence. Equal image-axis labels plus a cycle-free bridge do not imply a common anatomical branch.'))
    figure(arrays['visible'],arrays['truth'],results,OUT/'holdout39.png','Historical failure: diagnostic only, not new evaluation')


def real_review():
    logs=[];tiles=[]
    source=ROOT/'results/step3_real_validation/coverage_revision_v4/run'
    folder=OUT/'real';folder.mkdir()
    for path in sorted(source.glob('R*/annotation.json')):
        annotation=s.load(path);sid=annotation['sample_id'];visible=np.asarray(Image.open(path.parent/'skeleton.png'))>0
        rgb_path=ROOT/annotation['rgb_path']
        assert digest(rgb_path)==annotation['rgb_sha256']
        rgb=Image.open(rgb_path).convert('RGB');results={}
        for method in METHODS:
            if method=='visible_only': result=s.baseline_result(visible);detection=dict(candidates=[],rejected=[])
            else:
                detection=(detect_anchored_gaps(visible,**dict(POLICY,max_gap_px=100.)) if method.startswith('anchored')
                           else s.detect_candidate_gaps(visible,max_gap_px=100.))
                result=complete_gaps(visible,detection['candidates'],~visible,method.removeprefix('anchored_'),
                                     max_gap_px=100.,support_points=12 if method.startswith('anchored') else 8)
            result['detection']=detection;results[method]=result
        # Complement-of-mask is an unverified display carrier, never occlusion evidence.
        figure(visible,None,results,folder/f'{sid}.png',sid+' | AI DRAFT; hypotheses only; no calibrated 3D',rgb)
        logs.append(dict(sample_id=sid,rgb_sha256=annotation['rgb_sha256'],notes=annotation['notes'],
             annotation_status=annotation['review_status'],verified_ground_truth=False,confirmed_occlusion=False,
             metric_3d=False,manual_review_required=True,
             methods={m:dict(accepted=r['accepted'],rejected=r['rejected'],detection=r['detection']) for m,r in results.items()}))
        tiles.append(Image.open(folder/f'{sid}.png').resize((1280,209)))
    sheet=Image.new('RGB',(1280,209*len(tiles)),'white')
    for i,tile in enumerate(tiles):sheet.paste(tile,(0,i*209))
    sheet.save(folder/'contact_sheet.png');s.save(folder/'qualitative_review.json',logs)
    return logs


def replay(configs):
    spec=importlib.util.spec_from_file_location('policy',ROOT/'scripts/replay_saved_synthetic.py')
    policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
    count=0
    for config in configs:
        folder=OUT/'evaluation'/config['case_id']
        with np.load(folder/'inputs_and_reference.npz') as z:
            visible,depth,occlusion=[z[k] for k in ('visible','depth','occlusion')]
        camera=s.Calibration(**s.load(folder/'calibration.json'))
        for method in METHODS:
            actual=json.loads(json.dumps(infer(visible,depth,camera,occlusion,method)['graph3d']))
            policy.compare_graphs(actual,s.load(folder/f'{method}_graph3d.json'));count+=1
    return dict(graphs_checked=count,reference_arrays_read=False,simulator_called=False,
                exact_topology_identity_status=True,atol=policy.ATOL,rtol=policy.RTOL)


def finish(rows,logs,real):
    summary=summarize(rows);s.save(OUT/'comparison_summary.json',summary);s.table(OUT/'comparison_summary.csv',summary)
    reason_rows=[]
    for method in METHODS:
        records=[(stage,r) for d in logs if d['method']==method
                 for stage,items in [('detection',d['detection']['rejected']),('completion',d['rejected'])] for r in items]
        reason_rows.extend(dict(method=method,stage=stage,reason=reason,category=category(reason),count=count)
                           for (stage,reason),count in Counter((stage,r['reason']) for stage,r in records).items())
    s.table(OUT/'rejection_reasons.csv',reason_rows)
    paired=[]
    for baseline,new in [('linear','anchored_linear'),('quadratic','anchored_quadratic')]:
        old={r['case_id']:r for r in rows if r['method']==baseline};newrows={r['case_id']:r for r in rows if r['method']==new}
        ids=[i for i in old if old[i]['completed'] and newrows[i]['completed']]
        paired.append(dict(baseline=baseline,improved=new,paired_accepted_cases=len(ids),
            gained_cases=[i for i in old if not old[i]['completed'] and newrows[i]['completed']],
            lost_cases=[i for i in old if old[i]['completed'] and not newrows[i]['completed']],
            paired_mean_deltas={f:float(np.mean([newrows[i][f]-old[i][f] for i in ids])) if ids else None for f in FIELDS}))
    s.save(OUT/'paired_comparison.json',paired)
    headers=['method','cases','accepted_cases','correct_connections','incorrect_connections','incorrect_role_labels']+['mean_'+f for f in FIELDS]+['median_runtime_ms','median_detector_ms']
    table='<table><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r[h]))+'</td>' for h in headers)+'</tr>' for r in summary)+'</table>'
    figures=''.join(f'<article><h2>{c["case_id"]}</h2><img loading="lazy" src="evaluation/{c["case_id"]}/comparison.png"></article>' for c in s.load(OUT/'frozen_plan.json')['evaluation'])
    figures+=''.join(f'<article><h2>{r["sample_id"]}: AI DRAFT / human review required</h2><p>{html.escape(r["notes"])}</p><img loading="lazy" src="real/{r["sample_id"]}.png"></article>' for r in real)
    s.write(OUT/'index.html','<!doctype html><meta charset="utf-8"><title>Step 6.1 matching study</title><style>body{font:15px/1.5 system-ui;margin:24px}img{max-width:100%}table{border-collapse:collapse;display:block;overflow:auto}td,th{border:1px solid #ccc;padding:7px}article{margin:32px 0}</style><h1>Step 6.1 fork-anchored matching</h1><p>Gray: synthetic reference; cyan: observed skeleton; magenta: inferred hypothesis. Columns: visible, Linear, Quadratic, anchored Linear, anchored Quadratic.</p><p>New seeds from the same simulator; 24 development cases and 96 frozen evaluation cases. All-case means include refusals. Runtime: thinning + detection + completion + 3D lifting, excluding I/O/metrics; median of 3 after warmup. No real accuracy or camera calibration claim. Real display uses mask complement as an UNVERIFIED hypothesis carrier, not confirmed occlusion.</p><p><a href="technical_report.md">Report</a> | <a href="comparison_summary.csv">Metrics</a> | <a href="rejection_reasons.csv">Rejections</a> | <a href="paired_comparison.json">Paired comparison</a></p>'+table+'<h2>Historical incorrect connection</h2><img src="holdout39.png">'+figures)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['develop','evaluate']);args=parser.parse_args()
    if args.phase=='develop':
        OUT.mkdir(exist_ok=False)
        s.save(OUT/'git_status_before.json',dict(status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)))
        s.save(OUT/'protected_before.json',protected())
        plan=dict(policy=POLICY,development=config_list('development',61261025,24),evaluation=config_list('evaluation',62261025,96),
             method='fork-anchored matching + 12-point half-window continuity; unchanged linear/quadratic fitters',
             baseline_sha256=digest(ROOT/'src/apple_tree_project/completion.py'),
             matching_sha256=digest(ROOT/'src/apple_tree_project/matching.py'),
             design_rule='No tuning on old holdout or new evaluation. New evaluation stays unopened until development is complete.',
             scope='Independent seeds/configurations from the SAME simulator, not independent real trees.')
        s.save(OUT/'frozen_plan.json',plan);historical_audit()
        rows,logs=run_cases(plan['development'],OUT/'development')
        s.save(OUT/'development_complete.json',dict(matching_sha256=plan['matching_sha256'],settings_changed=False,summary=summarize(rows)))
    else:
        plan=s.load(OUT/'frozen_plan.json');dev=s.load(OUT/'development_complete.json')
        assert digest(ROOT/'src/apple_tree_project/matching.py')==dev['matching_sha256']==plan['matching_sha256']
        assert digest(ROOT/'src/apple_tree_project/completion.py')==plan['baseline_sha256']
        rows,logs=run_cases(plan['evaluation'],OUT/'evaluation')
        real=real_review();finish(rows,logs,real)
        s.save(OUT/'saved_observation_replay.json',replay(plan['evaluation']))
        s.save(OUT/'protection_verification.json',verify_protected())
    print(json.dumps(summarize(rows),indent=2),flush=True)


if __name__=='__main__':main()
