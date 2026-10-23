"""Visible-mask-only 2D baseline; no hidden completion, RGB segmentation or 3D."""
from __future__ import annotations
import math
import numpy as np


def binary_visible(mask):
    """Copy an explicit binary mask (bool, 0/1 or 0/255); reject soft labels."""
    a = np.asarray(mask)
    if a.ndim != 2 or 0 in a.shape or a.dtype.kind not in 'buif':
        raise ValueError('Expected a nonempty 2D binary visible mask')
    if not np.isfinite(a).all() or not (np.isin(a, [0,1]).all() or np.isin(a, [0,255]).all()):
        raise ValueError('Expected binary 0/1 or 0/255 visible mask')
    return a.astype(bool, copy=True)


def thin_visible(mask):
    """Zhang-Suen two-subiteration thinning to convergence, zero outside frame.

    Simultaneous deletion within each pass. Output is always a subset of input;
    no closing, gap bridging, pruning or largest-component selection is applied.
    """
    a = binary_visible(mask)
    while True:
        changed = False
        for phase in (0,1):
            p = np.pad(a, 1)
            n = [p[:-2,1:-1], p[:-2,2:], p[1:-1,2:], p[2:,2:],
                 p[2:,1:-1], p[2:,:-2], p[1:-1,:-2], p[:-2,:-2]]
            count = np.sum(n, axis=0)
            transitions = np.sum([~n[i] & n[(i+1)%8] for i in range(8)],axis=0)
            if phase == 0:
                keep1, keep2 = n[0]&n[2]&n[4], n[2]&n[4]&n[6]
            else:
                keep1, keep2 = n[0]&n[2]&n[6], n[0]&n[4]&n[6]
            remove = a & (count>=2) & (count<=6) & (transitions==1) & ~keep1 & ~keep2
            if remove.any():
                a[remove] = False
                changed = True
        if not changed:
            return a


def pixel_graph(skeleton):
    """Build deterministic undirected pixel graph, coordinates x=column,y=row.

    Eight-neighbour adjacency with diagonal shortcuts suppressed whenever either
    orthogonal intermediary exists. Nodes represent pixels, not fitted anatomical
    joints. Lengths are pixel units. Disconnected pieces and cycles are retained.
    """
    a = binary_visible(skeleton)
    coords = [tuple(map(int, yx)) for yx in np.argwhere(a)]
    ids = {p:i for i,p in enumerate(coords)}
    edges, adjacent = [], [set() for _ in coords]
    for i,(y,x) in enumerate(coords):
        for dy,dx in ((0,1),(1,-1),(1,0),(1,1)):
            j = ids.get((y+dy,x+dx))
            if j is None:
                continue
            if dy and dx and ((y,x+dx) in ids or (y+dy,x) in ids):
                continue
            edges.append(dict(source=i,target=j,length_px=math.hypot(dx,dy),inferred=False))
            adjacent[i].add(j); adjacent[j].add(i)
    nodes = [dict(id=i,x=x,y=y,degree=len(adjacent[i]),inferred=False) for i,(y,x) in enumerate(coords)]
    unseen, components = set(range(len(coords))), []
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        stack, component = [seed], []
        while stack:
            i = stack.pop(); component.append(i)
            for j in sorted(adjacent[i]):
                if j in unseen:
                    unseen.remove(j); stack.append(j)
        components.append(sorted(component))
    return dict(coordinate_system='image pixels; x right, y down; integer pixel indices',
                nodes=nodes, edges=edges, components=components,
                endpoint_ids=[n['id'] for n in nodes if n['degree']==1],
                junction_pixel_ids=[n['id'] for n in nodes if n['degree']>=3],
                isolated_pixel_ids=[n['id'] for n in nodes if n['degree']==0],
                total_length_px=sum(e['length_px'] for e in edges))


def visible_only_baseline(visible_mask):
    """Return unchanged prediction mask, subset skeleton and pixel graph.

    Only visible_mask is accepted. Whole/amodal labels and depth are deliberately
    absent from this inference API. Output quality depends on the supplied mask;
    an 'inferred=False' flag means no added geometry, not verified physical truth.
    """
    prediction = binary_visible(visible_mask)
    skeleton = thin_visible(prediction)
    return dict(prediction=prediction,skeleton=skeleton,graph=pixel_graph(skeleton))
