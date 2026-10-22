"""A provisional CSV manifest for paired RGB-D images and branch labels.

The Monash download's true directory layout has not been verified yet; this
schema is a stable *internal interface*, not a claim about original filenames.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

REQUIRED_COLUMNS = (
    "sample_id", "season", "rgb_path", "depth_path",
    "visible_mask_path", "whole_mask_path",
)
OPTIONAL_COLUMNS = ("tree_id", "calibration_path")
SEASONS = {"summer", "autumn", "winter"}


@dataclass(frozen=True)
class Sample:
    """Metadata for one registered RGB-D observation and two branch masks.

    Attributes:
        sample_id: Dataset-unique sample identifier.
        season: One of summer, autumn, winter.
        rgb_path: RGB image, relative to manifest directory.
        depth_path: Depth map, relative to manifest directory.
        visible_mask_path: Annotation of directly visible branch pixels.
        whole_mask_path: Annotation of whole (visible+occluded) branches.
        tree_id: Optional tree identity for leakage-aware splits.
        calibration_path: Optional per-camera calibration JSON.
    """

    sample_id: str
    season: str
    rgb_path: Path
    depth_path: Path
    visible_mask_path: Path
    whole_mask_path: Path
    tree_id: str | None = None
    calibration_path: Path | None = None


def load_manifest(manifest_path: str | Path) -> list[Sample]:
    """Read an internal-format manifest and validate its metadata.

    Args:
        manifest_path: Path to a UTF-8 CSV file.

    Returns:
        List of records with absolute resolved paths.

    Raises:
        FileNotFoundError: If the manifest is missing.
        ValueError: If columns, identifiers or seasons are invalid.
    """
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    records: list[Sample] = []
    observed: set[str] = set()
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        cols = set(reader.fieldnames or [])
        missing = set(REQUIRED_COLUMNS) - cols
        if missing:
            raise ValueError(f"Missing manifest columns: {sorted(missing)}")
        for lineno, row in enumerate(reader, start=2):
            sample_id = (row.get("sample_id") or "").strip()
            season = (row.get("season") or "").strip().lower()
            if not sample_id or sample_id in observed:
                raise ValueError(f"Empty or duplicate sample_id at row {lineno}")
            if season not in SEASONS:
                raise ValueError(f"Unsupported season '{season}' at row {lineno}")
            observed.add(sample_id)

            def relative_file(col: str) -> Path:
                raw = (row.get(col) or "").strip()
                if not raw:
                    raise ValueError(f"Missing {col} at row {lineno}")
                return (manifest_path.parent / raw).resolve()

            calib = (row.get("calibration_path") or "").strip()
            records.append(Sample(
                sample_id=sample_id, season=season,
                rgb_path=relative_file("rgb_path"),
                depth_path=relative_file("depth_path"),
                visible_mask_path=relative_file("visible_mask_path"),
                whole_mask_path=relative_file("whole_mask_path"),
                tree_id=(row.get("tree_id") or "").strip() or None,
                calibration_path=(manifest_path.parent / calib).resolve() if calib else None,
            ))
    if not records:
        raise ValueError("Manifest contains no samples")
    return records
