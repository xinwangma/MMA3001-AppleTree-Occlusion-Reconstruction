"""Record explicit human review/approval into a NEW annotation file.

Metadata is a user declaration, not proof of independence or anatomical quality.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_tree_project.visible_annotation import rasterize,verify_source
ROOT=Path(__file__).resolve().parents[1]


def transition(annotation,status,person,notes):
    import copy
    result=copy.deepcopy(annotation)
    if not person.strip() or not notes.strip():raise ValueError('Identity and review notes required')
    person=person.strip();notes=notes.strip()
    if status=='reviewed':
        if result['provenance']=='ai_rgb_only_draft':
            result.update(parent_provenance=result['provenance'],provenance='human_rgb_revision')
        result.update(review_status='reviewed',reviewer=person,review_notes=notes,
                      reviewed_utc=datetime.now(timezone.utc).isoformat())
        result.pop('approved_by',None);result.pop('approved_utc',None);result.pop('approval_notes',None)
    elif status=='accepted':
        if result['review_status']!='reviewed':raise ValueError('Approval requires an explicitly reviewed annotation first')
        if person==result['reviewer']:raise ValueError('Use a separate approving person')
        result.update(review_status='accepted',approved_by=person,approval_notes=notes,
                      approved_utc=datetime.now(timezone.utc).isoformat())
    elif status=='rejected':result.update(review_status='rejected',rejection_by=person,rejection_notes=notes)
    else:raise ValueError('Unknown transition')
    rasterize(result,tuple(result['image_size']))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--annotation',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--status',choices=['reviewed','accepted','rejected'],required=True)
    p.add_argument('--person',required=True);p.add_argument('--notes',required=True)
    a=p.parse_args();out=a.output.resolve()
    if not any(r.resolve() in out.parents for r in (ROOT/'results',ROOT/'data/processed')):p.error('Output must be below results/ or data/processed/')
    annotation=json.loads(a.annotation.read_text(encoding='utf-8-sig'))
    verify_source(annotation,ROOT/annotation['rgb_path'])
    result=transition(annotation,a.status,a.person,a.notes)
    result['parent_annotation_sha256']=hashlib.sha256(a.annotation.read_bytes()).hexdigest()
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(out)


if __name__=='__main__':main()
