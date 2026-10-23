"""Explicit RGB visual draft additions, checkpoint audit and before/after report.

Coordinates were selected by AI inspection of the 12 RGBs, without GT/depth.
They are conservative examples, NOT a complete annotation or human review.
The original bundle and draft_run are preserved. No interpolation across gaps.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import html
import json
import sys
from datetime import datetime,timezone
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from apple_tree_project.visible_annotation import quality_checks,rasterize,verify_source
from apple_tree_project.baseline import visible_only_baseline
from validate_visible_baseline import run
ROOT=Path(__file__).resolve().parents[1]

# Separate polygons deliberately preserve unlabelled gaps. No line/branch fitter.
# Each tuple: role, native polygon, visually required point, observation.
EDITS={
 'R01N02':('trunk',[[288,443],[298,443],[300,451],[291,454]],[295,451],
            'Short exposed lower-trunk surface below old y=447 boundary. The apparent continuation into ground vegetation is NOT annotated.'),
 'R02N02':('major_branch',[[227,350],[231,350],[240,361],[237,363],[230,357],[227,354]],[230,355],
            'Visible lower edge of left arm omitted by the narrow old polygon. The leaf across its upper part is excluded.'),
 'R03N02':('trunk',[],None,
            'No defensible addition in this pass: lower trunk, support and vegetation overlap. Original draft retained; sparse coverage remains unresolved.'),
 'R04N02':('major_branch',[[397,370],[402,356],[403,342],[406,329],[412,315],[417,308],[421,305],[420,313],[415,325],[412,340],[410,354],[408,366],[403,376]],[415,318],
            'Exposed right-arm segment extends upward beyond old y=329 boundary; foliage at upper end excluded.'),
 'R05N02':('major_branch',[[163,124],[169,123],[181,148],[192,173],[188,177],[176,153]],[181,153],
            'Exposed upper left-arm wood absent from old lower-trunk patches. Leaf-covered intermediate sections remain gaps.'),
 'R06N02':('major_branch',[[369,289],[373,287],[370,294],[364,301],[360,304],[358,302],[364,295]],[366,296],
            'Short exposed right-arm piece above the earlier patch; foliage between y=307 and y=313 is left out. Existing graft spur requires review.'),
 'R07N02':('major_branch',[[210,309],[216,312],[225,320],[229,324],[225,327],[217,320],[211,315]],[221,319],
            'Exposed left-arm segment only; stop before the apple at y=330. Dense leaf/fruit interruptions are not connected.'),
 'R08N02':('major_branch',[[281,354],[285,353],[295,363],[302,371],[303,376],[298,373],[289,363]],[294,365],
            'Left visible major arm was absent from the old right-arm/trunk-only polygons. Leaves at both ends remain excluded.'),
 'R09N02':('major_branch',[[374,348],[378,333],[383,317],[382,300],[380,289],[380,280],[384,280],[387,295],[393,301],[390,323],[385,340],[380,352]],[382,285],
            'Exposed right-arm surface above old boundary. Stop below the horizontal wire at y=276; do not annotate the wire.'),
 'R10N02':('major_branch',[[260,281],[265,281],[270,291],[266,296],[262,289]],[265,288],
            'Short visible left arm above the original patch. Apple/leaf occlusions above are excluded.'),
 'R11N02':('major_branch',[[245,357],[249,357],[252,363],[254,368],[250,369],[247,363]],[249,361],
            'Exposed left-arm segment missing from the original trunk/right-arm patches; foliage toward crotch remains unlabelled.'),
 'R12N02':('trunk',[],None,
            'No defensible addition in this pass: apparent lower-trunk continuation is interrupted by vegetation. Do not trace a guessed trunk through it; human review required.'),
}

OBSERVATIONS_ZH={
 'R01N02':'补充原标注下沿附近的短段可见树干；不沿疑似延续描到草丛。',
 'R02N02':'补充左主枝窄多边形遗漏的可见下侧表面；上方覆盖叶片保持未标注。',
 'R03N02':'本轮不新增：下部树干、支撑物与植被重叠，无法可靠分辨；原有稀疏覆盖仍需人工修订。',
 'R04N02':'重新记录右主枝上部完整多边形边界，避免窄条与旧多边形叠加产生微小孔洞。',
 'R05N02':'补充左上裸露木质段，与下部之间的叶片覆盖处保持断开。',
 'R06N02':'重点复核：补充右侧短裸露枝段；原嫁接区域的额外短刺与 1 个交汇像素仍保留，不能认定为真实分叉。',
 'R07N02':'补充左主枝裸露段，在果实上缘前停止；不穿过果实描枝。',
 'R08N02':'补充旧标注完全遗漏的左主枝裸露中段；上方叶片覆盖部分保持空白。',
 'R09N02':'重新记录右主枝上部木质边界，在横向线材下方停止，不将线材视为枝条。',
 'R10N02':'补充左主枝短裸露段；保留附近叶片／果实间隙，邻近端点仅提示复核。',
 'R11N02':'补充左侧小段裸露木质；触发小分量候选，不自动删除真实可见片段。',
 'R12N02':'本轮不新增：下部疑似树干延续被植被遮挡，不猜测连续路径；保留原掩膜待人工检查。',
}


def build(output,repeats=3):
    output=output.resolve()
    if (ROOT/'results').resolve() not in output.parents:raise ValueError('Output must be below results/')
    if output.exists():raise ValueError('Use a new revision output directory')
    original=ROOT/'data/annotations/step3_rgb_only_drafts.json'
    bundle=json.loads(original.read_text(encoding='utf-8'))
    revisions=[];audit=[]
    for old in bundle['samples']:
        a=copy.deepcopy(old);sid=a['sample_id'];role,points,point,note=EDITS[sid]
        parent=ROOT/'results/step3_real_validation/draft_run'/sid/'annotation.json'
        source=ROOT/a['rgb_path'];verify_source(a,source)
        a.update(parent_annotation_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),
                 parent_provenance=old['provenance'],revision='rgb_visual_coverage_v4',
                 revised_utc=datetime.now(timezone.utc).isoformat(),review_status='pending',reviewer='',
                 annotator='Codex RGB visual draft revision; NOT human reviewed',
                 notes=old['notes']+' Revision: '+note+' Coverage remains partial; no hidden completion.')
        if points:
            if sid in ('R04N02','R09N02'):
                # Replace the right-arm polygon explicitly; overlapping narrow
                # additions produced tiny raster holes/spurs in preflight.
                # This is a recorded RGB-supported polygon edit, not hole filling.
                a['polygons'][2]=dict(id='visible_patch_3',role=role,points=points)
            else:a['polygons'].append(dict(id='rgb_revision_visible_piece',role=role,points=points))
        a['checkpoints']=([dict(id='omitted_visible_main_wood',point=point,kind='visible_required',role=role,note=note,
                               provenance='AI RGB visual checkpoint; requires human confirmation')] if point else [])
        # Occluded checkpoints must be placed by a reviewer at a specific RGB
        # pixel; this batch does not invent universal occlusion/background truth.
        before_mask=rasterize(old,tuple(a['image_size']))
        after_mask=rasterize(a,tuple(a['image_size']))
        before_graph=json.loads((parent.parent/'graph.json').read_text())
        before_qa=quality_checks(before_mask,before_graph,a['checkpoints'])
        after_result=visible_only_baseline(after_mask)
        after_qa=quality_checks(after_mask,after_result['graph'],a['checkpoints'])
        audit.append(dict(sample_id=sid,observation=note,before_quality=before_qa,after_quality=after_qa,
                          added_mask_pixels=int(((after_mask>0)&(before_mask==0)).sum()),
                          removed_mask_pixels=int(((before_mask>0)&(after_mask==0)).sum())))
        revisions.append(a)
    output.mkdir(parents=True)
    revised_bundle=output/'annotations.json'
    revised_bundle.write_text(json.dumps(dict(note='AI RGB-only draft coverage revision; human review pending; no accuracy claim',samples=revisions),indent=2),encoding='utf-8')
    summary=run(revised_bundle,output/'run',True,repeats)
    (output/'coverage_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    render_report(output,revisions,audit)
    print(json.dumps(summary,indent=2))
    print(output/'run/index.html')


def render_report(output,revisions,audit):
    rows=[]
    for a,item in zip(revisions,audit):
        sid=a['sample_id'];before=ROOT/'results/step3_real_validation/draft_run'/sid;after=output/'run'/sid
        # Preserve the actual existing panels and stack the two comparisons.
        with Image.open(before/'comparison.png') as im:b=im.copy()
        with Image.open(after/'comparison.png') as im:c=im.copy()
        figure=Image.new('RGB',(1280,2*(b.height+30)),(245,248,250));draw=ImageDraw.Draw(figure)
        draw.text((10,8),f'{sid} BEFORE - DRAFT original',fill='black');figure.paste(b,(0,30))
        draw.text((10,b.height+38),f'{sid} AFTER - DRAFT revision; NOT human reviewed',fill='black');figure.paste(c,(0,b.height+60))
        figure.save(after/'before_after.png')
        bd=json.loads((before/'diagnostics.json').read_text());ad=json.loads((after/'diagnostics.json').read_text())
        bqa=item['before_quality'];aqa=item['after_quality']
        short=sum(p['short_spur_candidate'] for p in aqa['terminal_paths'])
        highlight=' style="border:2px solid #cf8c29"' if sid=='R06N02' else ''
        rows.append(f'''<article id="{sid}"{highlight}><h2>{sid} <span>DRAFT · 待人工审核</span></h2>
<p>{html.escape(OBSERVATIONS_ZH[sid])}</p><p>新增掩膜像素：{item['added_mask_pixels']}；移除：{item['removed_mask_pixels']}；骨架像素 {bd['skeleton_pixels']} → {ad['skeleton_pixels']}；连通分量 {bd['skeleton_components']} → {ad['skeleton_components']}；端点 {bd['endpoints']} → {ad['endpoints']}；交汇像素 {bd['junction_pixels']} → {ad['junction_pixels']}。</p>
<p>显式可见点漏标提示 {len(bqa['failed_checkpoints'])} → {len(aqa['failed_checkpoints'])}；小分量候选 {len(aqa['small_component_candidates'])}；短刺候选 {short}；邻近但断开的端点对 {len(aqa['near_disconnected_endpoints'])}；环秩 {ad['cycle_rank']}；孤立像素 {ad['isolated_pixels']}。所有候选仅供复核，不自动删除或连线。</p>
<div class="pair"><figure><figcaption>修订前 · DRAFT</figcaption><a href="../../draft_run/{sid}/comparison.png"><img loading="lazy" src="../../draft_run/{sid}/comparison.png" alt="{sid} 修订前四联图"></a></figure><figure><figcaption>修订后 · DRAFT</figcaption><a href="{sid}/comparison.png"><img loading="lazy" src="{sid}/comparison.png" alt="{sid} 修订后四联图"></a></figure></div>
<p><a href="{sid}/before_after.png">完整前后对比图</a> · <a href="{sid}/visible.png">修订掩膜</a> · <a href="{sid}/skeleton.png">修订骨架</a> · <a href="{sid}/graph.json">像素图</a> · <a href="{sid}/quality_checks.json">质量检查</a> · <a href="{sid}/annotation.json">标注</a></p></article>''')
    nav=' '.join(f'<a href="#{a["sample_id"]}">{a["sample_id"]}</a>' for a in revisions)
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Step 3 · 可见枝条草稿修订对比</title><style>body{{font:15px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f1f5f8;color:#193246;margin:0}}main{{max-width:1500px;margin:auto;padding:24px}}article,header{{background:white;border:1px solid #d4e0e7;border-radius:12px;padding:24px;margin-bottom:24px}}h1{{font-size:30px}}h2 span{{font-size:12px;background:#fff0ce;color:#86500a;padding:5px 10px;border-radius:5px}}a{{color:#086c76}}nav{{position:sticky;top:0;background:#edf5f6;padding:12px;display:flex;gap:14px;overflow:auto}}article{{scroll-margin-top:65px}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}figure{{margin:0}}figcaption{{font-weight:700;padding:8px}}img{{width:100%;height:auto}}.notice{{background:#fff5dd;padding:16px;border-left:4px solid #cb8b27}}@media(max-width:850px){{.pair{{grid-template-columns:1fr}}main{{padding:10px}}}}</style><main><header><h1>Step 3 · 可见枝条草稿修订前后对比</h1><p class="notice">全部 12 个样本仍为 AI RGB-only DRAFT，人工已复核 0、已批准 0。10 个样本新增可见小段；R03N02 / R12N02 因歧义保留原掩膜。增加的区域不是完整可见真值，也没有证明真实重建精度提高。不自动跨遮挡连接。</p><p>每幅四联图：左上原始 RGB，右上青色草稿叠加，左下黄色骨架，右下连通分量着色的图结构（红圈端点，白圈交汇／孤立像素）。点击图片查看原尺寸。</p><p>可见检查点来自 AI 目视选择，修订直接围绕它们进行；通过仅说明这些点被覆盖，不是独立验证。R03N02 / R12N02 没有可见检查点，0 条提示不能解释为无漏标。当前未提供经人工确认的遮挡检查点；遮挡检查能力不能解释为本批已验证所有遮挡。</p><p>阈值：小分量 ≤12 骨架像素；连接到交汇的短端路径 ≤8 px；跨分量邻近端点 ≤12 px。多分量可能是真实遮挡，更多像素或更少分量均不等于更好。</p><p>所有原始草稿与原图保持不变。R06N02 的原有嫁接区域短刺未擅自删改，仍待人工确认。<a href="../../index.html">原始图库</a> · <a href="../coverage_audit.json">覆盖审计 JSON</a> · <a href="summary.json">修订运行汇总</a></p></header><nav>{nav}</nav>{''.join(rows)}</main></html>'''
    (output/'run/index.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'results/step3_real_validation/coverage_revision_v4')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--report-only',action='store_true',help='Refresh QA and HTML from saved masks/graphs; no thinning rerun')
    a=p.parse_args()
    if a.report_only:
        output=a.output.resolve()
        if (ROOT/'results').resolve() not in output.parents:raise ValueError('Output must be below results/')
        revisions=json.loads((output/'annotations.json').read_text())['samples']
        audit=json.loads((output/'coverage_audit.json').read_text())
        for annotation,item in zip(revisions,audit):
            if annotation['sample_id']!=item['sample_id']:raise ValueError('Audit order mismatch')
            for phase,directory in [('before',ROOT/'results/step3_real_validation/draft_run'/annotation['sample_id']),('after',output/'run'/annotation['sample_id'])]:
                with Image.open(directory/'visible.png') as image:mask=__import__('numpy').array(image)
                graph=json.loads((directory/'graph.json').read_text())
                qa=quality_checks(mask,graph,annotation.get('checkpoints',[]))
                item[phase+'_quality']=qa
                if phase=='after':(directory/'quality_checks.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
        (output/'coverage_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
        render_report(output,revisions,audit)
        print(output/'run/index.html')
    else:build(a.output,a.repeats)
