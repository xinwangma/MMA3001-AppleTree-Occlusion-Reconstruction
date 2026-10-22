"""Read-only recursive Monash inventory; JSON goes to stdout, never into raw data.

Usage: python scripts/inspect_monash_dataset.py [--root PATH]
All files are hashed, all PNGs fully decoded. No image or filesystem writes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
from PIL import Image


NAME = re.compile(r"^(R\d+)([A-Za-z])(\d+)_(Summer|Winter)_(RGB|D|GT)-((?:R\d+[A-Za-z]\d+_RGB_)?\d{1,2}-\d{1,2}-\d{1,2})\.png$")
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data/raw/monash_y_tree/TreeID"


def parse_name(name: str) -> dict | None:
    match = NAME.fullmatch(name)
    if not match:
        return None
    row, marker, number, season, modality, timestamp = match.groups()
    return dict(tree_id=f"{row}{marker}{number}", row=row, marker=marker,
                number=number, season=season, modality=modality, timestamp=timestamp,
                embedded_source_id=timestamp.split('_')[0] if '_' in timestamp else None)


def inspect(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    records, errors, directories = [], [], []
    groups = defaultdict(list)
    before = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append(dict(path=relative, error="Symlink skipped"))
            continue
        if path.is_dir():
            directories.append(relative)
            continue
        stat = path.stat()
        before[relative] = (stat.st_size, stat.st_mtime_ns)
        record = dict(path=relative, folder=path.parent.relative_to(root).as_posix(),
                      bytes=stat.st_size, extension=path.suffix.lower(),
                      sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      sample=parse_name(path.name))
        if path.suffix.lower() == ".png":
            try:
                with Image.open(path) as im:
                    im.load()
                    array = np.asarray(im)
                    record.update(format=im.format, mode=im.mode, size=list(im.size),
                                  dtype=str(array.dtype), minimum=int(array.min()),
                                  maximum=int(array.max()), metadata_keys=sorted(im.info),
                                  exif_tags={str(k): str(v) for k, v in im.getexif().items()},
                                  pixel_sha256=hashlib.sha256(array.tobytes()).hexdigest())
                    if record["sample"] and record["sample"]["modality"] in ("D", "GT"):
                        flat = array.reshape(-1, array.shape[-1]) if array.ndim == 3 else array.reshape(-1, 1)
                        # Packed integer colours avoid expensive per-pixel Python objects.
                        packed = np.zeros(len(flat), dtype=np.uint64)
                        for channel in range(flat.shape[1]):
                            packed = (packed << 16) | flat[:, channel].astype(np.uint64)
                        colours, counts = np.unique(packed, return_counts=True)
                        record.update(unique_colours=len(colours),
                                      zero_pixels=int(np.count_nonzero(np.all(flat == 0, axis=1))),
                                      pixels=len(flat),
                                      equal_channels=bool(np.all(flat == flat[:, :1])),
                                      top_colours=[dict(value=[int((int(c) >> (16 * j)) & 65535)
                                                                    for j in reversed(range(flat.shape[1]))],
                                                       count=int(n))
                                                   for c, n in sorted(zip(colours, counts), key=lambda pair: -int(pair[1]))[:8]])
            except Exception as exc:
                errors.append(dict(path=relative, error=f"{type(exc).__name__}: {exc}"))
        records.append(record)
        groups[record["folder"]].append(record)
    summaries = {}
    for folder, items in groups.items():
        samples = defaultdict(dict)
        duplicates = []
        for item in items:
            s = item["sample"]
            if s:
                key = (s["tree_id"], s["season"])
                if s["modality"] in samples[key]:
                    duplicates.append(item["path"])
                samples[key][s["modality"]] = item
        trees = sorted({tree for tree, _ in samples})
        mismatches, missing, timestamps = [], [], []
        for (tree, season), modalities in sorted(samples.items()):
            required = {"RGB", "D"} | ({"GT"} if folder == "Dataset (With Summer GT)" and season == "Summer" else set())
            if required - modalities.keys():
                missing.append([tree, season, sorted(required - modalities.keys())])
            if len({tuple(x.get("size", [])) for x in modalities.values()}) > 1:
                mismatches.append([tree, season])
            if len({x["sample"]["timestamp"] for x in modalities.values()}) > 1:
                timestamps.append([tree, season])
        summaries[folder] = dict(files=len(items), bytes=sum(x["bytes"] for x in items),
            counts=dict(Counter(f'{x["sample"]["season"]}/{x["sample"]["modality"]}' if x["sample"] else "unclassified" for x in items)),
            trees=len(trees), tree_ids=trees, rows=dict(Counter(re.match(r"R\d+", t)[0] for t in trees)),
            markers=dict(Counter(re.search(r"[A-Za-z](?=\d+$)", t)[0] for t in trees)),
            paired_season_trees=sum((t, "Summer") in samples and (t, "Winter") in samples for t in trees),
            missing_modalities=missing, duplicate_modalities=duplicates, dimension_mismatches=mismatches,
            timestamp_mismatches=timestamps,
            image_signatures=dict(Counter(f'{x.get("format")}/{x.get("mode")}/{x.get("size")}/{x.get("dtype")}' for x in items)))
    left = {Path(x["path"]).name: x for x in groups.get("Dataset", [])}
    right = {Path(x["path"]).name: x for x in groups.get("Dataset (With Summer GT)", [])}
    common = sorted(left.keys() & right.keys())
    # Content comparison also finds duplicates when filenames/tree markers differ.
    right_hashes = defaultdict(list)
    for item in right.values():
        right_hashes[item["sha256"]].append(item["path"])
    comparison = dict(common_names=len(common), identical_bytes=sum(left[n]["sha256"] == right[n]["sha256"] for n in common),
                      changed_common_names=[n for n in common if left[n]["sha256"] != right[n]["sha256"]],
                      only_dataset=sorted(left.keys() - right.keys()), only_with_gt=sorted(right.keys() - left.keys()),
                      dataset_files_matching_any_gt_folder_content=sum(x["sha256"] in right_hashes for x in left.values()),
                      content_matches=[dict(source=x["path"], targets=right_hashes[x["sha256"]]) for x in left.values() if x["sha256"] in right_hashes])
    pixel_hashes = {x.get("pixel_sha256") for x in right.values() if x.get("pixel_sha256")}
    comparison["dataset_files_matching_any_gt_folder_pixels"] = sum(
        x.get("pixel_sha256") in pixel_hashes for x in left.values())
    changed = [rel for rel, signature in before.items()
               if not (root / rel).exists() or ((root / rel).stat().st_size, (root / rel).stat().st_mtime_ns) != signature]
    return dict(root=str(root), directories=directories, file_count=len(records),
                total_bytes=sum(x["bytes"] for x in records), extensions=dict(Counter(x["extension"] for x in records)),
                folders=summaries, comparison=comparison, errors=errors,
                changed_during_inspection=changed, files=records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    report = inspect(args.root)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return int(bool(report["errors"] or report["changed_during_inspection"]))


if __name__ == "__main__":
    raise SystemExit(main())
