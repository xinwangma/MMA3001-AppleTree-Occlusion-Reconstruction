"""Explicit-calibration camera lifting; no implicit real-data depth decoder."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import copy
import numpy as np
from .baseline import binary_visible


@dataclass(frozen=True)
class Calibration:
    """Caller-supplied evidence contract, not automatic proof of calibration.

    Grid is rectified and depth is registered to its pixels. Scalar decoding is
    raw*depth_unit_to_m + depth_offset_m; nonlinear/colour depth needs an external
    verified decoder. Integer pixel indices are centres; X right,Y down,Z forward.
    """
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    depth_unit_to_m: float
    depth_kind: str
    invalid_values: tuple
    registered_to_skeleton: bool
    rectified: bool
    evidence: str
    depth_offset_m: float = 0.

    def __post_init__(self):
        if any(isinstance(v,bool) or not isinstance(v,int) or v<=0 for v in (self.width,self.height)):
            raise ValueError('Positive integer calibration grid required')
        values=[self.fx,self.fy,self.cx,self.cy,self.depth_unit_to_m,self.depth_offset_m]
        if not np.isfinite(values).all() or min(self.fx,self.fy,self.depth_unit_to_m)<=0:
            raise ValueError('Finite calibration, positive focal lengths and scale required')
        if self.depth_kind not in ('axial_z','range'):
            raise ValueError('depth_kind must explicitly be axial_z or range')
        if self.registered_to_skeleton is not True or self.rectified is not True:
            raise ValueError('Verified registered and rectified grid required; no auto-resizing')
        if not isinstance(self.evidence,str) or not self.evidence.strip():
            raise ValueError('Calibration/decoding/registration evidence required')
        if not isinstance(self.invalid_values,(tuple,list)) or not np.isfinite(self.invalid_values).all():
            raise ValueError('Explicit finite invalid-value codes required (NaN always unsupported)')


def _rays(pixels, calibration):
    p=np.asarray(pixels,float)
    if p.ndim!=2 or p.shape[1]!=2 or not np.isfinite(p).all():
        raise ValueError('Expected finite N x 2 pixel coordinates')
    if ((p<0).any() or (p[:,0]>calibration.width-1).any() or (p[:,1]>calibration.height-1).any()):
        raise ValueError('Pixels outside calibration grid')
    return np.c_[(p[:,0]-calibration.cx)/calibration.fx,
                 (p[:,1]-calibration.cy)/calibration.fy,np.ones(len(p))]


def backproject(pixels, raw_values, calibration):
    """Return Nx3 metres and validity mask. Invalid rows contain NaN, never zero.

    axial_z: XYZ=((u-cx)/fx,(v-cy)/fy,1)*Z.
    range: normalize the ray before multiplying by Euclidean range.
    """
    ray=_rays(pixels,calibration);raw=np.asarray(raw_values,float)
    if raw.shape!=(len(ray),):raise ValueError('One scalar depth per pixel required')
    distance=raw*calibration.depth_unit_to_m+calibration.depth_offset_m
    valid=np.isfinite(distance)&(distance>0)&~np.isin(raw,calibration.invalid_values)
    if calibration.depth_kind=='range':ray=ray/np.linalg.norm(ray,axis=1)[:,None]
    xyz=np.full((len(ray),3),np.nan);xyz[valid]=ray[valid]*distance[valid,None]
    return xyz,valid


def _validate_graph(graph,calibration):
    nodes=graph.get('nodes',[]);edges=graph.get('edges',[])
    if [n.get('id') for n in nodes]!=list(range(len(nodes))):raise ValueError('Contiguous ordered node IDs required')
    pixels=[]
    for n in nodes:
        if any(isinstance(n.get(k),bool) or not isinstance(n.get(k),int) for k in ('x','y')):
            raise ValueError('Graph nodes must have integer image coordinates')
        if not isinstance(n.get('inferred'),bool):raise ValueError('Explicit Step 4 node inferred flag required')
        pixels.append([n['x'],n['y']])
    pixels=np.asarray(pixels,dtype=float).reshape(-1,2)
    _rays(pixels,calibration)
    if len({tuple(p) for p in pixels})!=len(pixels):raise ValueError('Duplicate node coordinates')
    adjacency=[set() for _ in nodes]
    for e in edges:
        a,b=e.get('source'),e.get('target')
        if (not isinstance(a,int) or not isinstance(b,int) or a==b or
            not 0<=a<len(nodes) or not 0<=b<len(nodes) or b in adjacency[a]):
            raise ValueError('Invalid/duplicate graph edge')
        adjacency[a].add(b);adjacency[b].add(a)
    return pixels,adjacency


def lift_skeleton(graph, depth, calibration, branch_support, *,
                  infer_hidden_depth=False, max_endpoint_z_difference_m=.5):
    """Lift Step 3/4 graph without modifying it or the supplied depth/support.

    Measured = observed node + explicit branch-support evidence + valid depth.
    Inferred nodes NEVER read image depth, even when it is finite/nonzero.
    Optional hidden Z interpolation requires a simple inferred chain with exactly
    two measured boundary anchors. All other coordinates stay unsupported/null.
    Surface depth at a visible centreline is a surface proxy, not wood-axis GT.
    """
    raw=np.asarray(depth)
    if raw.ndim!=2 or raw.shape!=(calibration.height,calibration.width) or raw.dtype.kind not in 'buif':
        raise ValueError('Scalar depth must match calibration grid; RGB depth needs a verified decoder')
    support=binary_visible(branch_support)
    if support.shape!=raw.shape:raise ValueError('Branch support grid mismatch')
    if not isinstance(infer_hidden_depth,bool) or not np.isfinite(max_endpoint_z_difference_m) or max_endpoint_z_difference_m<=0:
        raise ValueError('Explicit inference switch and positive finite Z-jump threshold required')
    pixels,adjacency=_validate_graph(graph,calibration)
    output=copy.deepcopy(graph);nodes=output['nodes']
    for n in nodes:
        n.update(xyz_m=None,status_3d='unsupported',reason_3d='hidden_depth_not_measured' if n['inferred'] else 'no_branch_support')
        if not n['inferred'] and support[n['y'],n['x']]:
            xyz,valid=backproject([[n['x'],n['y']]],[raw[n['y'],n['x']]],calibration)
            n['reason_3d']='invalid_depth'
            if valid[0]:n.update(xyz_m=xyz[0].tolist(),status_3d='measured',reason_3d='supported_registered_depth_sample')
    rejected=[]
    unseen={n['id'] for n in nodes if n['inferred']}
    while unseen:
        seed=min(unseen);unseen.remove(seed);stack=[seed];component=set()
        while stack:
            i=stack.pop();component.add(i)
            for j in adjacency[i]&unseen:unseen.remove(j);stack.append(j)
        boundary=sorted({j for i in component for j in adjacency[i] if j not in component})
        reason=None
        if not infer_hidden_depth:reason='hidden_inference_disabled'
        elif len(boundary)!=2 or any(len(adjacency[i])!=2 for i in component):reason='not_a_two_anchor_simple_chain'
        elif any(nodes[j]['status_3d']!='measured' for j in boundary):reason='anchor_depth_unsupported'
        elif abs(nodes[boundary[0]]['xyz_m'][2]-nodes[boundary[1]]['xyz_m'][2])>max_endpoint_z_difference_m:
            reason='anchor_depth_discontinuity'
        if reason:
            rejected.append(dict(node_ids=sorted(component),reason=reason));continue
        start,end=boundary;path=[start];previous=None;current=start
        allowed=component|set(boundary)
        while current!=end:
            following=[j for j in adjacency[current] if j in allowed and j!=previous]
            if len(following)!=1:reason='ambiguous_chain';break
            previous,current=current,following[0]
            if current in path:reason='cyclic_chain';break
            path.append(current)
        if reason or set(path)!=allowed:
            rejected.append(dict(node_ids=sorted(component),reason=reason or 'incomplete_chain'));continue
        xy=pixels[path];arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        z0,z1=nodes[start]['xyz_m'][2],nodes[end]['xyz_m'][2]
        for k,i in enumerate(path[1:-1],1):
            z=z0+(z1-z0)*arc[k]/arc[-1]
            xyz=_rays([pixels[i]],calibration)[0]*z
            nodes[i].update(xyz_m=xyz.tolist(),status_3d='inferred',reason_3d='assumed_Z_linear_in_2D_arc_between_measured_anchors')
    supported=[n['xyz_m'] is not None for n in nodes]
    for e in output['edges']:
        a,b=nodes[e['source']],nodes[e['target']]
        status='unsupported' if not(supported[a['id']] and supported[b['id']]) else (
            'inferred' if 'inferred' in (a['status_3d'],b['status_3d']) else 'measured')
        e['status_3d']=status
        e['length_m']=None if status=='unsupported' else float(np.linalg.norm(np.asarray(a['xyz_m'])-b['xyz_m']))
    # Connectivity of the supported 3D subgraph, distinct from retained 2D graph.
    active={i for i,v in enumerate(supported) if v};components=[]
    while active:
        seed=min(active);active.remove(seed);stack=[seed];component=[]
        while stack:
            i=stack.pop();component.append(i)
            for j in adjacency[i]&active:active.remove(j);stack.append(j)
        components.append(sorted(component))
    output.update(calibration=asdict(calibration),units='metres',frame='rectified camera: X right,Y down,Z forward',
                  supported_3d_components=components,hidden_depth_rejections=rejected,
                  status_counts={s:sum(n['status_3d']==s for n in nodes) for s in ('measured','inferred','unsupported')})
    return output


def nonmetric_demo(graph, stored_codes, image_shape):
    """Image/code relief only. Physical XYZ is null for every real-data node.

    Display coordinates are u/(W-1), 1-v/(H-1), code/255, with NO pinhole camera,
    depth decoding or registration claim. Hidden display points use plane z=0
    only as an annotation carrier; their depth code is never sampled.
    """
    raw=np.asarray(stored_codes)
    if raw.shape!=tuple(image_shape) or raw.ndim!=2 or raw.dtype.kind not in 'buif':raise ValueError('Expected nominal paired scalar code image')
    h,w=raw.shape
    if min(h,w)<2 or not np.isfinite(raw).all() or (raw<0).any() or (raw>255).any():raise ValueError('Expected finite 0..255 display codes')
    output=copy.deepcopy(graph)
    for n in output['nodes']:
        x,y=n['x'],n['y']
        if not isinstance(x,int) or not isinstance(y,int) or not 0<=x<w or not 0<=y<h:raise ValueError('Node outside code image')
        hidden=n.get('inferred')
        if not isinstance(hidden,bool):raise ValueError('Explicit inferred flag required')
        n.update(xyz_m=None,status_3d='unsupported',reason_3d='real_calibration_encoding_registration_unverified',
                 display_uvw=[x/(w-1),1-y/(h-1),0. if hidden else float(raw[y,x])/255],
                 display_only=True,stored_code=None if hidden else float(raw[y,x]))
    for e in output['edges']:e.update(status_3d='unsupported',length_m=None)
    output.update(units='none; image/code display only',metric_reconstruction_supported=False,
                  display_warning='Code relief is not physical depth or shape; RGB-depth registration and branch attribution unverified')
    return output
