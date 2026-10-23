"""Run a 2D mask-assisted baseline. Default input is the existing synthetic fixture."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_tree_project.baseline import visible_only_baseline

ROOT = Path(__file__).resolve().parents[1]


def run(mask_path, rgb_path, output, provenance):
    mask_path, rgb_path, output = mask_path.resolve(strict=True), rgb_path.resolve(strict=True), output.resolve()
    if provenance not in ('synthetic','manual_visible','predicted_visible'):
        raise ValueError('Declare visible-mask provenance')
    raw = (ROOT/'data/raw').resolve()
    if output == raw or raw in output.parents or output in raw.parents:
        raise ValueError('Output must not overlap raw data')
    # Also forbid overwriting either source, including a source with an output filename.
    if output in mask_path.parents or output in rgb_path.parents:
        raise ValueError('Output directory must not contain inputs')
    sources = {p:(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in (mask_path,rgb_path)}
    with Image.open(mask_path) as im:
        if im.mode not in ('1','L'):
            raise ValueError('Visible mask must be single channel; no implicit conversion')
        mask = np.array(im)
    with Image.open(rgb_path) as im:
        rgb = im.convert('RGB')
    if mask.shape != (rgb.height,rgb.width):
        raise ValueError('RGB and visible mask must share the native image grid; no automatic alignment')
    start = time.perf_counter()
    result = visible_only_baseline(mask)
    elapsed = time.perf_counter()-start
    output.mkdir(parents=True,exist_ok=True)
    for name in ('prediction','skeleton'):
        Image.fromarray(result[name].astype(np.uint8)*255).save(output/f'{name}.png')
    display = np.array(rgb)
    visible = result['prediction']
    display[visible] = (.6*display[visible]+.4*np.array([0,200,255])).astype(np.uint8)
    display[result['skeleton']] = [255,255,0]
    Image.fromarray(display).save(output/'overlay.png')
    graph = result['graph']
    (output/'graph.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
    changed = [str(p) for p,(sha,mtime) in sources.items() if hashlib.sha256(p.read_bytes()).hexdigest()!=sha or p.stat().st_mtime_ns!=mtime]
    if changed:
        raise RuntimeError(f'Source changed: {changed}')
    report = dict(method='visible-mask-only Zhang-Suen + pixel graph',provenance=provenance,
        warning='Mask-assisted 2D prototype; no real accuracy, GT registration or metric 3D validation.',
        source_files=[dict(path=str(p),sha256=s[0],mtime_ns=s[1]) for p,s in sources.items()],
        shape=list(mask.shape),visible_pixels=int(visible.sum()),skeleton_pixels=int(result['skeleton'].sum()),
        components=len(graph['components']),endpoints=len(graph['endpoint_ids']),
        junction_pixels=len(graph['junction_pixel_ids']),total_length_px=graph['total_length_px'],
        inference_seconds=elapsed,changed_sources=changed)
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--visible-mask',type=Path)
    parser.add_argument('--rgb',type=Path)
    parser.add_argument('--provenance',choices=('synthetic','manual_visible','predicted_visible'))
    parser.add_argument('--output',type=Path,default=ROOT/'results/visible_only_baseline')
    args = parser.parse_args()
    if args.visible_mask is None and args.rgb is None and args.provenance is None:
        args.visible_mask,args.rgb,args.provenance = ROOT/'data/demo/visible.png',ROOT/'data/demo/rgb.png','synthetic'
    elif args.visible_mask is None or args.rgb is None or args.provenance is None:
        parser.error('Custom inputs require --visible-mask, --rgb and --provenance together')
    print(json.dumps(run(args.visible_mask,args.rgb,args.output,args.provenance),indent=2))

if __name__ == '__main__':
    main()
