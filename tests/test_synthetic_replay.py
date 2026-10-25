"""Regression tests for a verification policy that must not hide graph changes."""
import copy
import importlib.util
from pathlib import Path
import pytest

def verifier():
    path=Path(__file__).parents[1]/'scripts/replay_saved_synthetic.py'
    spec=importlib.util.spec_from_file_location('synthetic_replay',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def graph():
    return dict(nodes=[dict(id=0,x=2,y=3,inferred=False,status_3d='measured',xyz_m=[0.,0.,3.]),
                       dict(id=1,x=3,y=3,inferred=True,status_3d='unsupported',xyz_m=None)],
                edges=[dict(source=0,target=1,inferred=True,status_3d='unsupported',length_m=None,length_px=1.)],
                supported_3d_components=[[0]],status_counts=dict(measured=1,inferred=0,unsupported=1),
                total_length_px=1.,calibration=dict(fx=140.,cx=96.))

def test_float64_roundoff_passes_including_near_zero():
    m=verifier();expected=graph();actual=copy.deepcopy(expected)
    actual['nodes'][0]['xyz_m']=[m.ATOL/2,0.,3.+1e-11]
    actual['edges'][0]['length_px']+=1e-12
    actual['total_length_px']+=1e-12
    stats=m.compare_graphs(actual,expected)
    assert stats['max_absolute_difference']>0 and stats['max_tolerance_fraction']<=1

@pytest.mark.parametrize('field,value',[
    ('id',True),('id',0.),('id',1),('x',2.),('x',3),('y',4),
    ('inferred',0),('inferred',True),('status_3d','inferred')])
def test_node_identity_pixels_and_status_are_exact(field,value):
    expected=graph();actual=copy.deepcopy(expected);actual['nodes'][0][field]=value
    with pytest.raises(AssertionError):verifier().compare_graphs(actual,expected)

@pytest.mark.parametrize('kind',['connectivity','components','node_order','edge_flag','null','count','calibration','missing_key','extra_key'])
def test_discrete_structure_and_calibration_changes_fail(kind):
    expected=graph();actual=copy.deepcopy(expected)
    if kind=='connectivity':actual['edges'][0]['source']=1
    elif kind=='components':actual['supported_3d_components']=[[0,1]]
    elif kind=='node_order':actual['nodes'].reverse()
    elif kind=='edge_flag':actual['edges'][0]['inferred']=False
    elif kind=='null':actual['nodes'][1]['xyz_m']=[0.,0.,0.]
    elif kind=='count':actual['status_counts']['measured']=1.+1e-12
    elif kind=='calibration':actual['calibration']['fx']+=1e-12
    elif kind=='missing_key':actual['nodes'][0].pop('status_3d')
    elif kind=='extra_key':actual['nodes'][0]['extra']=True
    with pytest.raises(AssertionError):verifier().compare_graphs(actual,expected)

@pytest.mark.parametrize('bad',[1e-7,float('nan'),float('inf'),True])
def test_excessive_or_invalid_coordinate_change_fails(bad):
    expected=graph();actual=copy.deepcopy(expected);actual['nodes'][0]['xyz_m'][0]=bad
    with pytest.raises(AssertionError):verifier().compare_graphs(actual,expected)

def test_policy_does_not_accept_shape_or_excessive_edge_length_changes():
    expected=graph();actual=copy.deepcopy(expected);actual['nodes'][0]['xyz_m'].append(0.)
    with pytest.raises(AssertionError):verifier().compare_graphs(actual,expected)
    actual=copy.deepcopy(expected);actual['edges'][0]['length_px']+=1e-5
    with pytest.raises(AssertionError):verifier().compare_graphs(actual,expected)

@pytest.mark.parametrize('coordinate',[0.,3.])
@pytest.mark.parametrize('fraction',[.99,1.01])
def test_documented_absolute_and_relative_tolerance_boundary(coordinate,fraction):
    m=verifier();expected=graph();actual=copy.deepcopy(expected)
    expected['nodes'][0]['xyz_m'][0]=coordinate
    actual['nodes'][0]['xyz_m'][0]=coordinate+fraction*(m.ATOL+m.RTOL*abs(coordinate))
    if fraction<1:m.compare_graphs(actual,expected)
    else:
        with pytest.raises(AssertionError):m.compare_graphs(actual,expected)

@pytest.mark.parametrize('difference',[1e-13,1e-7])
def test_metric_edge_lengths_use_geometry_tolerance(difference):
    m=verifier();expected=graph();expected['edges'][0]['length_m']=.03
    actual=copy.deepcopy(expected);actual['edges'][0]['length_m']+=difference
    if difference<1e-12:m.compare_graphs(actual,expected)
    else:
        with pytest.raises(AssertionError):m.compare_graphs(actual,expected)
