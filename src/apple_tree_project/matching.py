"""Fork-anchored Y matching with conservative geometric and topology gates.

Roles inferred here are provisional geometry, never verified tree identity.
The original completion module and its fitters remain unchanged.
"""
import math
from collections import Counter
import numpy as np
from .baseline import binary_visible, pixel_graph
from .completion import _trace, _tangent, _angular_threshold_state

POLICY = dict(max_gap_px=80., max_angle_deg=65., max_curvature_deg=45.,
              support_points=12, fork_margin_px=3.)


def continuity_state(first, second, direction, max_angle_deg=65., max_curvature_deg=45.):
    """Compare full-support tangents and overlapping half-support tangents.

    Each half has at least three points. The fixed Step 6 v2 angular guard
    applies to both direction and curvature, including exact equality.
    """
    angle = lambda a, b: math.degrees(math.acos(float(np.clip(a @ b, -1, 1))))
    angles = [angle(_tangent(first), direction), angle(_tangent(second), -direction)]
    turns = [angle(_tangent(p[:(len(p)+1)//2]), _tangent(p[len(p)//2:]))
             for p in (first, second)]
    for name, values, limit in (("direction", angles, max_angle_deg),
                                 ("curvature", turns, max_curvature_deg)):
        state = _angular_threshold_state(max(values), limit)
        if state != "below":
            return name + "_" + state, angles, turns
    return None, angles, turns


def detect_anchored_gaps(skeleton, *, max_gap_px=80., max_angle_deg=65.,
                         max_curvature_deg=45., support_points=12, fork_margin_px=3.):
    """Match a fork-connected terminal to an unbranched detached fragment.

    A single acyclic three-arm visible fork is required. Arm labels come from
    their terminals relative to the fork, rather than the lower-image axis.
    Detached terminals must lie consistently in the same upright Y sector.
    Nonunique matches are rejected, with no ranking or greedy tie breaking.
    """
    if (not np.isfinite([max_gap_px,max_angle_deg,max_curvature_deg,fork_margin_px]).all()
        or max_gap_px <= 1 or not 0 < max_angle_deg < 90
        or not 0 <= max_curvature_deg <= 180 or fork_margin_px <= 0
        or not isinstance(support_points,int) or support_points < 6):
        raise ValueError("Invalid anchored matching parameters")
    graph = pixel_graph(binary_visible(skeleton))
    xy = np.array([[n['x'],n['y']] for n in graph['nodes']],float).reshape(-1,2)
    adjacency = [set() for _ in xy]
    for e in graph['edges']:
        adjacency[e['source']].add(e['target']); adjacency[e['target']].add(e['source'])
    component = {i:k for k,c in enumerate(graph['components']) for i in c}
    junctions = set(graph['junction_pixel_ids'])
    ends = graph['endpoint_ids']
    pairs = [(i,j) for k,i in enumerate(ends) for j in ends[k+1:] if component[i]!=component[j]]
    records=[]; rejected=[]; context=None
    if not junctions:
        context='missing_visible_fork'
    elif len({component[i] for i in junctions}) != 1 or np.ptp(xy[list(junctions)],axis=0).max()>4:
        context='multiple_or_extended_visible_forks'
    elif len(graph['edges'])-len(xy)+len(graph['components']) != 0:
        context='non_tree_visible_topology'
    roles={}; anchor=None; centre=None
    if context is None:
        anchor=component[next(iter(junctions))]
        centre=xy[list(junctions)].mean(axis=0)
        def sector(point):
            dx,dy=point-centre
            if dy > fork_margin_px: return 'trunk'
            if dy < -fork_margin_px and abs(dx)>fork_margin_px:
                return 'left_primary' if dx<0 else 'right_primary'
            return None
        remaining=set(graph['components'][anchor])-junctions
        arms=[]
        while remaining:
            stack=[remaining.pop()]; arm=set(stack)
            while stack:
                for j in adjacency[stack.pop()] & remaining:
                    remaining.remove(j);arm.add(j);stack.append(j)
            terminals=[i for i in ends if i in arm]
            if len(terminals)!=1:
                context='fork_arm_not_simple';break
            endpoint=terminals[0]; roles[endpoint]=sector(xy[endpoint]);arms.append(arm)
        if len(arms)!=3 or set(roles.values())!={'trunk','left_primary','right_primary'}:
            context='fork_roles_ambiguous'
        for k,c in enumerate(graph['components']):
            if k==anchor: continue
            terminals=[i for i in ends if i in c]
            labels=[sector(xy[i]) for i in terminals]
            if len(terminals)==2 and labels[0] is not None and labels[0]==labels[1]:
                for i in terminals: roles[i]=labels[0]
    for i,j in pairs:
        a,b=xy[i],xy[j]; length=float(np.linalg.norm(b-a))
        record=dict(id=f'anchored_{i}_{j}',start=a.astype(int).tolist(),end=b.astype(int).tolist(),
                    distance_px=length,identity_status='provisional_fork_topology',occlusion_status='unverified')
        reason=context
        if reason is None:
            if not 1<length<=max_gap_px: reason='endpoint_distance'
            elif (component[i]==anchor)+(component[j]==anchor)!=1: reason='requires_one_fork_anchor'
            elif roles.get(i) is None or roles.get(i)!=roles.get(j): reason='branch_identity_ambiguous'
            else:
                first,second=[_trace(graph,n,support_points) for n in (i,j)]
                if min(len(first),len(second))<6: reason='insufficient_visible_support'
                else:
                    reason,angles,turns=continuity_state(first,second,(b-a)/length,max_angle_deg,max_curvature_deg)
                    record.update(direction_angles_deg=angles,local_turn_deg=turns,branch=roles[i])
        if reason:
            rejected.append(dict(record,reason=reason))
        else: records.append(record)
    counts=Counter(tuple(r[k]) for r in records for k in ('start','end'))
    candidates=[]
    for r in records:
        if any(counts[tuple(r[k])]>1 for k in ('start','end')):
            rejected.append(dict(r,reason='ambiguous_multiple_compatible_matches'))
        else: candidates.append(r)
    return dict(candidates=candidates,rejected=rejected,context_rejection=context,
                fork_xy=None if centre is None else centre.tolist(),
                assumptions=['upright isolated main Y','one visible acyclic fork',
                             'provisional roles are not verified object identity'])
