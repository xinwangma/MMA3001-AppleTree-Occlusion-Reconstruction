"""Prepare native-RGB-only review inputs; never manufacture visible annotations.

Reuses the Step 2 report selection/hashes. This is readiness checking, not a
real-data reconstruction benchmark. Existing review packages are never overwritten.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
from PIL import Image
from run_visible_baseline import run as run_baseline

ROOT = Path(__file__).resolve().parents[1]


def prepare(report_path, raw_root, output):
    output = output.resolve()
    results = (ROOT/'results').resolve()
    if results not in output.parents:
        raise ValueError('Review package must be below repository results/')
    if output.exists():
        raise ValueError('Use a new output directory to preserve existing review work')
    report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    raw_root = raw_root.resolve(strict=True)
    ids = [name.removesuffix('_comparison.png') for name in report['comparison_images']]
    if output == raw_root or raw_root in output.parents or output in raw_root.parents:
        raise ValueError("Review package must not overlap raw data")
    records = []
    for tree_id in ids:
        candidates = [s for s in report['sources'] if Path(s['path']).name.startswith(tree_id+'_Summer_RGB-')]
        if len(candidates) != 1:
            raise ValueError(f'Nonunique source for {tree_id}')
        source = candidates[0]
        path = (raw_root/source['path']).resolve(strict=True)
        if raw_root not in path.parents:
            raise ValueError('Source path escapes raw root')
        before = path.read_bytes()
        sha = hashlib.sha256(before).hexdigest()
        mtime = path.stat().st_mtime_ns
        if sha != source['sha256']:
            raise ValueError(f'Step 2 source hash mismatch: {path}')
        with Image.open(path) as im:
            im.load()
            if im.size != (640,480) or im.mode != 'RGB':
                raise ValueError(f'Unexpected native RGB schema: {path}')
        records.append((tree_id,path,before,sha,mtime))
    output.mkdir(parents=True)
    (output/'rgb').mkdir()
    rows = []
    for tree_id,path,content,sha,mtime in records:
        copied = output/'rgb'/path.name
        copied.write_bytes(content)
        if hashlib.sha256(copied.read_bytes()).hexdigest() != sha:
            raise RuntimeError(f'Copied RGB differs: {copied}')
        rows.append(dict(sample_id=tree_id,rgb_path='rgb/'+path.name,source_path=str(path),
            source_sha256=sha,visible_mask_path='',annotation_status='pending',review_status='pending',
            reviewer='',review_notes='Step 2 GT mismatch; do not reuse amodal GT' if tree_id=='R04N01' else '',
            accepted_for_native_2d='no',accepted_for_whole_gt_scoring='no'))
    with (output/'review_manifest.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    # Negative control: an actual Summer GT must fail the native visible-grid check.
    tree_id,rgb_path,*_ = records[0]
    gt_path=rgb_path.with_name(rgb_path.name.replace('_RGB-','_GT-'))
    gt_sha=hashlib.sha256(gt_path.read_bytes()).hexdigest()
    gt_mtime=gt_path.stat().st_mtime_ns
    try:
        run_baseline(gt_path,rgb_path,output/'rejected_gt_output','manual_visible')
    except ValueError as exc:
        if 'native image grid' not in str(exc):
            raise
        negative_control=dict(sample_id=tree_id,rejected=True,reason=str(exc),
            warning='Dimension guard only; same-size amodal labels cannot be identified automatically.')
    else:
        raise RuntimeError('Unexpected acceptance of mismatched real GT')
    changed=[str(p) for _,p,_,sha,mtime in records if hashlib.sha256(p.read_bytes()).hexdigest()!=sha or p.stat().st_mtime_ns!=mtime]
    if hashlib.sha256(gt_path.read_bytes()).hexdigest()!=gt_sha or gt_path.stat().st_mtime_ns!=gt_mtime:
        changed.append(str(gt_path))
    if changed:
        raise RuntimeError(f'Original inputs changed: {changed}')
    summary=dict(selection='Existing Step 2 first lexicographic Summer RGB per row prefix',
        selected_real_rgb_count=len(records),native_size=[640,480],copied_rgb_hashes_match=True,
        source_hashes_match_step2=True,source_files_checked=len(records)+1,changed_sources=changed,
        supplied_visible_masks=0,accepted_real_samples=0,real_accuracy_evaluated=False,
        negative_control=negative_control,
        next_requirement='Independent native-grid visible branch masks and human review; no GT-derived pseudo labels.')
    (output/'readiness_report.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (output/'ANNOTATION_GUIDE.md').write_text('''# Native RGB visible-branch review

All 20 masks and reviews are PENDING. No empty placeholder mask is supplied:
empty foreground is a valid algorithm input and must not be mistaken for a label.

Annotate only visibly supported central trunk and two main-arm surfaces in these
640 x 480 RGBs. Do not view amodal GT or winter images while constructing visible
labels. Leave foliage, fruit, supports, background trees and hidden continuations
unlabelled; record ambiguous regions in review_notes instead of guessing through
gaps. For uncertainty beyond a binary label, exclude the sample from quantitative
scoring or establish an explicit ignored-region evaluation protocol first.

Save single-channel L binary 0/255 PNGs at native size outside raw data. Review the
mask over the RGB at full resolution. A separate human reviewer should check
visible support, target-tree identity, alignment and coverage. Record annotator
and reviewer identities, dates, policy version and any uncertainty in review_notes.
Fill visible_mask_path and statuses only after annotation and review. Mark
accepted_for_native_2d=yes only after review; this manifest is a review checklist,
not an automatic loader or independent ground truth certification.

R04N01 has a known Step 2 amodal alignment exception. Its independent visible mask
may support native-grid prototype checking after review, but not whole-GT scoring.
Keep accepted_for_whole_gt_scoring=no for every sample until that separate mapping
and annotation protocol are verified. Row-prefix coverage is not a held-out split;
physical tree identity and independence still need confirmation before benchmarking.

Run scripts/run_visible_baseline.py with the reviewed mask, matching RGB and
--provenance manual_visible. Inspect subset/gap behaviour and graph overlay.
Do not report mask-vs-itself scores as segmentation accuracy. Skeleton validation
needs independent centreline/topology references or explicit human adjudication.
''',encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=ROOT/'results/alignment_candidates/report.json')
    parser.add_argument('--raw-root',type=Path,default=ROOT/'data/raw/monash_y_tree/TreeID')
    parser.add_argument('--output',type=Path,default=ROOT/'results/visible_only_baseline/real_review')
    args=parser.parse_args()
    print(json.dumps(prepare(args.report,args.raw_root,args.output),indent=2))
