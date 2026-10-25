"""Lift a Step 3/4 graph with explicit, evidence-backed registered calibration."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from PIL import Image
from apple_tree_project.reconstruction3d import Calibration,lift_skeleton


def run(graph_path,depth_path,calibration_path,support_path,output,infer_hidden_depth=False):
    root=Path(__file__).resolve().parents[1];output=Path(output).resolve()
    if output.exists() or not any(output.is_relative_to(root/p) for p in ('results','data/processed')):
        raise ValueError('Use a new output directory below results or data/processed')
    graph=json.loads(Path(graph_path).read_text(encoding='utf-8'))
    # Accept either graph.json or Step 4 completion.json containing graph.
    if 'graph' in graph:graph=graph['graph']
    calibration=Calibration(**json.loads(Path(calibration_path).read_text(encoding='utf-8')))
    with Image.open(depth_path) as image:depth=np.array(image)
    with Image.open(support_path) as image:support=np.array(image)
    result=lift_skeleton(graph,depth,calibration,support,infer_hidden_depth=infer_hidden_depth)
    output.mkdir(parents=True)
    (output/'graph3d.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    with (output/'points.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['id','u','v','status_3d','X_m','Y_m','Z_m','reason'])
        for n in result['nodes']:writer.writerow([n['id'],n['x'],n['y'],n['status_3d'],*(n['xyz_m'] or ['','','']),n['reason_3d']])
    return result['status_counts']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('graph','depth','calibration','support','output'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--infer-hidden-depth',action='store_true')
    a=parser.parse_args();print(run(a.graph,a.depth,a.calibration,a.support,a.output,a.infer_hidden_depth))
