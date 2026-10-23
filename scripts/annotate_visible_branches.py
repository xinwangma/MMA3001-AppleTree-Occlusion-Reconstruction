"""Native-grid RGB polygon editor. No GT/depth loading or automatic segmentation.

Left click adds a vertex; Enter completes polygon; Backspace undoes a vertex;
Delete removes the last completed polygon; S saves JSON + binary mask.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_tree_project.visible_annotation import POLICY, rasterize, verify_source
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rgb',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True,help='New directory under results/ or data/processed/')
    p.add_argument('--annotator',required=True)
    p.add_argument('--notes',required=True,help='Coverage and ambiguity notes; do not guess hidden wood')
    p.add_argument('--load',type=Path,help='Load existing JSON for a new independently saved revision')
    a=p.parse_args()
    out=a.output.resolve()
    if not any(root.resolve() in out.parents for root in (ROOT/'results',ROOT/'data/processed')):
        p.error('Output must be below results/ or data/processed/')
    if out.exists() or out in a.rgb.resolve().parents:
        p.error('Use a new output directory, separate from source inputs')
    # GUI imports are delayed so --help works without a display.
    import tkinter as tk
    from tkinter import messagebox
    from PIL import ImageTk
    with Image.open(a.rgb) as im:
        if im.mode!='RGB':
            p.error('Only RGB source images are accepted; no implicit label conversion')
        rgb=im.copy()
    annotation=dict(policy=POLICY,image_size=list(rgb.size),rgb_path=str(a.rgb.resolve()),
        rgb_sha256=hashlib.sha256(a.rgb.read_bytes()).hexdigest(),annotator=a.annotator,
        provenance='human_rgb_only',review_status='pending',reviewer='',notes=a.notes,
        created_utc=datetime.now(timezone.utc).isoformat(),polygons=[])
    if a.load:
        previous=json.loads(a.load.read_text(encoding='utf-8-sig'))
        verify_source(previous,a.rgb)
        rasterize(previous,rgb.size)
        annotation['polygons']=previous['polygons']
        annotation['provenance']='human_rgb_revision'
        annotation['parent_provenance']=previous['provenance']
        annotation['parent_annotation_sha256']=hashlib.sha256(a.load.read_bytes()).hexdigest()
    window=tk.Tk(); window.title('Visible wood ONLY | Enter polygon | Backspace undo | Delete polygon | S save')
    photo=ImageTk.PhotoImage(rgb)
    canvas=tk.Canvas(window,width=rgb.width,height=rgb.height)
    canvas.pack(); points=[]
    status=tk.Label(window,text='Native pixel coordinates. Pending review; no hidden continuation.'); status.pack()
    def redraw():
        canvas.delete('all'); canvas.create_image(0,0,anchor='nw',image=photo)
        for poly in annotation['polygons']:
            canvas.create_polygon(*[v for point in poly['points'] for v in point],outline='cyan',fill='',width=2)
        if len(points)>1: canvas.create_line(*[v for point in points for v in point],fill='yellow',width=2)
        for x,y in points: canvas.create_oval(x-2,y-2,x+2,y+2,fill='yellow')
        status.config(text=f"{len(annotation['polygons'])} polygons; {len(points)} current vertices; pending review")
    def click(event):
        if 0<=event.x<rgb.width and 0<=event.y<rgb.height:
            points.append([event.x,event.y]); redraw()
    def finish(event):
        if len(points)>=3:
            annotation['polygons'].append(dict(id=f'fragment_{len(annotation["polygons"])+1}',points=points.copy()))
            try: rasterize(annotation,rgb.size)
            except ValueError as exc:
                annotation['polygons'].pop(); messagebox.showerror('Invalid polygon',str(exc)); return
            points.clear(); redraw()
    def undo(event):
        if points: points.pop()
        redraw()
    def remove(event):
        if annotation['polygons']: annotation['polygons'].pop()
        redraw()
    def save(event):
        if points:
            messagebox.showerror('Unfinished polygon','Press Enter to complete or undo current vertices.'); return
        try:
            verify_source(annotation,a.rgb)
            mask=rasterize(annotation,rgb.size)
            out.mkdir(parents=True,exist_ok=True)
            (out/'annotation.json').write_text(json.dumps(annotation,indent=2),encoding='utf-8')
            Image.fromarray(mask).save(out/'visible.png')
            status.config(text=f'Saved draft to {out}; independent review still required')
        except (ValueError,OSError) as exc: messagebox.showerror('Save failed',str(exc))
    canvas.bind('<Button-1>',click)
    window.bind('<Return>',finish); window.bind('<BackSpace>',undo); window.bind('<Delete>',remove)
    window.bind('s',save); window.bind('S',save)
    redraw(); window.mainloop()

if __name__=='__main__': main()
