"""Conservative 2D gap completion on the Step 3 pixel skeleton.

Anatomical identity and occlusion are explicit inputs, never inferred from GT.
Coordinates are native image pixels (x right, y down).
"""
from __future__ import annotations
import math
import numpy as np
from PIL import Image, ImageDraw
from .baseline import binary_visible, pixel_graph


ROLES = {'trunk', 'left_primary', 'right_primary'}

# Conservative float64 decision band, fixed independently of evaluation scores.
# A 32*eps dot-product perturbation near +/-1 gives acos uncertainty about
# sqrt(64*eps) radians = 6.83e-6 degrees; round UP to a fixed 1e-5 degree band.
# This is an engineering roundoff guard, not a bound on arbitrary ill-conditioned
# least-squares input, a sensor tolerance, or a change to the physical threshold.
ANGLE_BOUNDARY_GUARD_DEG = 1e-5
ANGLE_BOUNDARY_POLICY = 'strict_below_angular_guard_v1'


def _angular_threshold_state(value_deg, threshold_deg):
    """Classify a finite angle as below/ambiguous/above a threshold.

    Eligibility requires strictly below T-guard. Equality and every value in
    [T-guard,T+guard] are ambiguous and conservatively rejected. No rounding
    to decimal places or score-dependent tolerance is used.
    """
    if not math.isfinite(value_deg) or not math.isfinite(threshold_deg):
        raise ValueError('Finite angles and thresholds required')
    if value_deg < threshold_deg-ANGLE_BOUNDARY_GUARD_DEG:
        return 'below'
    if value_deg > threshold_deg+ANGLE_BOUNDARY_GUARD_DEG:
        return 'above'
    return 'ambiguous'


