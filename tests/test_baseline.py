import importlib.util
from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageDraw
from apple_tree_project.baseline import binary_visible, thin_visible, pixel_graph, visible_only_baseline
from apple_tree_project.metrics import hidden_branch_recall


def test_thick_y_connectivity_and_idempotence():
    im = Image.new('L',(65,65))
    d = ImageDraw.Draw(im)
    for line in ((32,58,32,32),(32,32,8,8),(32,32,56,8)):
        d.line(line,fill=255,width=5)
    mask = np.array(im)
    before = mask.copy()
    r = visible_only_baseline(mask)
    assert np.array_equal(mask,before)
    assert np.array_equal(r['prediction'],mask>0)
    assert not (r['skeleton'] & ~(mask>0)).any()
    assert 0 < r['skeleton'].sum() < (mask>0).sum()
    assert np.array_equal(thin_visible(r['skeleton']),r['skeleton'])
    assert len(r['graph']['components']) == 1
    assert len(r['graph']['endpoint_ids']) == 3
    assert len(r['graph']['junction_pixel_ids']) == 1


def test_gap_remains_and_hidden_recall_zero():
    whole = np.zeros((15,9),bool); whole[:,3:6] = True
    visible = whole.copy(); visible[6:9] = False
    r = visible_only_baseline(visible)
    assert not r['prediction'][6:9].any() and not r['skeleton'][6:9].any()
    assert len(r['graph']['components']) == 2
    assert hidden_branch_recall(r['prediction'],visible,whole) == 0
    assert all(not e['inferred'] for e in r['graph']['edges'])


def test_empty_and_isolated_pixel():
    r = visible_only_baseline(np.zeros((5,7),bool))
    assert r['graph']['nodes'] == [] and r['graph']['components'] == []
    a = np.zeros((5,7),bool); a[2,3] = True
    graph = visible_only_baseline(a)['graph']
    assert graph['isolated_pixel_ids'] == [0]
    assert graph['nodes'][0]['x'] == 3 and graph['nodes'][0]['y'] == 2


def test_graph_lengths_diagonal_and_no_shortcut():
    a = np.eye(5,dtype=bool)
    graph = pixel_graph(a)
    assert len(graph['components']) == 1
    assert graph['total_length_px'] == pytest.approx(4*np.sqrt(2))
    graph = pixel_graph(np.array([[1,1],[0,1]]))
    assert len(graph['edges']) == 2 and graph['total_length_px'] == 2


def test_cycle_and_noise_are_retained():
    a = np.zeros((9,12),bool)
    a[2,2:7] = a[6,2:7] = True
    a[2:7,2] = a[2:7,6] = True
    a[1,10] = True
    r = visible_only_baseline(a)
    assert len(r['graph']['components']) == 2
    assert len(r['graph']['isolated_pixel_ids']) == 1
    assert not r['graph']['endpoint_ids']
    assert len(r['graph']['edges']) == len(r['graph']['nodes'])-1


def test_border_foreground_and_single_row():
    for a in (np.ones((1,7),bool),np.ones((7,1),bool)):
        assert np.array_equal(thin_visible(a),a)
        assert len(pixel_graph(a)['endpoint_ids']) == 2
    a = np.zeros((15,10),bool); a[:,0:3] = True
    r = visible_only_baseline(a)
    assert r['skeleton'].any() and len(r['graph']['components']) == 1


@pytest.mark.parametrize('bad',[np.zeros((2,2,3)),np.zeros((0,2)),np.array([[np.nan]]),
    np.array([[.5]]),np.array([[-1]]),np.array([[1,255]]),np.array([['x']])])
def test_invalid_visible_masks(bad):
    with pytest.raises(ValueError): binary_visible(bad)


def test_runner_outputs_guards_and_preservation(tmp_path):
    spec = importlib.util.spec_from_file_location('run_baseline',Path(__file__).parents[1]/'scripts/run_visible_baseline.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    rgb,mask = tmp_path/'rgb.png',tmp_path/'visible.png'
    Image.new('RGB',(10,10)).save(rgb)
    a = np.zeros((10,10),np.uint8); a[2:8,4:6] = 255
    Image.fromarray(a).save(mask)
    before = {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in (rgb,mask)}
    report = module.run(mask,rgb,tmp_path/'out','synthetic')
    assert report['changed_sources'] == []
    assert {p.name for p in (tmp_path/'out').iterdir()} == {'prediction.png','skeleton.png','graph.json','overlay.png','report.json'}
    assert before == {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before}
    with pytest.raises(ValueError): module.run(mask,rgb,tmp_path,'synthetic')
    with pytest.raises(ValueError): module.run(mask,rgb,tmp_path/'out','whole_GT')
    Image.new('RGB',(11,10)).save(rgb)
    with pytest.raises(ValueError,match='native image grid'): module.run(mask,rgb,tmp_path/'out','synthetic')
