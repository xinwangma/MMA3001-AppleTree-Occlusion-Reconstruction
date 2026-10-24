"""Compare Step 4 methods on explicit Step 3 skeleton gap requests."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image
from apple_tree_project.completion import complete_gaps


def run(skeleton_path, occlusion_path, gaps_path, output):
    skeleton_path,occlusion_path,gaps_path,output=map(Path,(skeleton_path,occlusion_path,gaps_path,output))
    root=Path(__file__).resolve().parents[1]
    resolved=output.resolve()
    if not any(resolved.is_relative_to(root/p) for p in ('results','data/processed')):
        raise ValueError('Output must be below results or data/processed')
    if output.exists():
        raise ValueError('Use a new output directory to preserve prior runs')
    with Image.open(skeleton_path) as image:skeleton=np.array(image)
    with Image.open(occlusion_path) as image:occlusion=np.array(image)
    gaps=json.loads(gaps_path.read_text(encoding='utf-8'))['gaps']
    results={}
    for method in ('linear','quadratic'):
        start=time.perf_counter()
        result=complete_gaps(skeleton,gaps,occlusion,method)
        result['runtime_seconds']=time.perf_counter()-start
        results[method]=result
    output.mkdir(parents=True)
    summary={}
    for method,result in results.items():
        directory=output/method;directory.mkdir()
        for key in ('skeleton','inferred_mask'):
            Image.fromarray(result.pop(key).astype(np.uint8)*255).save(directory/(key+'.png'))
        (directory/'completion.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        summary[method]=dict(accepted=len(result['accepted']),rejected=len(result['rejected']),
                             runtime_seconds=result['runtime_seconds'])
    summary['scope']='Geometric hypotheses only; no real-data reconstruction accuracy evaluated'
    (output/'comparison.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skeleton',required=True)
    parser.add_argument('--occlusion-mask',required=True)
    parser.add_argument('--gaps',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.skeleton,args.occlusion_mask,args.gaps,args.output),indent=2))
