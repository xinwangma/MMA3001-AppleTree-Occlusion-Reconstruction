import csv
from pathlib import Path
import pytest
from apple_tree_project.manifest import load_manifest


def write_manifest(path: Path, rows, cols=None):
    fields = cols or ["sample_id", "season", "rgb_path", "depth_path",
                      "visible_mask_path", "whole_mask_path", "tree_id"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def example(sample_id="one", season="winter"):
    return dict(sample_id=sample_id, season=season, rgb_path="a.png",
                depth_path="b.png", visible_mask_path="c.png",
                whole_mask_path="d.png", tree_id="tree_1")


def test_manifest_load(tmp_path):
    path = tmp_path / "manifest.csv"
    write_manifest(path, [example()])
    item, = load_manifest(path)
    assert item.sample_id == "one"
    assert item.tree_id == "tree_1"
    assert item.rgb_path.is_absolute()


def test_duplicate_id_rejected(tmp_path):
    path = tmp_path / "manifest.csv"
    write_manifest(path, [example(), example()])
    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(path)


def test_invalid_season_rejected(tmp_path):
    path = tmp_path / "manifest.csv"
    write_manifest(path, [example(season="spring")])
    with pytest.raises(ValueError, match="Unsupported season"):
        load_manifest(path)


def test_missing_column_rejected(tmp_path):
    path = tmp_path / "manifest.csv"
    cols = ["sample_id", "season", "rgb_path", "visible_mask_path", "whole_mask_path"]
    write_manifest(path, [{k: v for k, v in example().items() if k in cols}], cols)
    with pytest.raises(ValueError, match="Missing manifest columns"):
        load_manifest(path)
