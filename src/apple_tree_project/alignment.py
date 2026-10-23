"""Explicit, unverified RGB-to-annotation coordinate hypotheses.

Coordinates use pixel-edge units; a pixel centre is (column + .5, row + .5).
No transform here is a calibrated or dataset-confirmed registration.
"""
from __future__ import annotations
import numpy as np
from PIL import Image

CANDIDATES = ('stretch', 'center_crop', 'letterbox')


def geometry(size, method, target=256):
    """Return (sx, sy, tx, ty) for target = scale * source + offset."""
    w, h = size
    if min(w, h, target) <= 0 or method not in CANDIDATES:
        raise ValueError('Invalid dimensions or candidate')
    if method == 'stretch':
        return target / w, target / h, 0., 0.
    scale = target / (min(w, h) if method == 'center_crop' else max(w, h))
    return scale, scale, (target - scale*w)/2, (target-scale*h)/2


def transform_rgb(image, method, target=256):
    """Resample RGB onto annotation grid with bilinear interpolation and black fill."""
    sx, sy, tx, ty = geometry(image.size, method, target)
    return image.convert('RGB').transform((target, target), Image.Transform.AFFINE,
        (1/sx, 0, -tx/sx, 0, 1/sy, -ty/sy), Image.Resampling.BILINEAR)


def mask_to_rgb(mask, size, method):
    """Map a square binary annotation to RGB coordinates using nearest neighbour."""
    a = np.asarray(mask)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or not np.isin(a, [0, 255]).all():
        raise ValueError('Expected square binary 0/255 annotation')
    sx, sy, tx, ty = geometry(size, method, a.shape[0])
    return Image.fromarray(a.astype(np.uint8)).transform(size, Image.Transform.AFFINE,
        (sx, 0, tx, 0, sy, ty), Image.Resampling.NEAREST)


def boundary(mask):
    """Four-neighbour inner boundary, with outside-image pixels treated as background."""
    a = np.asarray(mask) > 0
    p = np.pad(a, 1)
    interior = p[:-2,1:-1] & p[2:,1:-1] & p[1:-1,:-2] & p[1:-1,2:]
    return a & ~interior


def edge_proxy(image, mask):
    """Mean luminance gradient within 2 pixels of GT boundary; NOT accuracy."""
    gray = np.asarray(image.convert('L'), dtype=float) / 255
    gy, gx = np.gradient(gray)
    grad = np.hypot(gx, gy)
    edge = boundary(mask)
    p = np.pad(grad, 2)
    nearby = np.maximum.reduce([p[y:y+gray.shape[0], x:x+gray.shape[1]]
                               for y in range(5) for x in range(5)])
    return float(nearby[edge].mean()) if edge.any() else None


def overlay(image, mask):
    """Translucent magenta foreground with yellow inner outline."""
    rgb = np.array(image.convert('RGB'))
    a = np.asarray(mask) > 0
    rgb[a] = (.65*rgb[a] + .35*np.array([255,0,255])).astype(np.uint8)
    rgb[boundary(mask)] = [255,255,0]
    return Image.fromarray(rgb)
