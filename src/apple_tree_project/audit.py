"""Command-line audit for a proposed paired RGB-D/annotation manifest.

Only image metadata and provisional label alignment are inspected here. A
successful audit DOES NOT verify camera units, calibration accuracy or the
quality of labels. Actual dataset-specific decoding is a later step.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image
from .manifest import load_manifest, Sample
from .metrics import to_mask


def audit_sample(sample: Sample) -> dict:
    """Check file existence, image sizes, depth values and label containment.

    Args:
        sample: One RGB-D observation and paired label paths.

    Returns:
        JSON-serialisable dictionary with errors, warnings and basic metadata.
    """
    errors: list[str] = []
    warnings: list[str] = []
    paths = {"rgb": sample.rgb_path, "depth": sample.depth_path,
             "visible": sample.visible_mask_path, "whole": sample.whole_mask_path}
    if sample.calibration_path is not None:
        paths["calibration"] = sample.calibration_path
    for key, path in paths.items():
        if not path.is_file():
            errors.append(f"Missing {key} file: {path}")
    summary = {"sample_id": sample.sample_id, "season": sample.season,
               "tree_id": sample.tree_id, "errors": errors, "warnings": warnings}
    if errors:
        return summary

    try:
        with Image.open(sample.rgb_path) as image:
            rgb = np.asarray(image.convert("RGB"))
        with Image.open(sample.depth_path) as image:
            depth = np.asarray(image)
        with Image.open(sample.visible_mask_path) as image:
            visible = to_mask(np.asarray(image.convert("L")))
        with Image.open(sample.whole_mask_path) as image:
            whole = to_mask(np.asarray(image.convert("L")))
        image_shape = rgb.shape[:2]
        for label, data in (("depth", depth), ("visible", visible), ("whole", whole)):
            if data.ndim != 2 or data.shape != image_shape:
                errors.append(f"{label} shape {data.shape} != RGB shape {image_shape}")
        if depth.ndim == 2:
            if not np.issubdtype(depth.dtype, np.number):
                errors.append("Depth image is not numeric")
            elif not np.all(np.isfinite(depth)) or np.any(depth < 0):
                errors.append("Depth image contains negative or nonfinite values")
        if visible.shape == whole.shape:
            disjoint = int(np.count_nonzero(visible & ~whole))
            if disjoint:
                warnings.append(f"{disjoint} visible pixels are absent from whole annotation")
        summary.update({"image_height": int(image_shape[0]),
                        "image_width": int(image_shape[1]),
                        "depth_dtype": str(depth.dtype),
                        "visible_pixels": int(np.count_nonzero(visible)),
                        "whole_pixels": int(np.count_nonzero(whole))})
        if sample.calibration_path:
            with sample.calibration_path.open(encoding="utf-8") as handle:
                calib = json.load(handle)
            # These names are the project's *target adapter format*, not
            # a statement about fields in the downloaded Monash data.
            for field in ("fx", "fy", "cx", "cy", "depth_unit_to_m"):
                if field not in calib:
                    warnings.append(f"Calibration field '{field}' not found")
            for field in ("fx", "fy", "depth_unit_to_m"):
                if field in calib and (not isinstance(calib[field], (int, float)) or calib[field] <= 0):
                    errors.append(f"Invalid calibration field '{field}'")
        else:
            warnings.append("Camera calibration unavailable: metric 3D lifting is not yet supported")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"Could not decode image or calibration: {exc}")
    return summary


def audit_manifest(manifest: str | Path) -> dict:
    """Audit each sample and return overall counts and per-sample evidence.

    Args:
        manifest: CSV in the internal sample format.

    Returns:
        JSON-compatible report including all failures and warnings.
    """
    samples = load_manifest(manifest)
    rows = [audit_sample(s) for s in samples]
    return {
        "source_manifest": str(Path(manifest).resolve()),
        "sample_count": len(samples),
        "season_counts": dict(Counter(s.season for s in samples)),
        "unique_known_tree_ids": len({s.tree_id for s in samples if s.tree_id}),
        "missing_tree_id_count": sum(s.tree_id is None for s in samples),
        "error_count": sum(len(r["errors"]) for r in rows),
        "warning_count": sum(len(r["warnings"]) for r in rows),
        "samples": rows,
    }


def main() -> int:
    """Run command-line auditing and optionally save a JSON test report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="Internal-format CSV containing RGB-D sample paths")
    parser.add_argument("--json-output", type=Path, help="Write full audit report JSON here")
    args = parser.parse_args()
    report = audit_manifest(args.manifest)
    print(f"Samples={report['sample_count']}  Errors={report['error_count']}  "
          f"Warnings={report['warning_count']}")
    print(f"Seasons={report['season_counts']}  Unknown tree IDs={report['missing_tree_id_count']}")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved report: {args.json_output}")
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
