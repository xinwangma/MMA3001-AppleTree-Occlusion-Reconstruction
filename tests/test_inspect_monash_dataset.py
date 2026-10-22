"""Synthetic coverage for missing pairs, renamed duplicates and damaged images."""
import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location(
    "inspect_monash_dataset", Path(__file__).parents[1] / "scripts/inspect_monash_dataset.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_recursive_comparison_and_read_only(tmp_path):
    base = tmp_path / "Dataset"
    other = tmp_path / "Dataset (With Summer GT)"
    base.mkdir()
    other.mkdir()
    source = base / "R01U01_Summer_RGB-1-2-3.png"
    Image.fromarray(np.zeros((3, 4, 3), dtype=np.uint8)).save(source)
    (other / "R01N01_Summer_RGB-1-2-3.png").write_bytes(source.read_bytes())
    Image.fromarray(np.ones((2, 4), dtype=np.uint16)).save(base / "R01U01_Summer_D-1-2-4.png")
    snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    result = module.inspect(tmp_path)
    assert result['file_count'] == 3
    assert result['comparison']['common_names'] == 0
    assert result['comparison']['dataset_files_matching_any_gt_folder_content'] == 1
    assert result['folders']['Dataset']['dimension_mismatches'] == [['R01U01', 'Summer']]
    assert result['folders']['Dataset']['timestamp_mismatches'] == [['R01U01', 'Summer']]
    assert result['folders']['Dataset (With Summer GT)']['missing_modalities'] == [['R01N01', 'Summer', ['D', 'GT']]]
    assert result['errors'] == result['changed_during_inspection'] == []
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}


def test_corrupt_png_is_reported(tmp_path):
    (tmp_path / 'broken.png').write_bytes(b'not a PNG')
    result = module.inspect(tmp_path)
    assert len(result['errors']) == 1
    assert result['errors'][0]['path'] == 'broken.png'


def test_filename_contract():
    assert module.parse_name('R23U47_Winter_D-13-39-24.png')['tree_id'] == 'R23U47'
    assert module.parse_name('R04U01_Winter_D-R04N03_RGB_12-17-14.png')['embedded_source_id'] == 'R04N03'
    assert module.parse_name('FANK_Sat.png') is None
