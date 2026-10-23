"""Zoomable RGB-only polygon editor. No GT/depth or automatic gap completion.

Draw separate polygons at occlusions. Zoom 1-6x; scrollbars/middle drag pan.
Select and drag vertices in Edit mode; right-click an edge to insert a vertex.
Enter completes polygon; Backspace undoes a drawing point; Delete removes the
selected polygon. Ctrl+Z/Y undo/redo; Ctrl+S saves DRAFT JSON and binary mask.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import copy
from datetime import datetime, timezone
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_tree_project.visible_annotation import POLICY, rasterize, verify_source, reset_review
ROOT=Path(__file__).resolve().parents[1]


def native_point(x,y,zoom,size):
    """Map scrolled, zoomed canvas coordinates to native integer pixel centres."""
    if zoom<=0:raise ValueError('Zoom must be positive')
    if x<0 or y<0:return None
    point=[int(x/zoom+.5),int(y/zoom+.5)]
    return point if 0<=point[0]<size[0] and 0<=point[1]<size[1] else None


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
    from tkinter import ttk
    from PIL import ImageTk
    with Image.open(a.rgb) as im:
        if im.mode!='RGB':
            p.error('Only RGB source images are accepted; no implicit label conversion')
        rgb=im.copy()
    annotation=dict(policy=POLICY,image_size=list(rgb.size),rgb_path=str(a.rgb.resolve()),
        rgb_sha256=hashlib.sha256(a.rgb.read_bytes()).hexdigest(),annotator=a.annotator,
        provenance='human_rgb_only',review_status='pending',reviewer='',notes=a.notes,
        sample_id=a.rgb.stem.split('_Summer_RGB')[0],
        created_utc=datetime.now(timezone.utc).isoformat(),polygons=[],checkpoints=[])
    if a.load:
        previous=json.loads(a.load.read_text(encoding='utf-8-sig'))
        verify_source(previous,a.rgb)
        rasterize(previous,rgb.size)
        annotation['polygons']=previous['polygons']
        annotation['checkpoints']=previous.get('checkpoints',[])
        annotation['provenance']='human_rgb_revision'
        annotation['parent_provenance']=previous['provenance']
        annotation['parent_annotation_sha256']=hashlib.sha256(a.load.read_bytes()).hexdigest()
    window=tk.Tk(); window.title('Visible wood ONLY | DRAFT / pending | Ctrl+S save');window.geometry('1150x820')
    zoom=tk.DoubleVar(value=1);overlay=tk.BooleanVar(value=True);mode=tk.StringVar(value='Draw')
    role=tk.StringVar(value='major_branch');history=[];future=[];drag=None;saved=False;dirty=False
    bar=ttk.Frame(window);bar.pack(fill='x',padx=8,pady=6)
    ttk.Label(bar,text='Mode').pack(side='left')
    ttk.Combobox(bar,textvariable=mode,values=['Draw','Edit','Visible checkpoint','Occluded checkpoint'],state='readonly',width=20).pack(side='left')
    ttk.Label(bar,text=' Role').pack(side='left')
    ttk.Combobox(bar,textvariable=role,values=['trunk','major_branch','uncertain_fragment'],state='readonly',width=18).pack(side='left')
    ttk.Label(bar,text=' Zoom').pack(side='left')
    zoom_menu=ttk.Combobox(bar,textvariable=zoom,values=[1,1.5,2,3,4,6],state='readonly',width=5);zoom_menu.pack(side='left')
    ttk.Checkbutton(bar,text='Mask overlay',variable=overlay,command=lambda:redraw()).pack(side='left')
    ttk.Label(window,text='Draw: click, Enter finish. Edit: select polygon, drag vertex; right-click edge to insert. Middle drag / scrollbars pan.\nBackspace: undo current vertex. Ctrl+Z/Y: history. Separate polygons at occlusions; never infer hidden continuation.').pack(anchor='w',padx=8)
    photo=ImageTk.PhotoImage(rgb)
    body=ttk.Frame(window);body.pack(fill='both',expand=True)
    side=ttk.Frame(body);side.pack(side='right',fill='y',padx=6)
    ttk.Label(side,text='Select polygon to edit').pack()
    listing=tk.Listbox(side,exportselection=False,width=26);listing.pack(fill='both',expand=True)
    frame=ttk.Frame(body);frame.pack(fill='both',expand=True)
    canvas=tk.Canvas(frame,width=rgb.width,height=rgb.height,background='#173047')
    xs=ttk.Scrollbar(frame,orient='horizontal',command=canvas.xview);ys=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview)
    canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
    canvas.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew')
    frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1);points=[]
    ttk.Label(window,text='Coverage / ambiguity notes (required)').pack(anchor='w')
    notes=tk.Text(window,height=3);notes.insert('1.0',a.notes);notes.pack(fill='x')
    status=tk.Label(window,text='Native pixel coordinates. Pending review; no hidden continuation.'); status.pack()
    def selected():return listing.curselection()[0] if listing.curselection() else None
    def remember():
        nonlocal dirty
        history.append(copy.deepcopy(annotation));future.clear();reset_review(annotation);dirty=True
    def redraw(*_):
        nonlocal photo
        chosen=selected();z=zoom.get();image=rgb.convert('RGBA')
        if overlay.get() and annotation['polygons']:
            mask=rasterize(annotation,rgb.size)
            layer=Image.new('RGBA',rgb.size,(0,230,240,0));layer.putalpha(Image.fromarray((mask>0).astype('uint8')*90))
            image=Image.alpha_composite(image,layer)
        image=image.resize((round(rgb.width*z),round(rgb.height*z)),Image.Resampling.NEAREST)
        photo=ImageTk.PhotoImage(image);canvas.configure(scrollregion=(0,0,image.width,image.height))
        canvas.delete('all'); canvas.create_image(0,0,anchor='nw',image=photo)
        listing.delete(0,'end')
        for i,poly in enumerate(annotation['polygons']):
            listing.insert('end',f"{poly['id']} [{poly.get('role','unspecified')}]")
            canvas.create_polygon(*[v*z for point in poly['points'] for v in point],outline='yellow' if i==chosen else 'cyan',fill='',width=2)
            if i==chosen:
                listing.selection_set(i)
                for x,y in poly['points']:canvas.create_rectangle(x*z-4,y*z-4,x*z+4,y*z+4,fill='yellow')
        if len(points)>1: canvas.create_line(*[v*z for point in points for v in point],fill='yellow',width=2)
        for x,y in points: canvas.create_oval(x*z-2,y*z-2,x*z+2,y*z+2,fill='yellow')
        for c in annotation['checkpoints']:
            x,y=c['point'];color='red' if c['kind']=='occluded_excluded' else '#80ff50'
            canvas.create_line(x*z-5,y*z,x*z+5,y*z,fill=color,width=2);canvas.create_line(x*z,y*z-5,x*z,y*z+5,fill=color,width=2)
        status.config(text=f"DRAFT / pending | {len(annotation['polygons'])} polygons; {len(points)} current vertices; {len(annotation['checkpoints'])} checkpoints")
    def event_point(event):return native_point(canvas.canvasx(event.x),canvas.canvasy(event.y),zoom.get(),rgb.size)
    def click(event):
        nonlocal drag
        point=event_point(event)
        if point is None:return
        if mode.get()=='Draw':points.append(point);redraw()
        elif mode.get()=='Edit':
            i=selected()
            if i is None:return
            distance,j=min(((x-point[0])**2+(y-point[1])**2,j) for j,(x,y) in enumerate(annotation['polygons'][i]['points']))
            if distance<=(9/zoom.get())**2:remember();drag=(i,j)
        else:
            remember();annotation['checkpoints'].append(dict(id=f'check_{len(annotation["checkpoints"])+1}',point=point,
                kind='visible_required' if mode.get()=='Visible checkpoint' else 'occluded_excluded',role=role.get(),note='Human RGB point check only'));redraw()
    def move(event):
        if drag is None:return
        point=event_point(event)
        if point is None:return
        i,j=drag;old=annotation['polygons'][i]['points'][j];annotation['polygons'][i]['points'][j]=point
        try:rasterize(annotation,rgb.size)
        except ValueError:annotation['polygons'][i]['points'][j]=old
        redraw()
    def release(event):
        nonlocal drag
        drag=None
    def insert(event):
        if mode.get()!='Edit':return
        i=selected();point=event_point(event)
        if i is None or point is None:return
        vertices=annotation['polygons'][i]['points']
        def distance(j):
            x,y=vertices[j];u,v=vertices[(j+1)%len(vertices)];dx,dy=u-x,v-y
            t=max(0,min(1,((point[0]-x)*dx+(point[1]-y)*dy)/(dx*dx+dy*dy or 1)))
            return (point[0]-x-t*dx)**2+(point[1]-y-t*dy)**2
        j=min(range(len(vertices)),key=distance)
        if distance(j)<=(10/zoom.get())**2:
            remember();vertices.insert(j+1,point)
            try:rasterize(annotation,rgb.size)
            except ValueError:vertices.pop(j+1)
            redraw()
    def finish(event):
        if len(points)>=3:
            used={p['id'] for p in annotation['polygons']};index=1
            while f'fragment_{index}' in used:index+=1
            remember();annotation['polygons'].append(dict(id=f'fragment_{index}',role=role.get(),points=points.copy()))
            try: rasterize(annotation,rgb.size)
            except ValueError as exc:
                annotation['polygons'].pop(); messagebox.showerror('Invalid polygon',str(exc)); return
            points.clear(); redraw()
    def undo(event):
        if points: points.pop()
        redraw()
    def remove(event):
        i=selected()
        if i is not None:remember();annotation['polygons'].pop(i)
        redraw()
    def history_move(redo=False):
        nonlocal dirty
        source,dest=(future,history) if redo else (history,future)
        if not source:return
        dest.append(copy.deepcopy(annotation));previous=source.pop();annotation.clear();annotation.update(previous)
        reset_review(annotation);points.clear();dirty=True;redraw()
    def remove_checkpoint():
        if annotation['checkpoints']:remember();annotation['checkpoints'].pop();redraw()
    def save(event):
        nonlocal saved,dirty
        if points:
            messagebox.showerror('Unfinished polygon','Press Enter to complete or undo current vertices.'); return
        try:
            annotation['notes']=notes.get('1.0','end').strip();reset_review(annotation)
            verify_source(annotation,a.rgb)
            mask=rasterize(annotation,rgb.size)
            if not saved:out.mkdir(parents=True,exist_ok=False)
            (out/'annotation.json').write_text(json.dumps(annotation,indent=2),encoding='utf-8')
            Image.fromarray(mask).save(out/'visible.png')
            saved=True;dirty=False
            status.config(text=f'Saved draft to {out}; independent review still required')
        except (ValueError,OSError) as exc: messagebox.showerror('Save failed',str(exc))
    canvas.bind('<Button-1>',click)
    canvas.bind('<B1-Motion>',move);canvas.bind('<ButtonRelease-1>',release);canvas.bind('<Button-3>',insert)
    canvas.bind('<Button-2>',lambda e:canvas.scan_mark(e.x,e.y));canvas.bind('<B2-Motion>',lambda e:canvas.scan_dragto(e.x,e.y,gain=1))
    listing.bind('<<ListboxSelect>>',redraw);zoom_menu.bind('<<ComboboxSelected>>',redraw)
    window.bind('<Return>',lambda e:finish(e) if e.widget is not notes else None)
    window.bind('<BackSpace>',lambda e:undo(e) if e.widget is not notes else None)
    window.bind('<Delete>',lambda e:remove(e) if e.widget is not notes else None)
    window.bind('<Control-s>',save)
    window.bind('<Control-z>',lambda e:history_move() if e.widget is not notes else None)
    window.bind('<Control-y>',lambda e:history_move(True) if e.widget is not notes else None)
    for label,command in [('Finish polygon',lambda:finish(None)),('Delete selected',lambda:remove(None)),('Undo',lambda:history_move()),('Redo',lambda:history_move(True)),('Undo checkpoint',remove_checkpoint),('Save DRAFT',lambda:save(None))]:
        ttk.Button(side,text=label,command=command).pack(fill='x',pady=2)
    def close():
        if dirty or points or notes.get('1.0','end').strip()!=annotation['notes']:
            if not messagebox.askyesno('Unsaved work','Close without saving changes?'):return
        window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    redraw(); window.mainloop()

if __name__=='__main__': main()
