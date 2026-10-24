"""Reproducible synthetic Y study and draft-only real RGB hypothesis gallery."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw
from apple_tree_project.baseline import pixel_graph, thin_visible
from apple_tree_project.completion import complete_gaps, detect_candidate_gaps, _trace, _tangent

ROOT=Path(__file__).resolve().parents[1]


def raster(points, size=(192,192)):
    image=Image.new('1',size)
    ImageDraw.Draw(image).line([tuple(p) for p in np.rint(points).astype(int)],fill=1)
    return np.asarray(image,dtype=bool)


def synthetic_y(branch='left_primary', gap_length=24, noise=0., seed=0):
    """Known analytic Y geometry; rectangular controlled occlusion on one arm.

    Noise is smooth transverse displacement of the observed centerline in pixels;
    clean ground truth is returned only to the evaluation code.
    """
    t=np.linspace(0,1,801)
    definitions={'trunk':([96,172],[96,105],[8,0]),
                 'left_primary':([96,105],[25,20],[0,70]),
                 'right_primary':([96,105],[167,20],[0,-45])}
    whole=np.zeros((192,192),bool);observed=whole.copy();curves={}
    rng=np.random.default_rng(seed)
    for role,(a,b,c) in definitions.items():
        a,b,c=map(lambda p:np.array(p,float),(a,b,c))
        curve=a+t[:,None]*(b-a)+(t*(t-1))[:,None]*c
        curves[role]=curve
        whole |= raster(curve)
        delta=b-a;normal=np.array([-delta[1],delta[0]])/np.linalg.norm(delta)
        phase=rng.uniform(0,2*np.pi)
        displacement=noise*np.sin(4*np.pi*t+phase)*np.sin(np.pi*t)
        observed |= raster(curve+displacement[:,None]*normal)
    curve=curves[branch]
    midpoint=curve[400]
    # Square occluder width is the controlled length parameter in image pixels.
    half=gap_length/2
    yy,xx=np.indices(whole.shape)
    occlusion=(abs(xx-midpoint[0])<=half)&(abs(yy-midpoint[1])<=half)
    # Raster overlap at the Y junction can form a 2x2 block. Use the same
    # Step 3 thinning on the synthetic input/reference before introducing gaps.
    whole=thin_visible(whole)
    visible=thin_visible(observed) & ~occlusion
    return visible,occlusion,whole,curves


def distances(a,b):
    a,b=np.asarray(a,float),np.asarray(b,float)
    if not len(a) or not len(b):return np.array([])
    return np.concatenate([np.sqrt(((p[:,None]-b[None,:])**2).sum(axis=2)).min(axis=1)
                           for p in np.array_split(a,max(1,len(a)//256))])


def measure(visible,occlusion,truth,result):
    hidden=truth&occlusion
    pred=np.argwhere(result['inferred_mask']);target=np.argwhere(hidden)
    forward,backward=distances(pred,target),distances(target,pred)
    graph=result['graph']
    tangent_errors=[];endpoint_errors=[]
    vg=pixel_graph(visible)
    lookup={(n['x'],n['y']):n['id'] for n in vg['nodes']}
    for r in result['accepted']:
        a,b=np.asarray(r['start']),np.asarray(r['end'])
        c=np.asarray(r['quadratic_coefficient']);delta=b-a
        for point,derivative,outward in ((a,delta-c,1),(b,delta+c,-1)):
            tangent=_tangent(_trace(vg,lookup[tuple(point)],8))*outward
            cosine=np.clip(tangent@derivative/np.linalg.norm(derivative),-1,1)
            tangent_errors.append(math.degrees(math.acos(float(cosine))))
        curve=np.asarray(r['curve_xy'])
        endpoint_errors.extend([float(np.linalg.norm(curve[0]-a)),float(np.linalg.norm(curve[-1]-b))])
    false_pixels=int((forward>3).sum())
    return dict(completion_chamfer_px=float((forward.mean()+backward.mean())/2) if len(forward) else None,
                hidden_recall_2px=float((backward<=2).mean()) if len(backward) else 0.,
                false_inferred_pixels_over_3px=false_pixels,
                false_inferred_pixel_fraction=float(false_pixels/len(pred)) if len(pred) else 0.,
                mean_tangent_error_deg=float(np.mean(tangent_errors)) if tangent_errors else None,
                max_endpoint_error_px=max(endpoint_errors) if endpoint_errors else None,
                components=len(graph['components']),cycle_rank=len(graph['edges'])-len(graph['nodes'])+len(graph['components']),
                junction_pixels=len(graph['junction_pixel_ids']),
                connected=len(graph['components'])==1,
                visible_preserved=bool(np.all(result['skeleton'][visible])),
                accepted=len(result['accepted']),rejected=len(result['rejected']))


def sensitivity_report(records, sweeps, output):
    """Keep acceptance and conditional error separate; compare matched cases."""
    rows=[]
    for factor,values in sweeps.items():
        for value in values:
            for method in ('linear','quadratic'):
                group=[r for r in records if r['factor']==factor and r['value']==value and r['method']==method]
                valid=[r for r in group if r['completion_chamfer_px'] is not None]
                rows.append(dict(factor=factor,value=value,method=method,
                    completion_rate=len(valid)/len(group),
                    mean_error_px=float(np.mean([r['completion_chamfer_px'] for r in valid])) if valid else None,
                    mean_recall_2px=float(np.mean([r['hidden_recall_2px'] for r in group])),
                    mean_tangent_error_deg=float(np.mean([r['mean_tangent_error_deg'] for r in valid])) if valid else None))
    paired=[]
    for a in records[::2]:
        b=next(r for r in records if r['factor']==a['factor'] and r['value']==a['value'] and r['branch']==a['branch'] and r['method']=='quadratic')
        if a['completion_chamfer_px'] is not None and b['completion_chamfer_px'] is not None:
            paired.append((a,b))
    matched=dict(cases=len(paired))
    for method,index in (('linear',0),('quadratic',1)):
        matched[method]={key:float(np.mean([p[index][key] for p in paired])) for key in
                        ('completion_chamfer_px','mean_tangent_error_deg','hidden_recall_2px')}
    (output/'sensitivity.json').write_text(json.dumps(dict(rows=rows,matched_cases=matched),indent=2),encoding='utf-8')
    # Matplotlib is optional for inference; the study exports a standalone figure.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(2,3,figsize=(14,8),constrained_layout=True)
    for axis,(factor,values) in zip(axes.flat,sweeps.items()):
        for method in ('linear','quadratic'):
            group=[r for r in rows if r['factor']==factor and r['method']==method]
            axis.plot(values,[r['mean_recall_2px'] for r in group],marker='o',label=method)
        axis.set(title=factor,xlabel=factor,ylabel='Hidden recall within 2 px')
        axis.set_ylim(-.05,1.05);axis.grid(alpha=.3)
    axes.flat[0].legend()
    figure.suptitle('Synthetic Y-tree one-factor sensitivity (3 branch cases per setting)')
    figure.savefig(output/'sensitivity.png',dpi=150);plt.close(figure)
    return rows,matched


def panels(background,visible,results,path,truth=None):
    w,h=background.size
    labels=['RGB / synthetic reference','Visible skeleton','Linear hypothesis','Quadratic hypothesis']
    canvas=Image.new('RGB',(w*4,h+42),'#111827')
    for k,label in enumerate(labels):
        panel=np.array(background.convert('RGB')).copy()
        if k>0:panel[visible]=[0,230,255]
        if k>1:panel[results[['linear','quadratic'][k-2]]['inferred_mask']]=[255,50,170]
        if k==0 and truth is not None:panel[truth]=[230,230,230]
        canvas.paste(Image.fromarray(panel),(k*w,42))
        ImageDraw.Draw(canvas).text((k*w+5,8),label,fill='white')
    canvas.save(path)


def run(output):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'results') or output.exists():
        raise ValueError('Use a new directory below results')
    output.mkdir(parents=True)
    synthetic=output/'synthetic';synthetic.mkdir()
    records=[];images=[]
    # One-factor-at-a-time, with all other parameters held at the base values.
    sweeps={'gap_length':[8,16,24,40,64], 'max_angle_deg':[20,35,50,65,80],
            'noise':[0.,.5,1.,2.,4.], 'tangent_weight':[.1,.5,1.,4.,10.],
            'support_points':[3,5,8,12,16], 'max_curvature_deg':[10,25,45,70,100]}
    for factor,values in sweeps.items():
        for value in values:
            for role in ('trunk','left_primary','right_primary'):
                settings=dict(gap_length=24,noise=0.,max_angle_deg=65.,tangent_weight=1.,support_points=8,max_curvature_deg=45.)
                settings[factor]=value
                visible,occlusion,truth,_=synthetic_y(role,settings['gap_length'],settings['noise'],seed=42)
                detection=detect_candidate_gaps(visible,max_gap_px=100,max_angle_deg=settings['max_angle_deg'],
                    support_points=settings['support_points'],max_curvature_deg=settings['max_curvature_deg'])
                results={}
                for method in ('linear','quadratic'):
                    durations=[]
                    for repeat in range(3):
                        start=time.perf_counter()
                        result=complete_gaps(visible,detection['candidates'],occlusion,method,max_gap_px=100,
                            max_angle_deg=settings['max_angle_deg'],support_points=settings['support_points'],tangent_weight=settings['tangent_weight'])
                        durations.append(time.perf_counter()-start)
                    results[method]=result
                    metric=measure(visible,occlusion,truth,result)
                    # Every synthetic scene has exactly one eligible hidden role.
                    metric['false_connections']=sum(r['branch']!=role for r in result['accepted'])
                    records.append(dict(factor=factor,value=value,branch=role,method=method,
                        runtime_median_seconds=float(np.median(durations)),parameters=settings,
                        detector_rejections=detection['rejected'],**metric))
                if factor=='gap_length' or (factor=='noise' and value in (2.,4.)):
                    name=f'{factor}_{value}_{role}.png'
                    panels(Image.new('RGB',(192,192),'#18212b'),visible,results,synthetic/name,truth)
                    images.append((f'{factor}={value}, {role}',f'synthetic/{name}'))
    (output/'synthetic_metrics.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    sensitivity,matched=sensitivity_report(records,sweeps,output)
    # All input paths come from the Step 3 v4 run; no whole-label reads.
    source=ROOT/'results/step3_real_validation/coverage_revision_v4/run'
    real=output/'real';real.mkdir();real_reports=[]
    for directory in sorted(source.iterdir()):
        if not directory.is_dir() or not (directory/'annotation.json').exists():continue
        annotation=json.loads((directory/'annotation.json').read_text(encoding='utf-8'))
        rgb_path=ROOT/annotation['rgb_path'];skeleton_path=directory/'skeleton.png'
        before={str(p):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in (rgb_path,skeleton_path)}
        if before[str(rgb_path)][0]!=annotation['rgb_sha256']:raise ValueError('RGB source hash mismatch')
        with Image.open(skeleton_path) as image:visible=np.array(image)>0
        detection=detect_candidate_gaps(visible,max_gap_px=100)
        # Permissive UNKNOWN region only for an explicitly labelled hypothesis
        # visualization. It is never saved or described as confirmed occlusion.
        unknown_region=~visible
        results={};report=dict(sample_id=directory.name,provenance=annotation['provenance'],
            review_status=annotation['review_status'],mode='unverified_gap_hypothesis_only',
            occlusion_confirmed=False,candidate_detection=detection,methods={})
        for method in ('linear','quadratic'):
            start=time.perf_counter()
            result=complete_gaps(visible,detection['candidates'],unknown_region,method,max_gap_px=100)
            results[method]=result
            payload={k:v for k,v in result.items() if k not in ('skeleton','inferred_mask')}
            for r in payload['accepted']:
                r['occlusion_status']='unverified';r['uncertainty']='Possible annotation omission or wrong branch identity; RGB review required'
            payload['runtime_seconds']=time.perf_counter()-start
            report['methods'][method]=payload
            Image.fromarray(result['inferred_mask'].astype(np.uint8)*255).save(real/f'{directory.name}_{method}_inferred.png')
            Image.fromarray(result['skeleton'].astype(np.uint8)*255).save(real/f'{directory.name}_{method}_skeleton.png')
        Image.fromarray(visible.astype(np.uint8)*255).save(real/f'{directory.name}_visible.png')
        with Image.open(rgb_path) as image:panels(image.convert('RGB'),visible,results,real/f'{directory.name}.png')
        after={str(p):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in (rgb_path,skeleton_path)}
        if before!=after:raise RuntimeError('Source changed')
        report['source_integrity']=before;real_reports.append(report)
        (real/f'{directory.name}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'real_summary.json').write_text(json.dumps(real_reports,indent=2),encoding='utf-8')
    summary={}
    for method in ('linear','quadratic'):
        rows=[r for r in records if r['method']==method]
        valid=[r for r in rows if r['completion_chamfer_px'] is not None]
        summary[method]=dict(cases=len(rows),completed_cases=len(valid),
            mean_completion_chamfer_px=float(np.mean([r['completion_chamfer_px'] for r in valid])) if valid else None,
            mean_hidden_recall_2px=float(np.mean([r['hidden_recall_2px'] for r in rows])),
            mean_tangent_error_deg=float(np.mean([r['mean_tangent_error_deg'] for r in valid])) if valid else None,
            false_connections=sum(r['false_connections'] for r in rows),
            connected_cases=sum(r['connected'] for r in rows),
            mean_runtime_ms=1000*float(np.mean([r['runtime_median_seconds'] for r in rows])))
    summary['real_samples']=len(real_reports)
    summary['matched_synthetic_cases']=matched
    summary['real_hypotheses']={m:sum(len(r['methods'][m]['accepted']) for r in real_reports) for m in ('linear','quadratic')}
    summary['note']='Synthetic one-factor sweeps reuse base cases; aggregates are descriptive, not independent trials. Real data has no accuracy metrics.'
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    parts=['<!doctype html><meta charset="utf-8"><title>Step 4 completion</title>',
        '<style>body{font:16px system-ui;background:#111827;color:#eee;margin:24px}img{width:100%;height:auto}a{color:#7dd3fc}pre{white-space:pre-wrap}section{margin:32px 0}</style>',
        '<h1>Step 4: 2D branch completion / 枝条补全</h1>',
        '<p>Cyan = original visible skeleton. Magenta = inferred hypothesis. 白色合成参考仅用于评估。</p>',
        '<p>真实样本全部是未审核草稿：缺口可能来自漏标；粉色线不是已确认遮挡。无真实准确率、无深度或三维推断。</p>',
        '<p><a href="synthetic_metrics.json">Synthetic metrics and sensitivity data</a> · <a href="real_summary.json">Real candidates, rejections and provenance</a></p>',
        '<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Real drafts: qualitative hypotheses only</h2>']
    for r in real_reports:
        name=r['sample_id'];counts={m:len(r['methods'][m]['accepted']) for m in ('linear','quadratic')}
        parts.append(f'<section><h3>{html.escape(name)} — {counts}</h3><a href="real/{name}.json">Decisions / rejection reasons</a><img loading="lazy" src="real/{name}.png"></section>')
    parts.append('<h2>Sensitivity analysis</h2><p>One factor at a time; three anatomical roles per setting. Error is conditional on acceptance; recall counts abstention as zero. Noise is smooth transverse pixel displacement, not sensor noise. Runtime covers completion and graph creation, excluding detection, I/O and plotting; median of three runs, no warmup.</p><img src="sensitivity.png"><p><a href="sensitivity.json">Sensitivity table and matched-case comparison</a></p>')
    parts.append('<table><tr><th>Factor</th><th>Value</th><th>Method</th><th>Accepted fraction</th><th>Mean error (px)</th><th>Recall (2px)</th></tr>')
    for r in sensitivity:
        error='N/A' if r['mean_error_px'] is None else f"{r['mean_error_px']:.3f}"
        parts.append(f"<tr><td>{r['factor']}</td><td>{r['value']}</td><td>{r['method']}</td><td>{r['completion_rate']:.2f}</td><td>{error}</td><td>{r['mean_recall_2px']:.3f}</td></tr>")
    parts.append('</table><h2>Synthetic controlled occlusions and noise</h2>')
    for title,path in images:parts.append(f'<section><h3>{html.escape(title)}</h3><img loading="lazy" src="{path}"></section>')
    (output/'index.html').write_text('\n'.join(parts),encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='results/step4_occlusion_completion')
    print(json.dumps(run(parser.parse_args().output),indent=2))