def detect_candidate_gaps(skeleton, *, max_gap_px=80., max_angle_deg=65.,
                          max_curvature_deg=45., support_points=8,
                          endpoint_roles=None):
    """Enumerate geometry-only hypotheses, rejecting nonunique endpoint matches.

    No occlusion is asserted. An optional mapping (x,y)->role supplies reviewed
    identities. Otherwise image-upright Y geometry assigns provisional roles
    around a lower-trunk axis. These are screening labels, not anatomical truth.
    Returned candidates still require an occlusion region for complete_gaps.
    Angular gates use strict_below_angular_guard_v1: a fixed 1e-5 degree band
    around each threshold is rejected, including exact mathematical equality.
    """
    s = binary_visible(skeleton)
    if (not np.isfinite(max_gap_px) or max_gap_px <= 1 or
        not np.isfinite(max_angle_deg) or not 0 < max_angle_deg < 90 or
        not np.isfinite(max_curvature_deg) or not 0 <= max_curvature_deg <= 180 or
        not isinstance(support_points, int) or support_points < 3):
        raise ValueError('Invalid candidate detection parameters')
    graph = pixel_graph(s)
    components = {i:k for k,c in enumerate(graph['components']) for i in c}
    ends = graph['endpoint_ids']
    xy = np.array([[n['x'],n['y']] for n in graph['nodes']], float).reshape(-1,2)
    if not len(xy):
        return dict(candidates=[], rejected=[], assumptions=['upright image Y-tree geometry'])
    axis = float(np.median(xy[xy[:,1] >= np.quantile(xy[:,1], .8),0]))
    width = max(8., .08*float(np.ptp(xy[:,0])))
    def role(point):
        if endpoint_roles is not None:
            return endpoint_roles.get(tuple(map(int,point)))
        return 'trunk' if abs(point[0]-axis) <= width else ('left_primary' if point[0]<axis else 'right_primary')
    def angle(a,b):
        return math.degrees(math.acos(float(np.clip(a@b,-1,1))))
    # Multiple spatially separate visible forks are outside the main-Y model.
    junctions = set(graph['junction_pixel_ids'])
    groups = 0
    while junctions:
        groups += 1
        stack = [junctions.pop()]
        while stack:
            i = stack.pop()
            near = [j for j in junctions if np.max(np.abs(xy[i]-xy[j])) <= 2]
            junctions.difference_update(near); stack.extend(near)
    records, rejected = [], []
    for k,i in enumerate(ends):
        for j in ends[k+1:]:
            if components[i] == components[j]:
                continue
            a,b = xy[i],xy[j]
            distance = float(np.linalg.norm(b-a))
            record = dict(id=f'gap_{i}_{j}', start=a.astype(int).tolist(), end=b.astype(int).tolist(),
                          distance_px=distance, occlusion_status='unverified',
                          identity_status='provided' if endpoint_roles is not None else 'provisional_geometry')
            reason = None
            first,second = [_trace(graph,n,support_points) for n in (i,j)]
            if not 1 < distance <= max_gap_px:
                reason = 'endpoint_distance'
            elif groups > 1:
                reason = 'multiple_visible_forks_outside_main_Y_scope'
            elif min(len(first),len(second)) < 3:
                reason = 'insufficient_visible_support'
            else:
                direction = (b-a)/distance
                angles = [angle(_tangent(first),direction),angle(_tangent(second),-direction)]
                turns = [angle(_tangent(p[:3]),_tangent(p[-3:])) for p in (first,second)]
                record.update(direction_angles_deg=angles,local_turn_deg=turns)
                r1,r2 = role(a),role(b)
                record['branch'] = r1
                if r1 not in ROLES or r1 != r2:
                    reason = 'incompatible_or_unknown_main_branch_identity'
                elif _angular_threshold_state(max(angles), max_angle_deg) != 'below':
                    state = _angular_threshold_state(max(angles), max_angle_deg)
                    reason = 'direction_threshold_numerically_ambiguous' if state == 'ambiguous' else 'direction_inconsistent'
                    if state == 'ambiguous':
                        record.update(boundary_quantity='direction',boundary_value_deg=max(angles),
                                      boundary_threshold_deg=max_angle_deg,boundary_guard_deg=ANGLE_BOUNDARY_GUARD_DEG,
                                      boundary_policy=ANGLE_BOUNDARY_POLICY)
                elif _angular_threshold_state(max(turns), max_curvature_deg) != 'below':
                    state = _angular_threshold_state(max(turns), max_curvature_deg)
                    reason = 'local_curvature_threshold_numerically_ambiguous' if state == 'ambiguous' else 'local_curvature_unstable'
                    if state == 'ambiguous':
                        record.update(boundary_quantity='local_curvature',boundary_value_deg=max(turns),
                                      boundary_threshold_deg=max_curvature_deg,boundary_guard_deg=ANGLE_BOUNDARY_GUARD_DEG,
                                      boundary_policy=ANGLE_BOUNDARY_POLICY)
                elif r1 == 'trunk' and abs(direction[1]) < .7:
                    reason = 'trunk_gap_not_vertical_in_upright_Y_model'
                elif r1 != 'trunk' and abs(direction[0]) < .2:
                    reason = 'primary_branch_gap_not_outward_in_upright_Y_model'
            if reason:
                record['reason'] = reason; rejected.append(record)
            else:
                records.append(record)
    counts = {}
    for r in records:
        for key in ('start','end'):
            p = tuple(r[key]); counts[p] = counts.get(p,0)+1
    candidates = []
    for r in records:
        if any(counts[tuple(r[key])] > 1 for key in ('start','end')):
            r['reason'] = 'ambiguous_multiple_compatible_matches'; rejected.append(r)
        else:
            r['uncertainty'] = 'geometry_only; occlusion_and_anatomy_require_RGB_review'
            candidates.append(r)
    return dict(candidates=candidates,rejected=rejected,
                assumptions=['upright main Y tree','at most one visible fork',
                             'no confirmed occlusion from skeleton alone'],trunk_axis_x=axis)


