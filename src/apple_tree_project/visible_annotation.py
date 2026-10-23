"""RGB-only polygon annotations; provenance does not certify independent review."""
from __future__ import annotations
import hashlib
import numpy as np
from PIL import Image, ImageDraw

POLICY = 'visible-main-wood-v1'


def rasterize(annotation, size):
    """Rasterize integer pixel-centre polygons with Pillow's inclusive fill.

    All geometry is recorded explicitly; no morphology or GT alignment is used.
    """
    w,h = size
    if annotation.get('policy') != POLICY or annotation.get('image_size') != [w,h]:
        raise ValueError('Annotation policy or native size mismatch')
    if annotation.get('provenance') not in ('human_rgb_only','ai_rgb_only_draft','human_rgb_revision'):
        raise ValueError('Explicit RGB-only provenance required')
    if not annotation.get('annotator') or not annotation.get('notes'):
        raise ValueError('Annotator identity and limitations required')
    if annotation.get('review_status') not in ('pending','reviewed','accepted','rejected'):
        raise ValueError('Explicit review status required')
    if annotation['review_status']=='accepted' and not annotation.get('reviewer'):
        raise ValueError('Accepted annotations require a reviewer identity')
    if annotation['review_status'] in ('reviewed','accepted'):
        if annotation['provenance']=='ai_rgb_only_draft':
            raise ValueError('AI draft cannot claim human review; record a human revision first')
        if not all(annotation.get(k) for k in ('reviewer','reviewed_utc','review_notes')):
            raise ValueError('Human review requires reviewer, date and review notes')
    if annotation['review_status']=='accepted':
        if not all(annotation.get(k) for k in ('approved_by','approved_utc','approval_notes')):
            raise ValueError('Approval requires approver, date and approval notes')
        if annotation['approved_by'].strip()==annotation['reviewer'].strip():
            raise ValueError('Approval requires a separate approving person')
    polygons=annotation.get('polygons',[])
    if not polygons:
        raise ValueError('No polygons; unlabelled input must not become an empty mask')
    mask=Image.new('L',size)
    draw=ImageDraw.Draw(mask)
    ids=set()
    for polygon in polygons:
        points=polygon['points']
        if not polygon.get('id') or polygon['id'] in ids:
            raise ValueError('Polygon IDs must be nonempty and unique')
        ids.add(polygon['id'])
        if len(points)<3:
            raise ValueError('A polygon needs at least three vertices')
        if any(len(p)!=2 or any(type(v) is not int for v in p) or not (0<=p[0]<w and 0<=p[1]<h) for p in points):
            raise ValueError('Vertices must be native-grid integer coordinates inside the image')
        area=sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))
        if area==0:
            raise ValueError('Degenerate polygon')
        if len({tuple(p) for p in points})!=len(points):
            raise ValueError('Repeated polygon vertex')
        def orientation(a,b,c):
            return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        def on_segment(a,b,c):
            return orientation(a,b,c)==0 and min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(a[1],b[1])<=c[1]<=max(a[1],b[1])
        for i in range(len(points)):
            a,b=points[i],points[(i+1)%len(points)]
            for j in range(i+1,len(points)):
                if j==i+1 or (i==0 and j==len(points)-1):continue
                c,d=points[j],points[(j+1)%len(points)]
                o1,o2,o3,o4=orientation(a,b,c),orientation(a,b,d),orientation(c,d,a),orientation(c,d,b)
                if (o1*o2<0 and o3*o4<0) or any((on_segment(a,b,c),on_segment(a,b,d),on_segment(c,d,a),on_segment(c,d,b))):
                    raise ValueError('Self-intersecting polygon')
        draw.polygon([tuple(p) for p in points],fill=255)
    return np.array(mask)


def reset_review(annotation):
    """Geometry changes invalidate any previous review/approval declaration."""
    annotation.update(review_status='pending',reviewer='')
    for key in ('reviewed_utc','review_notes','approved_by','approved_utc','approval_notes'):
        annotation.pop(key,None)


