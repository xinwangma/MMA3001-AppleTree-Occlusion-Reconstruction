"""RGB-only polygon annotations; provenance does not certify independent review."""
from __future__ import annotations
import hashlib
import numpy as np
from PIL import Image, ImageDraw

POLICY = 'visible-main-wood-v1'


def rasterize(annotation, size):
    """Rasterize integer pixel-centre polygons with Pillow's inclusive fill.

    All geometry is recorded explicitly; no morphology or GT alignment is used.
    """
    w,h = size
    if annotation.get('policy') != POLICY or annotation.get('image_size') != [w,h]:
        raise ValueError('Annotation policy or native size mismatch')
    if annotation.get('provenance') not in ('human_rgb_only','ai_rgb_only_draft','human_rgb_revision'):
        raise ValueError('Explicit RGB-only provenance required')
    if not annotation.get('annotator') or not annotation.get('notes'):
        raise ValueError('Annotator identity and limitations required')
    if annotation.get('review_status') not in ('pending','accepted','rejected'):
        raise ValueError('Explicit review status required')
    if annotation['review_status']=='accepted' and not annotation.get('reviewer'):
        raise ValueError('Accepted annotations require a reviewer identity')
    polygons=annotation.get('polygons',[])
    if not polygons:
        raise ValueError('No polygons; unlabelled input must not become an empty mask')
    mask=Image.new('L',size)
    draw=ImageDraw.Draw(mask)
    ids=set()
    for polygon in polygons:
        points=polygon['points']
        if not polygon.get('id') or polygon['id'] in ids:
            raise ValueError('Polygon IDs must be nonempty and unique')
        ids.add(polygon['id'])
        if len(points)<3:
            raise ValueError('A polygon needs at least three vertices')
        if any(len(p)!=2 or any(type(v) is not int for v in p) or not (0<=p[0]<w and 0<=p[1]<h) for p in points):
            raise ValueError('Vertices must be native-grid integer coordinates inside the image')
        area=sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))
        if area==0:
            raise ValueError('Degenerate polygon')
        draw.polygon([tuple(p) for p in points],fill=255)
    return np.array(mask)


def verify_source(annotation, rgb_path):
    """Bind annotation coordinates to exact RGB bytes; no filename-only pairing."""
    if hashlib.sha256(rgb_path.read_bytes()).hexdigest()!=annotation.get('rgb_sha256'):
        raise ValueError('RGB hash mismatch')