def _trace(graph, endpoint, count):
    adjacency = [[] for _ in graph['nodes']]
    for e in graph['edges']:
        adjacency[e['source']].append(e['target'])
        adjacency[e['target']].append(e['source'])
    path, previous, current = [], None, endpoint
    for _ in range(count):
        n = graph['nodes'][current]
        path.append([n['x'], n['y']])
        following = [i for i in adjacency[current] if i != previous]
        if len(following) != 1 or (current != endpoint and n['degree'] != 2):
            break
        previous, current = current, following[0]
    return np.asarray(path, dtype=float)


def _tangent(points):
    # Local least-squares line against cumulative arc length, facing outwards.
    distance = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    slope = np.linalg.lstsq(np.c_[np.ones(len(points)), distance], points, rcond=None)[0][1]
    size = np.linalg.norm(slope)
    if size < 1e-10:
        raise ValueError('degenerate tangent support')
    return -slope / size


def fit_quadratic(first, second, tangent_weight=1.0):
    """Fit P(t)=A+t(B-A)+t(t-1)C with exact endpoints.

    Support t is its projection onto the endpoint chord, including t outside
    [0,1]. Minimize mean squared visible support residual plus weighted mean
    squared endpoint derivative residual. Derivative targets have chord length
    and directions estimated from local visible geometry. A quadratic cannot
    generally satisfy both endpoint directions exactly; they are soft constraints.
    """
    first, second = np.asarray(first, float), np.asarray(second, float)
    for p in (first, second):
        if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
            raise ValueError('Each endpoint needs at least three finite 2D support points')
    if not np.isfinite(tangent_weight) or tangent_weight <= 0:
        raise ValueError('tangent_weight must be positive and finite')
    a, b = first[0], second[0]
    delta = b-a
    length = np.linalg.norm(delta)
    if length < 1e-10:
        raise ValueError('Distinct endpoints required')
    support = np.vstack((first[1:], second[1:]))
    t = (support-a) @ delta / length**2
    weight = 1 / math.sqrt(len(support))
    design = list(t*(t-1)*weight)
    target = list((support-a-t[:, None]*delta)*weight)
    tw = math.sqrt(tangent_weight/2)
    design.extend([-tw, tw])
    target.extend([(length*_tangent(first)-delta)*tw,
                   (-length*_tangent(second)-delta)*tw])
    c = np.linalg.lstsq(np.asarray(design)[:, None], np.asarray(target), rcond=None)[0][0]
    return a, b, c


