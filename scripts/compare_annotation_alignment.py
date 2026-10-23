"""Compare fixed alignment hypotheses; writes derived evidence outside raw data only."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from apple_tree_project.alignment import CANDIDATES, geometry, transform_rgb, mask_to_rgb, edge_proxy, overlay
from inspect_monash_dataset import parse_name, DEFAULT_ROOT


def run(root, output):
    root, output = root.resolve(strict=True), output.resolve()
    if output == root or root in output.parents or output in root.parents:
        raise ValueError('Output and raw root must be separate directory trees')
    folder = root / 'Dataset (With Summer GT)'
    pairs = []
    for gt in sorted(folder.glob('*_Summer_GT-*.png')):
        rgb = gt.with_name(gt.name.replace('_GT-', '_RGB-'))
        if not rgb.is_file():
            raise ValueError(f'Missing RGB: {rgb}')
        pairs.append((rgb, gt))
    if not pairs:
        raise ValueError('No Summer pairs')
    output.mkdir(parents=True, exist_ok=True)
    rows, sources, selected, seen = [], [], [], set()
    for rgb_path, gt_path in pairs:
        sample = parse_name(gt_path.name)
        row_id = sample['row']
        review = row_id not in seen
        seen.add(row_id)
        for path in (rgb_path, gt_path):
            sources.append(dict(path=str(path.relative_to(root)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                mtime_ns=path.stat().st_mtime_ns))
        with Image.open(rgb_path) as im:
            rgb = im.convert('RGB')
        with Image.open(gt_path) as im:
            mask = im.copy()
        if rgb.size != (640,480) or mask.size != (256,256) or mask.mode != 'L' or not np.isin(np.asarray(mask), [0,255]).all():
            raise ValueError(f'Unexpected input schema: {gt_path}')
        if review:
            sheet = Image.new('RGB', (1024, 570), 'white')
            draw = ImageDraw.Draw(sheet)
            draw.text((5,5), sample['tree_id'] + ' | hypotheses only; yellow outline / magenta GT', fill='black')
            sheet.paste(rgb.resize((256,192)), (0,42))
            sheet.paste(mask.convert('RGB'), (0,300))
            draw.text((5,25), 'Original RGB (aspect preserved)', fill='black')
            draw.text((5,280), 'Original GT', fill='black')
        for i, method in enumerate(CANDIDATES):
            transformed = transform_rgb(rgb, method)
            sx, sy, tx, ty = geometry(rgb.size, method)
            yy, xx = np.indices((256,256))
            valid = ((xx+.5-tx)/sx >= 0) & ((xx+.5-tx)/sx < 640) & ((yy+.5-ty)/sy >= 0) & ((yy+.5-ty)/sy < 480)
            fg = np.asarray(mask) > 0
            rows.append(dict(tree_id=sample['tree_id'], candidate=method,
                edge_proxy=edge_proxy(transformed, mask),
                foreground_outside_source_fraction=float((fg & ~valid).sum()/fg.sum())))
            if review:
                x = (i+1)*256
                sheet.paste(overlay(transformed, mask), (x,42))
                sheet.paste(overlay(rgb, mask_to_rgb(mask, rgb.size, method)).resize((256,192)), (x,340))
                draw.text((x+4,25), method, fill='black')
                draw.text((x+4,315), 'GT mapped back to RGB', fill='black')
        if review:
            name = sample['tree_id'] + '_comparison.png'
            sheet.save(output/name)
            selected.append(name)
    changed = [s['path'] for s in sources if hashlib.sha256((root/s['path']).read_bytes()).hexdigest() != s['sha256'] or (root/s['path']).stat().st_mtime_ns != s['mtime_ns']]
    if changed:
        raise RuntimeError(f'Source files changed: {changed}')
    with (output/'scores.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = dict(pair_count=len(pairs), visual_selection='First lexicographic Summer pair per row prefix',
        comparison_images=selected, source_files_checked=len(sources), changed_sources=changed,
        candidates={m:dict(geometry=geometry((640,480),m),
            mean_edge_proxy=float(np.mean([r['edge_proxy'] for r in rows if r['candidate']==m])),
            mean_foreground_outside_source_fraction=float(np.mean([r['foreground_outside_source_fraction'] for r in rows if r['candidate']==m]))) for m in CANDIDATES},
        warning='Edge proxy is confounded by foliage/background and amodal labels; no accuracy or confirmed registration.',
        sources=sources)
    (output/'report.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k != 'sources'}, indent=2))
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, default=Path('results/alignment_candidates'))
    args = parser.parse_args()
    run(args.root, args.output)
