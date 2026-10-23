import importlib.util
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from apple_tree_project.alignment import geometry, transform_rgb, mask_to_rgb, boundary, edge_proxy


def test_explicit_geometry():
    assert geometry((640,480), 'stretch') == (0.4, 256/480, 0, 0)
    assert geometry((640,480), 'center_crop') == (256/480, 256/480, pytest.approx(-128/3), 0)
    assert geometry((640,480), 'letterbox') == (0.4, 0.4, 0, 32)


def test_landmark_mapping_and_inverse_binary():
    rgb = np.zeros((480,640,3), dtype=np.uint8)
    rgb[230:250,310:330] = 255
    mask = np.zeros((256,256), dtype=np.uint8)
    mask[124:132,124:132] = 255
    for method in ('stretch','center_crop','letterbox'):
        out = np.asarray(transform_rgb(Image.fromarray(rgb), method))
        assert out[128,128,0] == 255
        back = np.asarray(mask_to_rgb(mask,(640,480),method))
        assert back[240,320] == 255
        assert set(np.unique(back)) == {0,255}


def test_crop_and_padding_distinguish_hypotheses():
    rgb = Image.new('RGB',(640,480),'white')
    padded = np.asarray(transform_rgb(rgb,'letterbox'))
    assert not padded[:32].any() and padded[32:224].all() and not padded[224:].any()
    mask = np.full((256,256),255,dtype=np.uint8)
    crop = np.asarray(mask_to_rgb(mask,(640,480),'center_crop'))
    assert not crop[:,:80].any() and crop[:,80:560].all() and not crop[:,560:].any()


def test_invalid_inputs_and_boundary():
    with pytest.raises(ValueError): geometry((640,480),'unknown')
    with pytest.raises(ValueError): geometry((0,480),'stretch')
    with pytest.raises(ValueError): mask_to_rgb(np.ones((2,3)),(640,480),'stretch')
    with pytest.raises(ValueError): mask_to_rgb(np.ones((3,3)),(640,480),'stretch')
    assert boundary(np.ones((3,3))).sum() == 8
    assert edge_proxy(Image.new('RGB',(3,3)),np.zeros((3,3))) is None


def test_runner_evidence_and_source_preservation(tmp_path):
    spec = importlib.util.spec_from_file_location('comparison',Path(__file__).parents[1]/'scripts/compare_annotation_alignment.py')
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
    spec.loader.exec_module(module)
    root = tmp_path/'raw'
    folder = root/'Dataset (With Summer GT)'
    folder.mkdir(parents=True)
    Image.new('RGB',(640,480),'white').save(folder/'R01N01_Summer_RGB-1-2-3.png')
    mask = np.zeros((256,256),dtype=np.uint8); mask[100:200,120:140] = 255
    Image.fromarray(mask).save(folder/'R01N01_Summer_GT-1-2-3.png')
    before = {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in folder.iterdir()}
    report = module.run(root,tmp_path/'out')
    assert report['pair_count'] == 1 and report['changed_sources'] == []
    assert (tmp_path/'out'/'R01N01_comparison.png').is_file()
    assert len((tmp_path/'out'/'scores.csv').read_text().splitlines()) == 4
    assert before == {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before}
    with pytest.raises(ValueError): module.run(root,root/'outputs')