def complete_gaps(skeleton, gaps, occlusion_mask, method='linear', *,
                  max_gap_px=80., support_points=8, max_angle_deg=65.,
                  tangent_weight=1.):
    """Complete explicit gap requests; return accepted/rejected records and graph.

    gaps: dictionaries with unique id, branch in ROLES, start/end integer [x,y].
    Endpoints must be in different components, have sufficient unbranched local
    support, face each other, and be used at most once. All added pixels must be
    in occlusion_mask. Raster paths touching unrelated geometry or introducing
    cycles/junctions are rejected. Requests are processed in caller order.
    This function accepts a skeleton, not a thick visible mask; use Step 3 first.
    """
    original = binary_visible(skeleton)
    occlusion = binary_visible(occlusion_mask)
    if original.shape != occlusion.shape:
        raise ValueError('Occlusion mask must use the skeleton native image grid')
    if method not in {'linear', 'quadratic'}:
        raise ValueError('method must be linear or quadratic')
    if (not np.isfinite(max_gap_px) or max_gap_px <= 0 or
        not isinstance(support_points, int) or support_points < 3 or
        not np.isfinite(max_angle_deg) or not 0 < max_angle_deg < 90 or
        not np.isfinite(tangent_weight) or tangent_weight <= 0):
        raise ValueError('Invalid completion parameters')
    graph = pixel_graph(original)
    lookup = {(n['x'], n['y']): n['id'] for n in graph['nodes']}
    components = {i:k for k,c in enumerate(graph['components']) for i in c}
    completed = original.copy()
    accepted, rejected, used, seen = [], [], set(), set()
    for request in gaps:
        record = dict(request)
        try:
            identity = request.get('id')
            if not isinstance(identity, str) or not identity or identity in seen:
                raise ValueError('Gap id must be a unique nonempty string')
            seen.add(identity)
            if request.get('branch') not in ROLES:
                raise ValueError('Explicit trunk/left_primary/right_primary identity required')
            ids = []
            for key in ('start', 'end'):
                p = np.asarray(request.get(key))
                if p.shape != (2,) or p.dtype.kind not in 'iu' or tuple(p) not in lookup:
                    raise ValueError('Endpoint must be an integer skeleton coordinate')
                i = lookup[tuple(p)]
                if i not in graph['endpoint_ids'] or i in used:
                    raise ValueError('Endpoint is not terminal or is already used')
                ids.append(i)
            if components[ids[0]] == components[ids[1]]:
                raise ValueError('Endpoints must belong to different visible components')
            first, second = [_trace(graph, i, support_points) for i in ids]
            if min(len(first), len(second)) < 3:
                raise ValueError('Insufficient local visible support')
            a, b = first[0], second[0]
            delta = b-a
            length = np.linalg.norm(delta)
            if not 1 < length <= max_gap_px:
                raise ValueError('Gap length outside eligible range')
            direction = delta/length
            cosine = math.cos(math.radians(max_angle_deg))
            if min(_tangent(first) @ direction, _tangent(second) @ -direction) < cosine:
                raise ValueError('Endpoint tangents do not face the gap')
            c = np.zeros(2) if method == 'linear' else fit_quadratic(first, second, tangent_weight)[2]
            # Bound the derivative to sample at <= 0.25 px along the curve.
            count = int(math.ceil(4*(length+np.linalg.norm(c))))+1
            t = np.linspace(0, 1, count)
            points = a+t[:, None]*delta+(t*(t-1))[:, None]*c
            h,w = original.shape
            if ((points < 0).any() or (points[:,0] > w-1).any() or (points[:,1] > h-1).any()):
                raise ValueError('Curve leaves image grid')
            image = Image.new('1', (w,h))
            ImageDraw.Draw(image).line([tuple(p) for p in np.rint(points).astype(int)], fill=1)
            path = np.asarray(image, dtype=bool)
            added = path & ~completed
            if not added.any() or (added & ~occlusion).any():
                raise ValueError('Added path lacks explicit occlusion support')
            candidate = completed | path
            before, after = pixel_graph(completed), pixel_graph(candidate)
            # Adding a simple bridge must reduce components by exactly one and
            # preserve cycle rank and number of junction pixels.
            rank = lambda g: len(g['edges'])-len(g['nodes'])+len(g['components'])
            if (len(after['components']) != len(before['components'])-1 or
                rank(after) != rank(before) or
                len(after['junction_pixel_ids']) != len(before['junction_pixel_ids'])):
                raise ValueError('Path intersects geometry or changes topology beyond a bridge')
            completed = candidate
            used.update(ids)
            record.update(method=method, inferred=True, chord_length_px=float(length),
                          quadratic_coefficient=c.tolist(), curve_xy=points.tolist(),
                          added_pixel_count=int(added.sum()))
            accepted.append(record)
        except ValueError as error:
            record['reason'] = str(error)
            rejected.append(record)
    inferred = completed & ~original
    final_graph = pixel_graph(completed)
    for n in final_graph['nodes']:
        n['inferred'] = bool(inferred[n['y'], n['x']])
    for e in final_graph['edges']:
        e['inferred'] = final_graph['nodes'][e['source']]['inferred'] or final_graph['nodes'][e['target']]['inferred']
    return dict(skeleton=completed, inferred_mask=inferred, graph=final_graph,
                accepted=accepted, rejected=rejected, method=method)