def quality_checks(mask, graph, checkpoints=(), small_component_pixels=12,
                   short_terminal_length=8.0, near_endpoint_distance=12.0):
    """Review prompts only: no RGB understanding, pruning or gap completion.

    Visible-required / occluded-excluded point checks test only supplied points,
    not region completeness. Thresholds use native pixels, not physical units.
    """
    import math
    mask=np.asarray(mask)>0
    h,w=mask.shape
    point_results=[]
    for point in checkpoints:
        x,y=point['point']
        if type(x) is not int or type(y) is not int or not (0<=x<w and 0<=y<h):
            raise ValueError('Checkpoint must be an in-frame integer pixel')
        kind=point['kind']
        if kind not in ('visible_required','occluded_excluded'):
            raise ValueError('Unknown checkpoint kind')
        covered=bool(mask[y,x])
        point_results.append(dict(**point,covered=covered,passed=covered if kind=='visible_required' else not covered))
    nodes=graph['nodes']; adjacent={n['id']:[] for n in nodes}
    for edge in graph['edges']:
        adjacent[edge['source']].append((edge['target'],edge['length_px']))
        adjacent[edge['target']].append((edge['source'],edge['length_px']))
    component_of={i:c for c,component in enumerate(graph['components']) for i in component}
    terminal=[]
    for endpoint in graph['endpoint_ids']:
        prev=None;current=endpoint;length=0.0
        while True:
            onward=[(i,d) for i,d in adjacent[current] if i!=prev]
            if not onward:break
            nxt,d=onward[0];length+=d;prev,current=current,nxt
            if len(adjacent[current])!=2:break
        terminal.append(dict(endpoint_id=endpoint,length_px=length,
                             ends_at_junction=len(adjacent[current])>=3,
                             short_spur_candidate=len(adjacent[current])>=3 and length<=short_terminal_length))
    pairs=[]
    endpoints=graph['endpoint_ids']
    for index,i in enumerate(endpoints):
        for j in endpoints[index+1:]:
            distance=math.hypot(nodes[i]['x']-nodes[j]['x'],nodes[i]['y']-nodes[j]['y'])
            if component_of[i]!=component_of[j] and distance<=near_endpoint_distance:
                pairs.append(dict(endpoint_ids=[i,j],distance_px=distance,action='inspect RGB; never auto-connect'))
    return dict(scope='Heuristic prompts and explicit point checks, not anatomical accuracy or full coverage verification',
                thresholds=dict(small_component_pixels=small_component_pixels,short_terminal_length_px=short_terminal_length,
                                near_endpoint_distance_px=near_endpoint_distance),
                checkpoints=point_results,failed_checkpoints=[p for p in point_results if not p['passed']],
                coverage_check_available=any(p['kind']=='visible_required' for p in point_results),
                small_component_candidates=[dict(component_index=c,skeleton_pixels=len(ids)) for c,ids in enumerate(graph['components']) if len(ids)<=small_component_pixels],
                terminal_paths=terminal,near_disconnected_endpoints=pairs,
                endpoint_coordinates=[dict(id=i,x=nodes[i]['x'],y=nodes[i]['y'],at_frame=nodes[i]['x'] in (0,w-1) or nodes[i]['y'] in (0,h-1)) for i in endpoints],
                component_sizes=[len(c) for c in graph['components']],
                cycle_rank=len(graph['edges'])-len(nodes)+len(graph['components']),
                isolated_pixel_ids=graph['isolated_pixel_ids'],
                junction_pixel_ids=graph['junction_pixel_ids'])


def verify_source(annotation, rgb_path):
    """Bind annotation coordinates to exact RGB bytes; no filename-only pairing."""
    if hashlib.sha256(rgb_path.read_bytes()).hexdigest()!=annotation.get('rgb_sha256'):
        raise ValueError('RGB hash mismatch')
