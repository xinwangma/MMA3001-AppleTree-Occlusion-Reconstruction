from pathlib import Path
import numpy as np
from PIL import Image
from apple_tree_project.audit import audit_manifest


def test_audit_one_valid_sample(tmp_path):
    Image.fromarray(np.zeros((6, 8, 3), dtype=np.uint8)).save(tmp_path / "rgb.png")
    Image.fromarray(np.ones((6, 8), dtype=np.uint16)).save(tmp_path / "depth.png")
    Image.fromarray(np.zeros((6, 8), dtype=np.uint8)).save(tmp_path / "visible.png")
    Image.fromarray(np.zeros((6, 8), dtype=np.uint8)).save(tmp_path / "whole.png")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("sample_id,season,rgb_path,depth_path,visible_mask_path,whole_mask_path\n"
                        "x,summer,rgb.png,depth.png,visible.png,whole.png\n", encoding="utf-8")
    report = audit_manifest(manifest)
    assert report["sample_count"] == 1
    assert report["error_count"] == 0
    assert report["missing_tree_id_count"] == 1
    assert report["warning_count"] >= 1  # no camera calibration


def test_audit_missing_file_is_error(tmp_path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("sample_id,season,rgb_path,depth_path,visible_mask_path,whole_mask_path\n"
                        "x,winter,rgb.png,depth.png,visible.png,whole.png\n", encoding="utf-8")
    report = audit_manifest(manifest)
    assert report["error_count"] == 4


def test_audit_dimension_mismatch(tmp_path):
    Image.fromarray(np.zeros((6, 8, 3), dtype=np.uint8)).save(tmp_path / "rgb.png")
    Image.fromarray(np.ones((6, 7), dtype=np.uint16)).save(tmp_path / "depth.png")
    Image.fromarray(np.zeros((6, 8), dtype=np.uint8)).save(tmp_path / "visible.png")
    Image.fromarray(np.zeros((6, 8), dtype=np.uint8)).save(tmp_path / "whole.png")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("sample_id,season,rgb_path,depth_path,visible_mask_path,whole_mask_path\n"
                        "x,summer,rgb.png,depth.png,visible.png,whole.png\n", encoding="utf-8")
    report = audit_manifest(manifest)
    assert report["error_count"] == 1
