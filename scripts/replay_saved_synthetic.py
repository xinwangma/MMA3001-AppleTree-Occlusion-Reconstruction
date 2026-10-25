"""Replay saved Step 5 synthetic inputs; exact structure, tolerant geometry.

Only node xyz_m, edge length_m/length_px and total_length_px are tolerant.
Acceptance: abs(actual-expected) <= 1e-12 + 1e-10*abs(expected).
At 3 m this is 3.01e-10 m, far below the 3 cm coverage threshold and
approximately 8 mm rasterisation RMSE. This accommodates float64 arithmetic
and LAPACK roundoff; it does not allow different raster paths or topology.
Calibration inputs and every other field, including integer/boolean types,
remain exact. Missing coordinates remain exactly null. Nonfinite values fail.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys

RTOL = 1e-10
ATOL = 1e-12


def _tolerant(path):
    return (path == ('total_length_px',) or
            (len(path) == 4 and path[0] == 'nodes' and isinstance(path[1], int)
             and path[2] == 'xyz_m' and isinstance(path[3], int)) or
            (len(path) == 3 and path[0] == 'edges' and isinstance(path[1], int)
             and path[2] in ('length_m', 'length_px')))


def compare_graphs(actual, expected):
    """Raise AssertionError with field path on mismatch; return numeric diagnostics.

    Pass JSON-compatible graph dictionaries. List order, key sets, lengths,
    identities, connectivity, flags and exact-field primitive types must match.
    The tolerances are fixed verification policy, not CLI tuning parameters.
    """
    diagnostics = dict(float_values_compared=0, max_absolute_difference=0.,
                       max_tolerance_fraction=0., rtol=RTOL, atol=ATOL)

    def compare(a, b, path):
        label = repr(path)
        if _tolerant(path) and b is not None:
            if (type(a) not in (float, int) or type(b) not in (float, int)
                    or not math.isfinite(a) or not math.isfinite(b)):
                raise AssertionError(f'{label}: finite numerical geometry required')
            difference = abs(a-b)
            limit = ATOL+RTOL*abs(b)
            if difference > limit:
                raise AssertionError(f'{label}: {a!r} != {b!r}; difference {difference} exceeds {limit}')
            diagnostics['float_values_compared'] += 1
            diagnostics['max_absolute_difference'] = max(diagnostics['max_absolute_difference'], difference)
            diagnostics['max_tolerance_fraction'] = max(diagnostics['max_tolerance_fraction'], difference/limit)
            return
        if type(a) is not type(b):
            raise AssertionError(f'{label}: type mismatch {type(a).__name__} vs {type(b).__name__}')
        if isinstance(b, dict):
            if a.keys() != b.keys():
                raise AssertionError(f'{label}: key set changed')
            for key in b:
                compare(a[key], b[key], path+(key,))
        elif isinstance(b, list):
            if len(a) != len(b):
                raise AssertionError(f'{label}: list length changed')
            for index, (item, target) in enumerate(zip(a, b)):
                compare(item, target, path+(index,))
        elif isinstance(b, float) and not (math.isfinite(a) and math.isfinite(b)):
            raise AssertionError(f'{label}: nonfinite value')
        elif a != b:
            raise AssertionError(f'{label}: exact value changed: {a!r} vs {b!r}')

    compare(actual, expected, ())
    return diagnostics


def replay(evidence_root, source_root):
    import numpy as np
    from PIL import Image
    source_root = Path(source_root).resolve()
    sys.path.insert(0, str(source_root/'src'))
    from apple_tree_project.baseline import pixel_graph
    from apple_tree_project.completion import detect_candidate_gaps, complete_gaps
    from apple_tree_project.reconstruction3d import Calibration, lift_skeleton

    folder = Path(evidence_root).resolve()
    reports = []
    for scene in ('constant_z', 'varying_z', 'curved_z'):
        camera = Calibration(**json.loads((folder/f'{scene}_calibration.json').read_text()))
        with Image.open(folder/f'{scene}_visible.png') as image:
            visible = np.array(image)>0
        with Image.open(folder/f'{scene}_occlusion.png') as image:
            occlusion = np.array(image)>0
        depth = np.load(folder/f'{scene}_input_depth_m.npy', allow_pickle=False)
        detection = detect_candidate_gaps(visible,max_gap_px=80,max_angle_deg=80,max_curvature_deg=70)
        for method in ('visible_only', 'linear', 'quadratic'):
            graph = (pixel_graph(visible) if method == 'visible_only' else
                     complete_gaps(visible,detection['candidates'],occlusion,method,max_angle_deg=80)['graph'])
            for infer in ((False,) if method == 'visible_only' else (False, True)):
                actual = lift_skeleton(graph,depth,camera,visible,infer_hidden_depth=infer)
                suffix = 'inferred_z' if infer else 'measured_only'
                name = f'{scene}_{method}_{suffix}'
                expected = json.loads((folder/f'{name}.json').read_text())
                # JSON converts Calibration.invalid_values tuple to a list.
                actual = json.loads(json.dumps(actual,allow_nan=False))
                reports.append(dict(output=name,**compare_graphs(actual,expected)))
    return dict(passed=len(reports),evidence_root=str(folder),source_root=str(source_root),
                policy='Exact structure/types/status/calibration; finite geometry uses abs(a-b)<=atol+rtol*abs(b)',
                rtol=RTOL,atol=ATOL,graphs=reports)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=root)
    parser.add_argument('--evidence-root',type=Path,default=root/'results/step5_3d_reconstruction/synthetic')
    parser.add_argument('--report',type=Path,help='New JSON output file; existing files are never overwritten')
    args = parser.parse_args()
    if args.report is not None and args.report.exists():
        parser.error('Use a new report path; refusing to overwrite existing results')
    report = replay(args.evidence_root,args.source_root)
    if args.report is not None:
        with args.report.open('x',encoding='utf-8') as stream:
            json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__ == '__main__':
    main()
