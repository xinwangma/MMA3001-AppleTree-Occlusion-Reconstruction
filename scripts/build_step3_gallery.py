"""Build an offline, read-only gallery from the existing Step 3 draft run.

No baseline processing or source-image modification is performed.
"""
from pathlib import Path
import html
import json
import os
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/step3_real_validation'
RUN = OUT / 'draft_run'


def esc(value):
    return html.escape(str(value), quote=True)


def url(path):
    return quote(Path(os.path.relpath(path, OUT)).as_posix(), safe='/')


def build():
    summary = json.loads((RUN / 'summary.json').read_text(encoding='utf-8'))
    notes = {
        'R06N02': '重点复核：宽大的下部树干／嫁接区域草稿产生额外短刺及 1 个度数为 3 的交汇像素；不能据此认定存在额外真实树枝。多边形拐角与膨大区域会影响中心线。',
        'R03N02': '遮挡与覆盖限制：叶片／果实遮挡较重，保守标注仅覆盖稀疏片段；不能据此确认完整 Y 形连接。',
        'R07N02': '遮挡与覆盖限制：叶片／果实遮挡较重，保守标注仅覆盖稀疏片段；不能据此确认完整 Y 形连接。',
        'R01N02': '标注间隙：分离的保守多边形可能产生人工间隙，也可能存在遮挡间隙；当前方法无法区分。',
        'R09N02': '标注间隙：分离的保守多边形可能产生人工间隙，也可能存在遮挡间隙；当前方法无法区分。',
        'R12N02': '标注间隙：分离的保守多边形可能产生人工间隙，也可能存在遮挡间隙；当前方法无法区分。',
    }
    cards, rows, nav = [], [], []
    for sample in summary['samples']:
        sid = sample['sample_id']
        directory = RUN / sid
        d = json.loads((directory / 'diagnostics.json').read_text(encoding='utf-8'))
        a = json.loads((directory / 'annotation.json').read_text(encoding='utf-8'))
        g = json.loads((directory / 'graph.json').read_text(encoding='utf-8'))
        assert d['skeleton_pixels'] == len(g['nodes'])
        assert d['skeleton_components'] == len(g['components'])
        rgb = ROOT / a['rgb_path']
        for path in [rgb, *(directory / f for f in ('comparison.png', 'visible.png', 'skeleton.png', 'graph.json'))]:
            if not path.is_file():
                raise FileNotFoundError(path)
        nav.append(f'<a href="#{sid}" class="{"flag" if sid in notes else ""}">{sid}</a>')
        metrics = [('骨架像素', d['skeleton_pixels']), ('连通分量（输入 → 骨架）', f'{d["input_components"]} → {d["skeleton_components"]}'), ('端点', d['endpoints']), ('交汇像素', d['junction_pixels']), ('像素图边数', len(g['edges'])), ('处理时间 · 中位数', f'{d["median_inference_seconds"]*1000:.1f} ms')]
        stats = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in metrics)
        panels = []
        # These are viewports onto the actual existing comparison PNG. The
        # original renderer uses 640x480 panels with 38px title strips.
        specs = [
            ('01', '原始 RGB', '原始数据 · 640 × 480', 'rgb'),
            ('02', '可见枝条标注叠加', 'DRAFT · 青色为 AI 多边形草稿', 'overlay'),
            ('03', '可见枝条二值掩膜', 'DRAFT · 白色为标注区域，黑色为未标注区域', 'mask'),
            ('04', '提取的 2D 骨架', 'DRAFT 输入派生 · 原始二值骨架', 'skeleton'),
            ('05', '骨架像素图', 'DRAFT 输入派生 · 分量颜色／红色端点／白色交汇', 'graph'),
        ]
        for number, title, caption, kind in specs:
            if kind in ('overlay', 'graph'):
                x, y = (640, 38) if kind == 'overlay' else (640, 556)
                visual = f'<svg viewBox="0 0 640 480" role="img" aria-label="{sid} {title}"><title>{sid} {title}</title><image href="{url(directory / "comparison.png")}" x="{-x}" y="{-y}" width="1280" height="1036"/></svg>'
            else:
                path = rgb if kind == 'rgb' else directory / ('visible.png' if kind == 'mask' else 'skeleton.png')
                visual = f'<img src="{url(path)}" alt="{sid} {title}" loading="lazy" width="640" height="480">'
            panels.append(f'<figure><figcaption><span>{number}</span> {title}<small>{caption}</small></figcaption><button type="button" class="visual" data-title="{sid} · {title}" aria-label="放大 {sid} {title}">{visual}</button></figure>')
        checks = []
        if not d['components_preserved_one_to_one']:
            checks.append('连通分量未一一保留')
        if d['skeleton_outside_input_pixels']:
            checks.append(f'骨架越界像素：{d["skeleton_outside_input_pixels"]}')
        if not d['unchanged_prediction']:
            checks.append('预测掩膜发生改变')
        if d['isolated_pixels'] or d['cycle_rank']:
            checks.append(f'孤立像素：{d["isolated_pixels"]}；环秩：{d["cycle_rank"]}')
        diagnostic = '；'.join(checks) if checks else '已记录的诊断检查未发现失败：分量一一保留、骨架越界 0、预测掩膜未改变、孤立像素 0、环秩 0。'
        warning = notes.get(sid, '未在现有复核报告中单独列出特定问题；仍需人工检查枝条身份、边界、覆盖与遮挡。')
        links = ' · '.join(f'<a href="{url(directory / filename)}">{label}</a>' for filename, label in [('comparison.png', '原始四联图'), ('annotation.json', '标注 JSON'), ('diagnostics.json', '诊断 JSON'), ('graph.json', '像素图 JSON')])
        times = ' / '.join(f'{v*1000:.1f}' for v in d['timing_seconds'])
        cards.append(f'''<article id="{sid}" class="sample {'priority' if sid == 'R06N02' else ''}">
<header class="sample-head"><h2>{sid}</h2><span class="badge">DRAFT · 待人工审核</span><a href="#overview">↑ 返回总览</a></header>
<dl class="metrics">{stats}</dl>
<p class="warning">{esc(warning)}</p>
<div class="panels">{''.join(panels)}</div>
<p class="legend">图例：青色叠加＝草稿区域；掩膜外为未标注，不能直接视为真实背景。像素图中同色节点与边属于同一连通分量（青／粉／黄）；红圈＝度数 1 的端点，白圈＝交汇或孤立像素。本次所有样本孤立像素均为 0。交汇像素数不等于解剖学分叉数。</p>
<details><summary>诊断、标注说明与原始文件</summary><p>{esc(diagnostic)}</p><p>可见掩膜像素：{d['visible_pixels']}；保留骨架的草稿片区：{d['patches_with_skeleton']} / {d['annotated_patches']}。片区存活不能解释为枝条召回率。</p><p>5 次计时（ms）：{times}。计时仅包含细化与像素图构建；不包含标注、文件读写、诊断或绘图。</p><p>原始标注说明：{esc(a['notes'])}</p><p>来源：{esc(a['provenance'])}；审核状态：{esc(a['review_status'])}；审核人：{esc(a.get('reviewer') or '未提供')}。</p><p>{links}</p><p>错误记录说明：现有 diagnostics.json 没有独立的 warnings/errors 字段；以上为已存诊断结果与项目复核报告中的观察，不代表完整运行日志。</p></details></article>''')
        rows.append(f'<tr><th scope="row"><a href="#{sid}">{sid}{" ⚠" if sid in notes else ""}</a></th><td>{d["skeleton_pixels"]}</td><td>{d["skeleton_components"]}</td><td>{d["endpoints"]}</td><td>{d["junction_pixels"]}</td><td>{len(g["edges"])}</td><td>{d["median_inference_seconds"]*1000:.1f}</td><td>DRAFT</td></tr>')
    style = '''
:root{color-scheme:light;--ink:#173047;--muted:#52677a;--line:#d9e3e9;--teal:#076c72}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:100px}body{margin:0;background:#f2f6f8;color:var(--ink);font:15px/1.7 system-ui,"Microsoft YaHei",sans-serif}a{color:var(--teal);text-underline-offset:3px}a:hover{text-decoration:underline}button{font:inherit}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #cf6817;outline-offset:3px}.hero{background:#142f43;color:white;padding:48px max(24px,calc((100vw - 1440px)/2));border-bottom:5px solid #36b6ab}.eyebrow{letter-spacing:.14em;color:#a4ded8;font-size:12px}h1{font-size:clamp(26px,3.6vw,44px);line-height:1.3;margin:12px 0}.hero p{max-width:900px;color:#d4e4ed}.badge{display:inline-block;background:#fff0d4;border:1px solid #e8bf6c;border-radius:6px;color:#7c4807;padding:3px 10px;font-size:12px;font-weight:700}.nav{position:sticky;top:0;z-index:5;background:#ffffffef;backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:10px 20px;display:flex;gap:8px;overflow-x:auto;white-space:nowrap}.nav a{padding:5px 10px;border-radius:5px;text-decoration:none;background:#eef4f6;font-size:13px}.nav .flag{box-shadow:inset 0 -2px #dc9b3a}main{max-width:1488px;margin:auto;padding:28px 24px}section,.sample{background:white;border:1px solid var(--line);border-radius:12px;padding:26px;margin-bottom:28px}h2{font-size:23px;margin:0 0 12px}h3{font-size:17px}.notice,.warning{padding:12px 16px;border-left:4px solid #d39432;background:#fff8eb;border-radius:4px}.summary-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:18px 0}.metrics div{padding:12px;background:#f1f6f8;border-radius:7px}.metrics dt{font-size:12px;color:var(--muted)}.metrics dd{font-size:23px;font-weight:700;margin:5px 0 0}.sample-head{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.sample-head h2{margin:0}.sample-head>a{margin-left:auto;font-size:13px}.priority{border:2px solid #d38b2a}.panels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}figure{margin:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#f6f9fa}figcaption{padding:10px 14px;font-weight:650}figcaption span{color:var(--teal);font-size:12px;margin-right:6px}figcaption small{display:block;font-weight:400;color:var(--muted);font-size:12px}.visual{display:block;padding:0;border:0;width:100%;background:#0e1720;cursor:zoom-in;overflow:hidden}.visual img,.visual svg{display:block;width:100%;height:auto;aspect-ratio:4/3}.legend{font-size:13px;color:var(--muted)}details{border-top:1px solid var(--line);padding-top:12px}summary{cursor:pointer;font-weight:600}details p{font-size:13px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:right;font-size:13px}th,td{padding:9px 12px;border-bottom:1px solid var(--line);white-space:nowrap}th:first-child{text-align:left}thead{background:#edf4f6}.hint{color:var(--muted);font-size:13px}dialog{border:0;border-radius:12px;padding:16px;max-width:96vw;width:1100px;max-height:94vh;overflow:auto;background:#f5f8fa}dialog::backdrop{background:#081c2bdc}.dialog-head{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-bottom:12px}dialog button{padding:7px 15px;cursor:pointer;border:1px solid var(--line);border-radius:5px;background:white}#enlarged img,#enlarged svg{display:block;width:100%;height:auto}footer{text-align:center;color:var(--muted);font-size:12px;padding:10px 0 30px}@media(max-width:900px){.metrics{grid-template-columns:repeat(3,1fr)}.summary-grid{grid-template-columns:1fr;gap:0}}@media(max-width:600px){main{padding:16px 10px}section,.sample{padding:16px}.panels{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.hero{padding:30px 20px}.sample-head>a{margin-left:0}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{.nav,dialog,.sample-head>a{display:none}body{background:white}.sample{break-before:page}.panels{grid-template-columns:1fr 1fr}details{display:block}}
'''
    revision_link = ('<p class="notice"><strong>新增覆盖修订：</strong><a href="coverage_revision_v4/run/index.html">查看 12 样本修订前后对比、质量检查与修订草稿</a>。10 个样本补充可见区域，2 个样本因歧义保留；全部仍待人工审核。本页继续展示原始 draft_run。</p>' if (OUT / 'coverage_revision_v4/run/index.html').is_file() else '')
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MMA3001 · Step 3 真实数据结果图库</title><style>{style}</style></head><body>
<header class="hero"><div class="eyebrow">MMA3001 / STEP 03 / REAL-DATA REVIEW</div><h1>真实苹果树 · 可见枝条结果图库</h1><p>12 个真实 RGB 样本，从可见区域草稿到二维骨架与像素图。直接复用 draft_run 中的既有输出，供逐图目视检查。</p><span class="badge">全部标注 DRAFT · 0 个已通过人工审核样本</span></header>
<nav class="nav" aria-label="样本快速导航"><a href="#overview">总览</a><a href="#measurements">指标表</a>{''.join(nav)}</nav>
<main><section id="overview"><h2>当前状态与阅读指南</h2>{revision_link}<p class="notice"><strong>DRAFT：12 / 12 均待人工审核。</strong>标注是从 RGB 人工式描绘的 AI 保守多边形草稿，不是独立人工验证真值。当前没有可报告的真实重建准确率、IoU、F1 或三维精度。</p>
<div class="summary-grid"><div><h3>当前已具备</h3><p>对给定的可见枝条二值掩膜进行细化、提取 2D 骨架、构建含节点／边／连通分量的像素图，并记录连通性与运行时间。12 个样本的输入分量均一一保留，30 / 30 个标注片区中存在骨架像素，骨架越出输入区域的像素数为 0。</p><p>样本计时中位数的中位数为 <strong>{summary['median_sample_runtime_seconds']*1000:.1f} ms</strong>，范围 {summary['min_sample_runtime_seconds']*1000:.1f}–{summary['max_sample_runtime_seconds']*1000:.1f} ms。每样本预热一次后重复 5 次；仅细化与图构建，不是端到端 RGB 处理时间。</p></div>
<div><h3>当前限制与复核重点</h3><p>基线需要外部提供掩膜，不能自动从 RGB 识别枝条，也不能恢复遮挡后的真实连接或完成 3D 重建。分量保留和片区存活只是对草稿输入的实现诊断，不代表枝条完整性、召回率或解剖结构正确。</p><p>优先检查 <a href="#R06N02">R06N02 的额外短刺</a>、R03N02 / R07N02 的遮挡，以及 R01N02 / R09N02 / R12N02 的人工间隙。样本是 R01–R12 的 N02 便利样本，未形成独立留出验证；尚无独立中心线／拓扑标签或深度标定。</p></div></div>
<p class="hint">使用方法：顶部跳转到样本，点击图像放大，按 Esc 或“关闭”返回；浏览器缩放可进一步检查细节。五面板按原始 RGB → 标注叠加 → 掩膜 → 骨架 → 图结构排列。所有派生结果均来自 DRAFT 输入。标注叠加和图结构面板直接显示既有 comparison.png 的对应图像区域，没有重新计算或重新绘制结果。</p>
<p><a href="draft_run/contact_sheet.png">打开既有 12 样本联系表</a> · <a href="draft_run/summary.json">汇总 JSON</a> · <a href="draft_run/summary.csv">汇总 CSV</a> · <a href="../../docs/12_step3_real_data_review.md">项目复核说明</a></p></section>
<section id="measurements"><h2>实际测量总览</h2><p class="hint">数值来自各样本 diagnostics.json；边数来自 graph.json。交汇为像素计数，时间为本次既有运行的中位数。⚠ 表示现有报告提及的复核问题。</p><div class="table-wrap"><table><thead><tr><th>样本</th><th>骨架像素</th><th>连通分量</th><th>端点</th><th>交汇像素</th><th>图边数</th><th>时间 ms</th><th>标注状态</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
{''.join(cards)}</main><footer>来源：results/step3_real_validation/draft_run/ · 离线相对路径 · 仅展示既有结果 · 未修改数据集</footer>
<dialog id="viewer" aria-labelledby="viewer-title"><div class="dialog-head"><strong id="viewer-title"></strong><button id="close-viewer" type="button">关闭 ×</button></div><div id="enlarged"></div></dialog>
<script>
const viewer=document.getElementById('viewer');
document.querySelectorAll('.visual').forEach(button=>button.addEventListener('click',()=>{{
document.getElementById('viewer-title').textContent=button.dataset.title;
document.getElementById('enlarged').replaceChildren(button.firstElementChild.cloneNode(true));
viewer.showModal();
}}));
document.getElementById('close-viewer').addEventListener('click',()=>viewer.close());
viewer.addEventListener('click',event=>{{if(event.target===viewer){{const r=viewer.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)viewer.close();}}}});
</script></body></html>'''
    destination = OUT / 'index.html'
    destination.write_text(page, encoding='utf-8')
    print(f'Created {destination}: {len(cards)} samples, {len(cards)*5} image panels.')


if __name__ == '__main__':
    build()
