"""Real RGB mask-assisted diagnostics; draft annotations require explicit opt-in.

No Summer GT, winter, depth or learned segmentation is accessed. All reported
preservation measures refer to the supplied polygons, not independent tree truth.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
import time
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_tree_project.baseline import visible_only_baseline
from apple_tree_project.visible_annotation import rasterize,verify_source,quality_checks
ROOT=Path(__file__).resolve().parents[1]


def label_components(mask):
    """Independent eight-neighbour flood fill for input connectivity diagnostics."""
    foreground={tuple(map(int,p)) for p in np.argwhere(mask)}
    labels=np.zeros(mask.shape,dtype=np.int32)
    component_id=0
    while foreground:
        seed=min(foreground);foreground.remove(seed);component_id+=1;stack=[seed]
        while stack:
            y,x=stack.pop();labels[y,x]=component_id
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    p=(y+dy,x+dx)
                    if p in foreground:
                        foreground.remove(p);stack.append(p)
    return labels,component_id


def diagnostics(mask,result,annotation):
    labels,count=label_components(mask)
    graph=result['graph']
    mapped=[]
    for component in graph['components']:
        mapped.append({int(labels[graph['nodes'][i]['y'],graph['nodes'][i]['x']]) for i in component})
    component_ok=(len(mapped)==count and all(len(m)==1 and 0 not in m for m in mapped)
                  and set.union(set(),*mapped)==set(range(1,count+1)))
    patches=[]
    for polygon in annotation['polygons']:
        single=dict(annotation,polygons=[polygon])
        region=rasterize(single,(mask.shape[1],mask.shape[0]))>0
        patches.append(dict(id=polygon['id'],mask_pixels=int(region.sum()),
                            skeleton_pixels=int((region & result['skeleton']).sum())))
    return dict(input_components=count,skeleton_components=len(graph['components']),
        components_preserved_one_to_one=component_ok,
        skeleton_outside_input_pixels=int((result['skeleton'] & ~(mask>0)).sum()),
        unchanged_prediction=bool(np.array_equal(result['prediction'],mask>0)),
        annotated_patches=len(patches),patches_with_skeleton=sum(p['skeleton_pixels']>0 for p in patches),
        patches=patches,endpoints=len(graph['endpoint_ids']),junction_pixels=len(graph['junction_pixel_ids']),
        isolated_pixels=len(graph['isolated_pixel_ids']),
        cycle_rank=len(graph['edges'])-len(graph['nodes'])+len(graph['components']))


def comparison(rgb,mask,result,sample_id,provenance):
    """Four native-resolution panels: RGB, labelled patches, skeleton, pixel graph."""
    w,h=rgb.size
    sheet=Image.new('RGB',(2*w,2*(h+38)),(245,245,245))
    draw=ImageDraw.Draw(sheet)
    a=np.array(rgb)
    masked=a.copy();fg=mask>0
    masked[fg]=(.45*masked[fg]+.55*np.array([0,255,255])).astype(np.uint8)
    sk=a.copy();sk[result['skeleton']]=[255,255,0]
    graph=result['graph'];graph_image=Image.fromarray((a*.25).astype(np.uint8))
    gd=ImageDraw.Draw(graph_image)
    colors=['#00ffff','#ff80ff','#ffff00','#80ff80','#ffa040','#8080ff','#ffffff']
    node_color={}
    for c,component in enumerate(graph['components']):
        color=colors[c%len(colors)]
        for i in component:node_color[i]=color
    for edge in graph['edges']:
        source,target=graph['nodes'][edge['source']],graph['nodes'][edge['target']]
        gd.line((source['x'],source['y'],target['x'],target['y']),fill=node_color[source['id']],width=1)
    for node in graph['nodes']:
        x,y=node['x'],node['y']
        gd.point((x,y),fill=node_color[node['id']])
        if node['degree']!=2:
            color='red' if node['degree']==1 else 'white'
            gd.ellipse((x-3,y-3,x+3,y+3),outline=color,width=1)
    panels=[('Original RGB',rgb),('RGB-only polygon draft: NOT reviewed truth',Image.fromarray(masked)),
            ('Extracted skeleton (yellow)',Image.fromarray(sk)),
            (f"Pixel graph: {len(graph['components'])} components; red endpoints / white junctions",graph_image)]
    for i,(title,panel) in enumerate(panels):
        x,y=(i%2)*w,(i//2)*(h+38)
        draw.text((x+5,y+3),sample_id+' | '+title,fill='black')
        draw.text((x+5,y+18),provenance+' | graph pixels/edges share component colour',fill='black')
        sheet.paste(panel,(x,y+38))
    return sheet


def run(bundle_path,output,include_drafts=False,repeats=5):
    output=output.resolve()
    if (ROOT/'results').resolve() not in output.parents:
        raise ValueError('Outputs must be below results/')
    if output.exists():raise ValueError('New output directory required; preserve previous runs')
    if not 1<=repeats<=100:raise ValueError('repeats must be 1..100')
    data=bundle_path.read_bytes();bundle=json.loads(data.decode('utf-8-sig'))
    samples=bundle.get('samples',[bundle])
    if not samples:raise ValueError('No annotations')
    ids=[s['sample_id'] for s in samples]
    if len(set(ids))!=len(ids) or any(not sid.replace('_','').isalnum() for sid in ids):
        raise ValueError('Nonunique or unsafe sample IDs')
    sources={}
    for annotation in samples:
        if annotation['review_status']!='accepted' and not include_drafts:
            raise ValueError('Unapproved annotations require --include-drafts; not approved validation')
        if annotation['review_status']=='rejected':raise ValueError('Rejected annotation must not run')
        path=(ROOT/annotation['rgb_path']).resolve(strict=True)
        if output in path.parents:raise ValueError('Output contains source RGB')
        verify_source(annotation,path)
        sources[path]=(annotation['rgb_sha256'],path.stat().st_mtime_ns)
        with Image.open(path) as im:
            if im.mode!='RGB':raise ValueError('RGB-only input required')
            rasterize(annotation,im.size)
    output.mkdir(parents=True)
    rows=[];details=[]
    for annotation in samples:
        sid=annotation['sample_id'];path=(ROOT/annotation['rgb_path']).resolve()
        with Image.open(path) as im:rgb=im.copy()
        mask=rasterize(annotation,rgb.size)
        result=visible_only_baseline(mask) # one warmup, excluded from timing
        durations=[]
        for _ in range(repeats):
            start=time.perf_counter();result=visible_only_baseline(mask)
            durations.append(time.perf_counter()-start)
        measures=diagnostics(mask,result,annotation)
        directory=output/sid;directory.mkdir()
        Image.fromarray(mask).save(directory/'visible.png')
        Image.fromarray(result['skeleton'].astype(np.uint8)*255).save(directory/'skeleton.png')
        comparison(rgb,mask,result,sid,annotation['provenance']).save(directory/'comparison.png')
        (directory/'graph.json').write_text(json.dumps(result['graph'],indent=2),encoding='utf-8')
        (directory/'annotation.json').write_text(json.dumps(annotation,indent=2),encoding='utf-8')
        detail=dict(sample_id=sid,provenance=annotation['provenance'],review_status=annotation['review_status'],
                    visible_pixels=int((mask>0).sum()),skeleton_pixels=int(result['skeleton'].sum()),
                    median_inference_seconds=statistics.median(durations),timing_seconds=durations,**measures)
        (directory/'diagnostics.json').write_text(json.dumps(detail,indent=2),encoding='utf-8')
        (directory/'quality_checks.json').write_text(json.dumps(quality_checks(mask,result['graph'],annotation.get('checkpoints',[])),indent=2),encoding='utf-8')
        details.append(detail)
        rows.append({k:v for k,v in detail.items() if k not in ('patches','timing_seconds')})
    contact=Image.new('RGB',(1280,278*((len(samples)+3)//4)),'white')
    cd=ImageDraw.Draw(contact)
    for i,annotation in enumerate(samples):
        x,y=(i%4)*320,(i//4)*278
        with Image.open(output/annotation['sample_id']/'comparison.png') as im:
            tile=im.resize((320,259))
        cd.text((x+3,y+2),annotation['sample_id'],fill='black')
        contact.paste(tile,(x,y+19))
    contact.save(output/'contact_sheet.png')
    changed=[str(p) for p,(sha,mtime) in sources.items() if hashlib.sha256(p.read_bytes()).hexdigest()!=sha or p.stat().st_mtime_ns!=mtime]
    if changed:raise RuntimeError(f'Source files changed: {changed}')
    if bundle_path.read_bytes()!=data:raise RuntimeError('Annotation bundle changed during run')
    with (output/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=dict(sample_count=len(rows),accepted_human_review_count=sum(s['review_status']=='accepted' for s in samples),
        manually_reviewed_count=sum(s['review_status'] in ('reviewed','accepted') for s in samples),
        draft_count=sum(s['review_status']=='pending' for s in samples),
        note='RGB-only draft diagnostics, not real anatomical accuracy; patch survival is not branch recall.',
        annotation_bundle_sha256=hashlib.sha256(data).hexdigest(),
        runtime_scope='NumPy thinning plus pixel graph, one warmup then repeats; excludes annotation, IO and figures',
        repeats=repeats,python=platform.python_version(),platform=platform.platform(),numpy=np.__version__,
        all_components_preserved=all(d['components_preserved_one_to_one'] for d in details),
        skeleton_outside_input_pixels=sum(d['skeleton_outside_input_pixels'] for d in details),
        total_annotated_patches=sum(d['annotated_patches'] for d in details),
        total_patches_with_skeleton=sum(d['patches_with_skeleton'] for d in details),
        median_sample_runtime_seconds=statistics.median(d['median_inference_seconds'] for d in details),
        min_sample_runtime_seconds=min(d['median_inference_seconds'] for d in details),
        max_sample_runtime_seconds=max(d['median_inference_seconds'] for d in details),
        checked_original_rgb_count=len(sources),changed_sources=changed,samples=rows)
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return {k:v for k,v in summary.items() if k!='samples'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--annotations',type=Path,default=ROOT/'data/annotations/step3_rgb_only_drafts.json')
    p.add_argument('--output',type=Path,default=ROOT/'results/step3_real_validation/draft_run')
    p.add_argument('--include-drafts',action='store_true')
    p.add_argument('--repeats',type=int,default=5)
    a=p.parse_args();print(json.dumps(run(a.annotations,a.output,a.include_drafts,a.repeats),indent=2))
