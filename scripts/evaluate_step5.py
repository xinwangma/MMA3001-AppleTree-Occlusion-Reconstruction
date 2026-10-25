"""Read-only depth investigation, known-camera synthetic study and real code relief."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import asdict,replace
from datetime import datetime,timezone
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image,ImageDraw
from apple_tree_project.baseline import pixel_graph,thin_visible
from apple_tree_project.completion import complete_gaps,detect_candidate_gaps
from apple_tree_project.reconstruction3d import Calibration,lift_skeleton,nonmetric_demo

ROOT=Path(__file__).resolve().parents[1]
SOURCES=[
 dict(url='https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction',
      finding='2022 landing page describes 435 RGB-D images/trees and annotation categories; no numerical calibration or encoding specification on inspected page.'),
 dict(url='https://www.monash.edu/engineering/lmga/news/y-shaped-apple-tree-public-dataset-for-hob-cnnv2',
      finding='2023 landing page points to a different archive and author repository; no numerical calibration on inspected page.'),
 dict(url='https://github.com/ZijueChen/HOBCNN-v2',finding='Author repository README describes 2D branch detection and installation, not a depth decoder or calibration for the local files.'),
 dict(url='https://www.sciencedirect.com/science/article/pii/S0168169924001182',
      finding='Accessible article abstract/preview covers 2D detection and seasonal images; no usable numeric calibration in the inspected preview. Full paper/archive not audited.')]


def save_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')


def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    stat=path.stat();return dict(sha256=h.hexdigest(),size=stat.st_size,mtime_ns=stat.st_mtime_ns)


def depth_investigation(output):
    raw=ROOT/'data/raw/monash_y_tree/TreeID'
    files=sorted(p for p in raw.rglob('*') if p.is_file())
    groups=defaultdict(list);details=[]
    for path in files:
        if '_D-' not in path.name:continue
        with Image.open(path) as image:
            a=np.array(image);equal=a.ndim==3 and a.shape[2]==3 and bool(np.all(a==a[:,:,:1]))
            row=dict(path=path.relative_to(ROOT).as_posix(),size=list(image.size),mode=image.mode,dtype=str(a.dtype),
                equal_channels=equal,minimum=int(a.min()),maximum=int(a.max()),unique_levels=int(len(np.unique(a))),
                zero_fraction=float(np.mean(a[:,:,0]==0)) if equal else None,
                metadata_keys=sorted(image.info),exif_count=len(image.getexif()))
        season='Summer' if '_Summer_' in path.name else 'Winter'
        groups[path.parent.name+'/'+season].append(row);details.append(row)
    aggregate={name:dict(files=len(rows),all_rgb_uint8_equal=all(r['mode']=='RGB' and r['dtype']=='uint8' and r['equal_channels'] for r in rows),
        sizes=sorted({tuple(r['size']) for r in rows}),stored_min=min(r['minimum'] for r in rows),stored_max=max(r['maximum'] for r in rows),
        mean_zero_fraction=float(np.mean([r['zero_fraction'] for r in rows])),
        images_with_metadata=sum(bool(r['metadata_keys'] or r['exif_count']) for r in rows)) for name,rows in groups.items()}
    result=dict(inspected_utc=datetime.now(timezone.utc).isoformat(),raw_files=len(files),raw_bytes=sum(p.stat().st_size for p in files),
        extensions=sorted({p.suffix for p in files}),depth_files=len(details),groups=aggregate,depth_records=details,
        verified=['Local stored representation and dimensions measured directly','Filename pairing is nominal only'],
        unresolved=['depth transfer function/scale/offset','axial Z versus Euclidean range','invalid-value conventions',
                    'intrinsics and distortion','RGB-depth spatial registration/extrinsics','3D reference geometry','upstream archive/version correspondence'],
        metric_real_reconstruction_supported=False,public_sources=SOURCES,
        evidence_scope='Inspected local files and cited public pages/README/abstract only; no full-paper or remote-archive audit, no proof calibration cannot exist elsewhere.')
    save_json(output/'calibration/depth_investigation.json',result)
    return result


def synthetic_scene(kind='varying_z',gap_size=16):
    """Analytic 3D curves first, perspective projection second; never use GT in lift.

    Ray-centre rasterisation introduces genuine quantisation error. Reference
    correspondences are nearest projected analytic samples, disclosed in metrics.
    """
    camera=Calibration(192,192,140.,140.,96.,96.,1.,'axial_z',(0.,),True,True,
                       'Synthetic analytic 3D tree; known pinhole, rectified registered scalar axial metres')
    definitions=[([0,.9,3.2],[0,0,3.],[.12,0,.10]),
                 ([0,0,3.],[-.95,-1.1,2.7],[0,.35,.25]),
                 ([0,0,3.],[.95,-1.1,3.3],[0,-.20,-.15])]
    points=[];projected=[];masks=[]
    t=np.linspace(0,1,2001)
    for a,b,c in definitions:
        a,b,c=map(lambda x:np.asarray(x,float),(a,b,c))
        if kind=='constant_z':a[2]=b[2]=3.;c[2]=0.
        if kind=='curved_z':c[2]+=1.2
        xyz=a+t[:,None]*(b-a)+(t*(t-1))[:,None]*c
        uv=np.c_[camera.fx*xyz[:,0]/xyz[:,2]+camera.cx,camera.fy*xyz[:,1]/xyz[:,2]+camera.cy]
        image=Image.new('1',(192,192));ImageDraw.Draw(image).line([tuple(p) for p in np.rint(uv).astype(int)],fill=1)
        masks.append(np.array(image,bool));points.append(xyz);projected.append(uv)
    full=thin_visible(np.logical_or.reduce(masks));xyz=np.vstack(points);uv=np.vstack(projected)
    centre=projected[1][1000];yy,xx=np.indices(full.shape)
    occlusion=(abs(xx-centre[0])<=gap_size/2)&(abs(yy-centre[1])<=gap_size/2)
    visible=full&~occlusion
    depth=np.full(full.shape,.4) # foreground at every hidden pixel: never branch depth
    reference={}
    for y,x in np.argwhere(full):
        i=int(np.argmin(np.sum((uv-[x,y])**2,axis=1)))
        reference[(int(x),int(y))]=xyz[i]
        if visible[y,x]:depth[y,x]=xyz[i,2]
    return camera,visible,occlusion,depth,full,xyz,uv,reference


def evaluate_geometry(result,reference_xyz,reference_uv,full_reference):
    errors=defaultdict(list);valid=[]
    for n in result['nodes']:
        if n['xyz_m'] is None:continue
        i=int(np.argmin(np.sum((reference_uv-[n['x'],n['y']])**2,axis=1)))
        errors[n['status_3d']].append(float(np.linalg.norm(np.asarray(n['xyz_m'])-reference_xyz[i])))
        valid.append(n['xyz_m'])
    metric=dict(**result['status_counts'],supported_components=len(result['supported_3d_components']),
        supported_edges=sum(e['status_3d']!='unsupported' for e in result['edges']),
        supported_length_m=sum(e['length_m'] or 0 for e in result['edges']))
    all_errors=[]
    for status in ('measured','inferred'):
        values=errors[status];all_errors.extend(values)
        metric[status+'_rmse_m']=float(np.sqrt(np.mean(np.square(values)))) if values else None
    metric['supported_rmse_m']=float(np.sqrt(np.mean(np.square(all_errors)))) if all_errors else None
    target=np.array(list(full_reference.values()))
    if valid:
        distance=np.min(np.linalg.norm(target[:,None]-np.array(valid)[None,:],axis=2),axis=1)
        metric['reference_coverage_3cm']=float(np.mean(distance<=.03))
    else:metric['reference_coverage_3cm']=0.
    n=sum(result['status_counts'].values());metric['supported_fraction']=(len(valid)/n if n else 0.)
    metric['supported_cycle_rank']=metric['supported_edges']-len(valid)+metric['supported_components']
    return metric


def plot_graph(result,path,reference=None,nonmetric=False,title=''):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    figure=plt.figure(figsize=(8,7));axis=figure.add_subplot(projection='3d')
    nodes=result['nodes'];key='display_uvw' if nonmetric else 'xyz_m'
    if reference is not None:axis.scatter(*reference[::12].T,c='#888888',s=2,alpha=.4,label='Analytic 3D reference')
    if nonmetric:
        categories=[('draft-visible','#00a4b8'),('hidden display plane','#dc267f')]
        for hidden,(label,color) in enumerate(categories):
            group=np.array([n[key] for n in nodes if n['inferred']==bool(hidden)])
            if len(group):axis.scatter(*group.T,s=8,c=color,label=label)
        axis.set(xlabel='u / (W-1), image fraction',ylabel='1-v / (H-1), image fraction',zlabel='stored code / 255 (NOT DEPTH)')
    else:
        for status,color in [('measured','#00a4b8'),('inferred','#dc267f')]:
            group=np.array([n[key] for n in nodes if n['status_3d']==status])
            if len(group):axis.scatter(*group.T,s=8,c=color,label=status)
        axis.set(xlabel='Camera X (m)',ylabel='Camera Y down (m)',zlabel='Camera Z forward (m)')
    segments=[];colors=[]
    for e in result['edges']:
        a,b=nodes[e['source']],nodes[e['target']]
        if a[key] is None or b[key] is None:continue
        # In real code relief do not connect the display-plane annotation to
        # unrelated code heights; no implied physical hidden-depth continuity.
        if nonmetric and a['inferred']!=b['inferred']:continue
        segments.append([a[key],b[key]]);colors.append('#dc267f' if a['inferred'] or b['inferred'] else '#00a4b8')
    if segments:axis.add_collection3d(Line3DCollection(segments,colors=colors,linewidths=.8))
    axis.set_title(title,fontsize=10);axis.legend(loc='best');axis.view_init(elev=23,azim=-55)
    figure.tight_layout();figure.savefig(path,dpi=140);plt.close(figure)


def write_csv(path,records):
    keys=list(dict.fromkeys(k for row in records for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(records)


def run(output):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results'):raise ValueError('Use a new directory below results')
    # Protect all existing raw dataset/results bytes and timestamps before creating outputs.
    manifest={}
    for base in (ROOT/'data/raw/monash_y_tree/TreeID',ROOT/'results'):
        for p in sorted(base.rglob('*')):
            if p.is_file():manifest[p.relative_to(ROOT).as_posix()]=fingerprint(p)
    output.mkdir(parents=True);(output/'synthetic').mkdir();(output/'real_nonmetric').mkdir()
    save_json(output/'preservation_manifest.json',manifest)
    investigation=depth_investigation(output)
    metrics=[];scenes=[]
    for kind in ('constant_z','varying_z','curved_z'):
        camera,visible,occlusion,depth,full,truth,uv,reference=synthetic_scene(kind)
        detection=detect_candidate_gaps(visible,max_gap_px=80,max_angle_deg=80,max_curvature_deg=70)
        save_json(output/'synthetic'/f'{kind}_calibration.json',asdict(camera))
        save_json(output/'synthetic'/f'{kind}_reference.json',dict(analytic_xyz_m=truth.tolist(),projected_uv=uv.tolist(),
            raster_reference=[dict(u=x,v=y,xyz_m=p.tolist()) for (x,y),p in reference.items()]))
        for name,array in [('visible',visible),('occlusion',occlusion),('whole_reference',full)]:
            Image.fromarray(array.astype('uint8')*255).save(output/'synthetic'/f'{kind}_{name}.png')
        np.save(output/'synthetic'/f'{kind}_input_depth_m.npy',depth)
        for method in ('visible_only','linear','quadratic'):
            completion=None if method=='visible_only' else complete_gaps(visible,detection['candidates'],occlusion,method,max_angle_deg=80)
            graph=pixel_graph(visible) if completion is None else completion['graph']
            save_json(output/'synthetic'/f'{kind}_{method}_2d_decisions.json',dict(detection=detection,
                accepted=[] if completion is None else completion['accepted'],rejected=[] if completion is None else completion['rejected']))
            for infer in (False,True) if method!='visible_only' else (False,):
                result=lift_skeleton(graph,depth,camera,visible,infer_hidden_depth=infer)
                name=f'{kind}_{method}_'+('inferred_z' if infer else 'measured_only')
                save_json(output/'synthetic'/f'{name}.json',result)
                plot_graph(result,output/'synthetic'/f'{name}.png',truth,title=name+'\nSynthetic known-camera geometry; unsupported nodes omitted')
                row=dict(scene=kind,method=method,hidden_z_inference=infer,**evaluate_geometry(result,truth,uv,reference))
                metrics.append(row);scenes.append(name)
    save_json(output/'synthetic_metrics.json',metrics);write_csv(output/'synthetic_metrics.csv',metrics)
    # One-factor sweeps share the same known tree; calibration errors are the
    # parameters used for reconstruction, not claims about real-camera noise.
    camera,visible,occlusion,depth,full,truth,uv,reference=synthetic_scene('varying_z')
    detection=detect_candidate_gaps(visible,max_angle_deg=80,max_curvature_deg=70)
    sweeps={'depth_noise_m':[0,.002,.01,.03,.08],'focal_error_fraction':[-.1,-.05,0,.05,.1],
            'principal_point_error_px':[-8,-4,0,4,8],'scale_error_fraction':[-.1,-.05,0,.05,.1],
            'depth_dropout_fraction':[0,.05,.15,.3,.6]}
    sensitivity=[]
    for factor,values in sweeps.items():
        for value in values:
            for method in ('linear','quadratic'):
                graph=complete_gaps(visible,detection['candidates'],occlusion,method,max_angle_deg=80)['graph']
                for seed in (17,29,43):
                    rng=np.random.default_rng(seed);noisy=depth.copy();used=camera
                    if factor=='depth_noise_m':noisy[visible]+=rng.normal(0,value,int(visible.sum()))
                    if factor=='depth_dropout_fraction':noisy[visible & (rng.random(visible.shape)<value)]=0
                    if factor=='focal_error_fraction':used=replace(camera,fx=camera.fx*(1+value),fy=camera.fy*(1+value))
                    if factor=='principal_point_error_px':used=replace(camera,cx=camera.cx+value,cy=camera.cy+value)
                    if factor=='scale_error_fraction':used=replace(camera,depth_unit_to_m=1+value)
                    durations=[]
                    for repeat in range(3):
                        start=time.perf_counter();result=lift_skeleton(graph,noisy,used,visible,infer_hidden_depth=True)
                        durations.append(time.perf_counter()-start)
                    sensitivity.append(dict(factor=factor,value=value,method=method,seed=seed,
                        runtime_median_ms=1000*float(np.median(durations)),**evaluate_geometry(result,truth,uv,reference)))
    save_json(output/'sensitivity.json',sensitivity);write_csv(output/'sensitivity.csv',sensitivity)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(2,3,figsize=(14,8),constrained_layout=True)
    for axis,(factor,values) in zip(axes.flat,sweeps.items()):
        for method in ('linear','quadratic'):
            means=[np.mean([r['supported_rmse_m'] for r in sensitivity if r['factor']==factor and r['value']==v and r['method']==method]) for v in values]
            axis.plot(values,means,marker='o',label=method)
        axis.set(title=factor,xlabel=factor,ylabel='Supported point RMSE (m)');axis.grid(alpha=.3)
    axes.flat[0].legend();axes.flat[-1].axis('off')
    figure.suptitle('Synthetic calibration/depth sensitivity: 3 seeds; conditional error, see coverage CSV')
    figure.savefig(output/'sensitivity.png',dpi=140);plt.close(figure)
    real_records=[]
    for path in sorted((ROOT/'results/step4_occlusion_completion/real').glob('R*.json')):
        prior=json.loads(path.read_text(encoding='utf-8'));name=prior['sample_id']
        annotation=json.loads((ROOT/f'results/step3_real_validation/coverage_revision_v4/run/{name}/annotation.json').read_text(encoding='utf-8'))
        rgb=ROOT/annotation['rgb_path'];depth_path=rgb.with_name(rgb.name.replace('_RGB-','_D-'))
        with Image.open(depth_path) as image:raw=np.array(image)
        if raw.shape!=(480,640,3) or not np.all(raw==raw[:,:,:1]):raise ValueError('Unexpected real depth container')
        scalar=raw[:,:,0]
        for method in ('linear','quadratic'):
            result=nonmetric_demo(prior['methods'][method]['graph'],scalar,scalar.shape)
            result.update(sample_id=name,draft_provenance=annotation['provenance'],review_status=annotation['review_status'],
                depth_source=depth_path.relative_to(ROOT).as_posix(),depth_hash=fingerprint(depth_path),
                note='nominal image-pixel/code association only; every physical XYZ is unsupported')
            save_json(output/'real_nonmetric'/f'{name}_{method}.json',result)
            plot_graph(result,output/'real_nonmetric'/f'{name}_{method}.png',nonmetric=True,
                title=name+' '+method+' — NON-METRIC code relief\nAll physical XYZ unsupported; hidden annotations on display plane only')
        Image.fromarray(scalar).save(output/'real_nonmetric'/f'{name}_stored_codes.png')
        real_records.append(dict(sample_id=name,metric_supported=False,reason='scale/intrinsics/encoding/registration unverified',
            stored_code_range=[int(scalar.min()),int(scalar.max())],provenance=annotation['provenance'],review_status=annotation['review_status']))
    save_json(output/'real_summary.json',real_records)
    changed=[name for name,record in manifest.items() if fingerprint(ROOT/name)!=record]
    if changed:raise RuntimeError('Protected inputs changed: '+repr(changed))
    baseline=[r for r in metrics if r['scene']=='varying_z']
    summary=dict(synthetic_scenes=3,synthetic_metrics=len(metrics),sensitivity_rows=len(sensitivity),real_samples=len(real_records),
        depth_files_scanned=investigation['depth_files'],protected_files=len(manifest),changed_sources=changed,
        metric_real_reconstruction_supported=False,baseline=baseline,
        runtime_scope='Median of three lift_skeleton calls; no 2D completion/I/O/plot time; no warmup',
        reference_scope='Known analytic 3D curves, nearest projected sample correspondence; includes pixel quantisation; not real accuracy')
    save_json(output/'summary.json',summary)
    parts=['<!doctype html><meta charset="utf-8"><title>Step 5 3D reconstruction</title>',
        '<style>body{font:16px system-ui;background:#111827;color:#eee;margin:24px}a{color:#7dd3fc}img{max-width:100%}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:15px}pre{white-space:pre-wrap}</style>',
        '<h1>Step 5: Depth-assisted 3D skeleton / 深度辅助三维骨架</h1>',
        '<p>Synthetic: calibrated metres only. Cyan=measured synthetic depth; magenta=inferred Z assumption; grey=known reference. Unsupported coordinates are null and omitted.</p>',
        '<p>Real: NON-METRIC image/code relief only. All physical XYZ unsupported. Cyan is draft-derived image/code samples, not measured branch coordinates. Magenta is a display-plane annotation, not hidden depth.</p>',
        '<p><a href="calibration/depth_investigation.json">Calibration evidence and unresolved assumptions</a> | <a href="synthetic_metrics.csv">Synthetic errors/connectivity</a> | <a href="sensitivity.csv">Sensitivity/runtime CSV</a></p>',
        '<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Sensitivity</h2><img src="sensitivity.png"><h2>Synthetic known-camera trees</h2><div class="grid">']
    for name in scenes:parts.append(f'<section><h3>{name}</h3><a href="synthetic/{name}.json">Coordinates and statuses</a><img src="synthetic/{name}.png"></section>')
    parts.append('</div><h2>Real samples: NOT metric reconstruction</h2><div class="grid">')
    for row in real_records:
        name=row['sample_id']
        for method in ('linear','quadratic'):parts.append(f'<section><h3>{name} {method} — unverified draft</h3><a href="real_nonmetric/{name}_{method}.json">Null physical XYZ / display codes</a><img src="real_nonmetric/{name}_{method}.png"></section>')
    parts.append('</div>')
    (output/'index.html').write_text('\n'.join(parts),encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='results/step5_3d_reconstruction')
    print(json.dumps(run(parser.parse_args().output),indent=2))
