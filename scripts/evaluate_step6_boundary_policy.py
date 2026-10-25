"""Versioned Step 6 angular-boundary audit using frozen, saved observations.

Never regenerates the simulator or overwrites v1 results. Legacy replay uses
the archived pre-fix completion source; current replay uses the installed policy.
"""
from pathlib import Path
import argparse,copy,hashlib,html,importlib.util,json,math,os,re,shutil,subprocess,sys,tempfile,types,uuid,zipfile
from datetime import datetime,timezone
import numpy as np
from PIL import Image
import apple_tree_project.completion as completion

ROOT=Path(__file__).resolve().parents[1]
V1=ROOT/'results/step6_final_validation'
DEFAULT_OUT=ROOT/'results/step6_final_validation_v2_boundary_policy'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

def json_graph(graph):return json.loads(json.dumps(graph,allow_nan=False))

def infer(study,algorithm,arrays,camera,settings):
    previous=study.detect_candidate_gaps,study.complete_gaps
    try:
        study.detect_candidate_gaps=algorithm.detect_candidate_gaps
        study.complete_gaps=algorithm.complete_gaps
        return study.infer_all(arrays['visible'],arrays['depth'],camera,arrays['visible'],arrays['occlusion'],settings)
    finally:study.detect_candidate_gaps,study.complete_gaps=previous

def holdout_19_roundoff(study,legacy,arrays,camera,settings):
    output=[];old_math=legacy.math;old_gate=completion._angular_threshold_state
    for angle in (44.99999999999987,45.,45.00000000000011):
        namespace=types.SimpleNamespace(**{k:getattr(math,k) for k in dir(math) if not k.startswith('__')})
        def forced_acos(value,angle=angle):
            radians=old_math.acos(value)
            return math.radians(angle) if abs(math.degrees(radians)-45.)<1e-8 else radians
        namespace.acos=forced_acos
        try:
            legacy.math=namespace
            old=infer(study,legacy,arrays,camera,settings)
            def forced_gate(value,threshold,angle=angle):
                return old_gate(angle,threshold) if threshold==45. and abs(value-45.)<completion.ANGLE_BOUNDARY_GUARD_DEG else old_gate(value,threshold)
            completion._angular_threshold_state=forced_gate
            new=infer(study,completion,arrays,camera,settings)
        finally:legacy.math=old_math;completion._angular_threshold_state=old_gate
        for method in study.METHODS:
            output.append(dict(simulated_boundary_angle_deg=angle,method=method,
                               v1_nodes=len(old[method]['graph3d']['nodes']),v2_nodes=len(new[method]['graph3d']['nodes']),
                               v1_inferred=sum(n['inferred'] for n in old[method]['graph3d']['nodes']),
                               v2_inferred=sum(n['inferred'] for n in new[method]['graph3d']['nodes']),
                               v2_accepted=len(new[method]['accepted']),
                               scope='controlled numerical perturbation in one environment; not a second physical OS run'))
    return output

def real_review(study,out):
    import matplotlib.pyplot as plt
    rows=[];logs=[]
    source=ROOT/'results/step3_real_validation/coverage_revision_v4/run'
    old_rows=study.load(V1/'real/qualitative_comparison.json')
    for path in sorted((ROOT/'results/step4_occlusion_completion/real').glob('R*.json')):
        old=study.load(path);sample=old['sample_id'];annotation=study.load(source/sample/'annotation.json')
        visible=np.array(Image.open(source/sample/'skeleton.png'))>0
        detection=completion.detect_candidate_gaps(visible,max_gap_px=100)
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        records={}
        for axis,method in zip(axes,study.METHODS):
            result=study.baseline_result(visible) if method=='visible_only' else completion.complete_gaps(visible,detection['candidates'],~visible,method,max_gap_px=100)
            graph=result['graph'];previous=next(r for r in old_rows if r['sample_id']==sample and r['method']==method)
            row=dict(sample_id=sample,method=method,classification='UNCALIBRATED/QUALITATIVE',annotation_status='AI DRAFT / pending',
                     human_accepted=False,independent_manual_review_required=sample in {'R06N02','R08N02','R09N02','R10N02'},
                     components=len(graph['components']),nodes=len(graph['nodes']),edges=len(graph['edges']),
                     cycle_rank=len(graph['edges'])-len(graph['nodes'])+len(graph['components']),
                     accepted_hypotheses=len(result['accepted']),v1_accepted_hypotheses=previous['accepted_hypotheses'],
                     rejected_requests=len(result['rejected']),candidate_rejections=len(detection['rejected']),
                     occlusion_confirmed=False,real_metric_xyz_supported=False)
            rows.append(row);records[method]=dict(graph=graph,accepted=result['accepted'],rejected=result['rejected'])
            for hidden,color in ((False,'#008b9a'),(True,'#ce1689')):
                points=np.array([[n['x'],n['y']] for n in graph['nodes'] if n['inferred']==hidden])
                if len(points):axis.scatter(*points.T,s=4,c=color,label='inferred hypothesis' if hidden else 'visible draft')
            axis.set(xlim=(0,640),ylim=(480,0),aspect='equal',xlabel='u image pixels',ylabel='v image pixels',title=method)
            axis.legend(fontsize=6)
        fig.suptitle(sample+' | V2 numerical policy | AI DRAFT / NOT metric 3D'+(' | HUMAN REVIEW REQUIRED' if row['independent_manual_review_required'] else ''))
        fig.tight_layout();folder=out/'real';folder.mkdir(exist_ok=True);fig.savefig(folder/f'{sample}.png',dpi=130);plt.close(fig)
        logs.append(dict(sample_id=sample,annotation_provenance=annotation,detection=detection,methods=records))
    study.table(out/'real/qualitative_comparison.csv',rows);study.save(out/'real/qualitative_comparison.json',rows)
    study.save(out/'real/decisions.json',logs)
    return rows

def figures(study,out,rows,comparison):
    import matplotlib.pyplot as plt
    summaries=study.summaries(rows)
    group=[r for r in summaries if r['cohort']=='independent_holdout' and r['scope']=='all_cases']
    fig,axes=plt.subplots(1,3,figsize=(14,4),constrained_layout=True)
    for ax,field in zip(axes,('mean_hidden_added_recall_2px','mean_chamfer_3d_m','mean_coverage_3cm')):
        ax.bar([r['method'] for r in group],[r[field] for r in group],color=['#aaa','#168b9a','#ce1689'])
        ax.set(title=field);ax.tick_params(axis='x',rotation=15)
    fig.suptitle('V2: strict-below angular policy; all 48 cases retained')
    fig.savefig(out/'figures/holdout_comparison_v2.png',dpi=140);plt.close(fig)
    for cohort,factor in [('targeted_3d_gap','gap_width_px'),('targeted_physical_curvature','curvature')]:
        selected=[r for r in rows if r['cohort']==cohort];values=sorted({r[factor] for r in selected})
        fig,axes=plt.subplots(1,3,figsize=(15,4),constrained_layout=True)
        for method in study.METHODS:
            for ax,field in zip(axes,('hidden_added_recall_2px','rmse_3d_m','coverage_3cm')):
                ax.plot(values,[np.mean([r[field] for r in selected if r['method']==method and r[factor]==v]) for v in values],'-o',label=method)
                ax.set(xlabel=factor,ylabel=field);ax.grid(alpha=.3)
        axes[0].legend();fig.suptitle('V2 frozen-input diagnostics; no retuning')
        fig.savefig(out/f'figures/{cohort}_v2.png',dpi=140);plt.close(fig)

def report(study,out,rows,summary,graph_audit,comparison,holdout,real):
    totals=study.load(out/'tests/totals.json')
    changed=[r for r in graph_audit if r['changed_from_v1']]
    fields=['method','accepted_cases_v1','accepted_cases_v2','mean_full_chamfer_px_v1','mean_full_chamfer_px_v2',
            'mean_hidden_added_recall_2px_v1','mean_hidden_added_recall_2px_v2','mean_rmse_3d_m_v1','mean_rmse_3d_m_v2',
            'mean_chamfer_3d_m_v1','mean_chamfer_3d_m_v2','mean_coverage_3cm_v1','mean_coverage_3cm_v2']
    headline=[r for r in comparison if r['cohort']=='independent_holdout' and r['scope']=='all_cases']
    text='''# Step 6 v2：角阈值数值稳定性与重新验证

## 问题与边界规则

v1 的 detect_candidate_gaps 直接判断 max(turns)>45。相同像素路径的最小二乘切向、单位化、点积和 acos 在不同数值后端可能给出45度上下的微小误差；离散接受/拒绝不能由几何坐标 allclose 补救。观察到的问题不应通过删案例、改45度参数或放宽重放节点数量来掩盖。

采用固定 policy=strict_below_angular_guard_v1，guard=0.00001度。
仅当 angle < threshold-guard 时允许通过；[threshold-guard,threshold+guard]（含端点和精确等于threshold）数值不确定，保守拒绝；超过上边界也拒绝。方向角与局部曲率角使用相同规则，距离/角色筛选、_tangent、拟合、栅格化、拓扑和3D lifting未改变。

误差尺度依据：float64 epsilon=2^-52。假定单位向量点积的数值扰动预算为32 epsilon，acos在±1附近的最坏一阶尺度为sqrt(2 delta)，得到sqrt(64 epsilon)弧度，约6.83e-6度；向上取整成固定1e-5度。固定字面常量不随平台库、案例或精度得分重新计算。该预算是明确的工程舍入防护，不是任意病态最小二乘的严格全局误差上界，也不是相机/传感器精度。角度单位及物理阈值仍为度，没有调参争取更高得分。

此策略故意改变“恰好等于阈值可接受”的旧语义；非常接近下边界 threshold-guard 的病态输入仍需更高精度/区间运算进一步审计。0度曲率阈值不可能严格低于其防护边界，因此会保守拒绝，而非默认接受精确零角。

## 冻结输入与版本

原 results/step6_final_validation/ 和所有旧ZIP保留为v1历史，不覆盖。复制原 frozen_experiment_plan.json、78个原 NPZ 和标定文件，SHA256逐文件一致，未调用make_scene或重新随机生成观测/真值。
全部234图逐一比较。未变化图逐字节复制；变化图重新生成并保存v1对应图供复核。几何指标只对变化图重算；所有图的候选/拒绝计数按新策略刷新。各方法和接受/全案例/共同接受的分母与v1相同定义，拒绝案例始终保留。
历史Step4/5扫描与v1性能记录只作为明确标记的历史证据；本次不重跑旧扫描，不把旧运行时间冒充新策略计时。

## 全部图一致性审计

'''+f'共审计234图，其中{len(changed)}图相对v1变化，{234-len(changed)}图保留。详情见graph_policy_audit.csv；v1在原算法源码下重放，v2在当前策略下重放；节点身份、像素、边、状态精确，几何使用atol=1e-12、rtol=1e-10。\n\n'+'''所有新图还分别在角判据加/减1e-12度的受控扰动下检查，模拟已报告舍入尺度；这些是单环境故障注入，不是声称已在第二台机器或另一操作系统运行。未证明所有BLAS版本/任意病态支持点都逐位一致。

## holdout_19 专项

原观测mask有189个像素，原流程的thin_visible预处理后187个节点。复核必须保留这一步，不能把直接在原观测mask上建图的189节点结果与保存图比较。

'''+study.md_table(holdout,['simulated_boundary_angle_deg','method','v1_nodes','v2_nodes','v1_inferred','v2_inferred','v2_accepted'])+'''
原v1在本机已拒绝holdout_19，所以此例本机最终图可以不变；但v2明确拒绝两侧舍入值，不能据单例未变推断整个比较指标不变。

## 独立48配置：v1/v2对照

所有误差为各案例指标均值，RMSE以有支持点条件化，方法点数可能不同，不能孤立排序；Chamfer与覆盖使用每例固定参考。3D单位米，2D单位像素。新增隐藏中心线召回与完整预测的边缘邻域召回分开。

'''+study.md_table(headline,fields)+'''
完整对照包含目标诊断和各接受子集，见comparison_metrics_v1_v2.csv。边界策略可能降低补全接受率和覆盖；这是明确数值政策的代价，不修改阈值把分数调回原结果。全案例和配对/各自接受子集必须分别解读。

## 真实数据与局限

12个真实样本重新评估候选/补全决策，仅为640x480图像像素示意；所有标注仍AI DRAFT/pending，未确认遮挡、未使用Summer GT计算精度，也没有真实米制3D。R06N02/R08N02/R09N02/R10N02继续要求独立人工复核。真实候选也可能因同一边界政策被拒绝，旧示意仍在v1保留。
本次数值修复不能认证树体身份、隐藏枝条真实性或真实深度标定。最终提交只能准确声明“校准合成验证与真实定性草稿”；若课程要求可靠真实米制3D，此项仍未满足。没有自动标记所有工程要求完成。

## 验证与复现

'''+json.dumps(totals,ensure_ascii=False)+'''

完整pytest、保存结果重放、Step5原15图重放、HTML/PNG检查、git diff --check及原数据/全部历史结果SHA256/大小/mtime检查见verification/与tests/。旧源代码和旧文档快照见history/。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python scripts/replay_step6_saved.py --results results/step6_final_validation_v2_boundary_policy
python scripts/evaluate_step6_boundary_policy.py --output results/step6_boundary_another_run
```

完整评估命令必须使用新目录，并需要保留的v1输入和旧源码history；解压后的project/可以用 `python scripts/replay_step6_saved.py --results ../results` 独立重放234个v2图，不需原始RGB-D。测试使用仅包含合成观测的holdout_19回归fixture，不读GT推断。
不提交/推送Git，不开始Step7。
'''
    study.write(out/'technical_report.md',text)
    return text

def archive(study,out):
    target=ROOT/'results/step6_review_package_v2_boundary_policy.zip'
    if target.exists():raise ValueError('New ZIP filename required; existing package preserved')
    entries=[]
    for p in sorted(out.rglob('*')):
        if p.is_file():entries.append((p,'step6_review_package_v2/results/'+p.relative_to(out).as_posix()))
    study.write(out/'SHA256SUMS.txt',''.join(study.fingerprint(p)['sha256']+'  '+p.relative_to(out).as_posix()+'\n' for p,_ in entries))
    entries.append((out/'SHA256SUMS.txt','step6_review_package_v2/results/SHA256SUMS.txt'))
    for folder in ('src','scripts','tests','docs','data/demo','data/annotations'):
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and not any(k in p.parts for k in ('__pycache__','.pytest_cache')):entries.append((p,'step6_review_package_v2/project/'+p.relative_to(ROOT).as_posix()))
    for name in ('README.md','pyproject.toml','LICENSE','.gitignore'):entries.append((ROOT/name,'step6_review_package_v2/project/'+name))
    hashes={}
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,name in entries:z.write(p,name);hashes[name]=study.fingerprint(p)['sha256']
        readme='# Step 6 v2 numerical boundary review\n\nOpen results/index.html and results/technical_report.md. v1 historical outcomes, original completion source and affected old graphs are retained in results/history.\n\nFrom project/: install .[study,dev], PYTHONPATH=src, python -m pytest -p no:cacheprovider. Replay without original RGB-D: python scripts/replay_step6_saved.py --results ../results\nThe full version-audit script additionally needs the separately retained v1 source tree, not raw RGB-D.\nAll real data remains AI DRAFT/UNCALIBRATED. No original dataset files, environments or caches included.\n'
        z.writestr('step6_review_package_v2/README.md',readme);hashes['step6_review_package_v2/README.md']=hashlib.sha256(readme.encode()).hexdigest()
        z.writestr('step6_review_package_v2/ZIP_MEMBER_SHA256.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in hashes.items())
        count=len(z.namelist())
    study.save(target.with_suffix('.zip.integrity.json'),dict(sha256=study.fingerprint(target)['sha256'],bytes=target.stat().st_size,
               members=count,crc_ok=True,member_sha256_ok=True))
    return target

def run(out,legacy_source,preservation_manifest=None):
    import matplotlib
    matplotlib.use('Agg')
    out=Path(out).resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results'):raise ValueError('New results directory required')
    study=module('step6_v2_study',ROOT/'scripts/evaluate_step6.py')
    policy=module('step6_v2_compare',ROOT/'scripts/replay_saved_synthetic.py')
    plan=study.load(V1/'frozen_experiment_plan.json')
    if plan['configs']!=study.experiment_configs() or plan['settings']!=study.SETTINGS:raise ValueError('Frozen plan mismatch')
    out.mkdir();(out/'history').mkdir();(out/'figures').mkdir();(out/'verification').mkdir()
    shutil.copy2(legacy_source,out/'history/completion_v1.py')
    legacy=module('apple_tree_project._completion_v1',out/'history/completion_v1.py')
    for name in ('all_case_metrics.json','overall_algorithm_comparison.json','decisions.json'):
        shutil.copy2(V1/name,out/'history'/name)
    for name in ('README.md','docs/16_step6_final_validation.md','docs/05_development_log.md'):
        shutil.copy2(ROOT/name,out/'history'/Path(name).name)
    shutil.copy2(V1/'frozen_experiment_plan.json',out/'frozen_experiment_plan.json')
    if preservation_manifest:shutil.copy2(preservation_manifest,out/'verification/preservation_before.json')
    study.save(out/'numerical_policy.json',dict(name=completion.ANGLE_BOUNDARY_POLICY,guard_deg=completion.ANGLE_BOUNDARY_GUARD_DEG,
               accepts='angle < threshold - guard',ambiguous='abs(angle-threshold) <= guard; reject',
               threshold_values=plan['settings'],basis='32*float64_eps dot budget, acos conditioning, upward rounded fixed degree band',
               legacy_source_sha256=study.fingerprint(out/'history/completion_v1.py')['sha256']))
    old_rows=study.load(V1/'all_case_metrics.json');rows=[r for r in old_rows if r['cohort']=='step5_saved']
    audit=[];all_decisions=[];old_replayed=0;legacy_drift=[];holdout=[]
    for index,config in enumerate(plan['configs']):
        case=config['case_id'];src=V1/'synthetic'/case;dst=out/'synthetic'/case;dst.mkdir(parents=True)
        for name in ('inputs_and_reference.npz','calibration.json'):shutil.copy2(src/name,dst/name)
        with np.load(src/'inputs_and_reference.npz',allow_pickle=False) as data:arrays={k:data[k] for k in data.files}
        camera=study.Calibration(**study.load(src/'calibration.json'))
        original=infer(study,legacy,arrays,camera,plan['settings'])
        results=infer(study,completion,arrays,camera,plan['settings'])
        scene=dict(arrays,config=config,camera=camera)
        case_rows=[];case_logs=[]
        for method in study.METHODS:
            expected=study.load(src/f'{method}_graph3d.json')
            try:policy.compare_graphs(json_graph(original[method]['graph3d']),expected)
            except AssertionError as error:legacy_drift.append(dict(case_id=case,method=method,error=str(error)))
            old_replayed+=1
            graph=json_graph(results[method]['graph3d'])
            try:policy.compare_graphs(graph,expected);changed=False
            except AssertionError:changed=True
            if changed:
                measured,logs=study.evaluate_scene(scene,{method:results[method]},case,config['cohort']);row=measured[0]
                study.save(dst/f'{method}_graph3d.json',graph)
                old_dst=out/'history/affected_v1_graphs'/case;old_dst.mkdir(parents=True,exist_ok=True)
                shutil.copy2(src/f'{method}_graph3d.json',old_dst/f'{method}_graph3d.json')
            else:
                row=copy.deepcopy(next(r for r in old_rows if r['case_id']==case and r['method']==method))
                shutil.copy2(src/f'{method}_graph3d.json',dst/f'{method}_graph3d.json')
            r=results[method];row.update(detector_candidates=len(r['detection']['candidates']),detector_rejected_pairs=len(r['detection']['rejected']),
                   accepted_requests=len(r['accepted']),completion_rejected_requests=len(r['rejected']),completed=bool(r['accepted']))
            log=dict(case_id=case,method=method,detection=r['detection'],accepted=r['accepted'],rejected=r['rejected'],depth_rejections=r['graph3d']['hidden_depth_rejections'])
            case_rows.append(row);case_logs.append(log)
            audit.append(dict(case_id=case,cohort=config['cohort'],method=method,changed_from_v1=changed,
                              old_nodes=len(expected['nodes']),new_nodes=len(graph['nodes']),
                              old_inferred=sum(n['inferred'] for n in expected['nodes']),new_inferred=sum(n['inferred'] for n in graph['nodes']),
                              old_supported=sum(n['xyz_m'] is not None for n in expected['nodes']),new_supported=sum(n['xyz_m'] is not None for n in graph['nodes']),
                              ambiguous_rejections=sum('numerically_ambiguous' in x['reason'] for x in r['detection']['rejected'])))
        rows.extend(case_rows);all_decisions.extend(case_logs)
        study.save(dst/'case_metrics.json',case_rows);study.save(dst/'case_decisions.json',case_logs)
        if case=='holdout_19':
            holdout=holdout_19_roundoff(study,legacy,arrays,camera,plan['settings'])
            study.save(out/'holdout_19_roundoff.json',holdout)
        if case=='holdout_19' or any(a['changed_from_v1'] for a in audit[-3:]):
            study.panels(scene,results,dst/'comparison.png',case+' | V2 numerical policy | CALIBRATED SYNTHETIC')
        if (index+1)%12==0:print(f'Boundary audit {index+1}/78 cases',flush=True)
    study.table(out/'graph_policy_audit.csv',audit);study.save(out/'graph_policy_audit.json',audit)
    study.table(out/'all_case_metrics.csv',rows);study.save(out/'all_case_metrics.json',rows);study.save(out/'decisions.json',all_decisions)
    summary=study.summaries(rows);study.table(out/'overall_algorithm_comparison.csv',summary);study.save(out/'overall_algorithm_comparison.json',summary)
    old_summary=study.load(V1/'overall_algorithm_comparison.json');comparison=[]
    compare_fields=['cases','accepted_cases','rejected_or_no_completion_cases','case_acceptance_rate','incorrect_connections',
        'mean_full_chamfer_px','mean_hidden_added_recall_2px','mean_rmse_3d_m','mean_chamfer_3d_m','mean_coverage_3cm','mean_components_3d']
    for new in summary:
        old=next(r for r in old_summary if all(r[k]==new[k] for k in ('cohort','method','scope')))
        comparison.append(dict(**{k:new[k] for k in ('cohort','method','scope')},
            **{k+'_v1':old[k] for k in compare_fields},**{k+'_v2':new[k] for k in compare_fields}))
    study.table(out/'comparison_metrics_v1_v2.csv',comparison);study.save(out/'comparison_metrics_v1_v2.json',comparison)
    study.save(out/'verification/v1_legacy_replay.json',dict(graphs_checked=old_replayed,legacy_source=str(out/'history/completion_v1.py'),all_passed=not legacy_drift,mismatches=legacy_drift))
    # Verify equality of the fixed graph outcomes under +/-1e-12 degree roundoff.
    gate=completion._angular_threshold_state;jitter=[]
    try:
        for perturbation in (-1e-12,1e-12):
            completion._angular_threshold_state=lambda value,threshold,p=perturbation:gate(value+p,threshold)
            count=0
            for config in plan['configs']:
                folder=out/'synthetic'/config['case_id']
                with np.load(folder/'inputs_and_reference.npz',allow_pickle=False) as a:observations={k:a[k] for k in ('visible','depth','occlusion')}
                camera=study.Calibration(**study.load(folder/'calibration.json'))
                actual=infer(study,completion,observations,camera,plan['settings'])
                for method in study.METHODS:
                    policy.compare_graphs(json_graph(actual[method]['graph3d']),study.load(folder/f'{method}_graph3d.json'));count+=1
            jitter.append(dict(angle_perturbation_deg=perturbation,graphs_checked=count,all_passed=True))
    finally:completion._angular_threshold_state=gate
    study.save(out/'verification/roundoff_fault_injection.json',dict(runs=jitter,scope='controlled same-environment decision perturbations; not a second platform'))
    real=real_review(study,out)
    # Preserve old timing/sensitivity as historical records rather than remeasure.
    shutil.copytree(V1/'performance',out/'history/v1_performance')
    shutil.copytree(V1/'reuse',out/'history/v1_reused_evidence')
    negatives=study.negative_experiments(out);study.failure_report(out,rows,negatives)
    figures(study,out,rows,comparison)
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONPATH']=str(ROOT/'src')
    for script,args,stem in [('replay_step6_saved.py',['--results',str(out)],'v2_saved_replay'),('replay_saved_synthetic.py',[],'step5_saved_replay')]:
        result=subprocess.run([sys.executable,str(ROOT/'scripts'/script),*args,'--report',str(out/'verification'/f'{stem}.json')],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        study.write(out/'verification'/f'{stem}.txt',result.stdout+'\nSTDERR:\n'+result.stderr)
        if result.returncode:raise RuntimeError(stem+' failed')
    totals=study.complete_tests(out)
    text=report(study,out,rows,summary,audit,comparison,holdout,real)
    # Latest technical conclusions are appended; previous numerical reports remain historical.
    doc=ROOT/'docs/16_step6_numerical_stability.md'
    if doc.exists():raise ValueError('Version-2 document already exists')
    doc.write_text(text,encoding='utf-8')
    with (ROOT/'docs/16_step6_final_validation.md').open('a',encoding='utf-8') as f:
        f.write('\n\n## Step 6 v2 数值边界策略（最新结论）\n\n原表格是v1历史。当前版本采用阈值±1e-5度保守拒绝带；全234图重放、指标变更和提交范围见[数值稳定性报告](16_step6_numerical_stability.md)，图库位于results/step6_final_validation_v2_boundary_policy/index.html。完整测试：'+json.dumps(totals,ensure_ascii=False)+'。\n')
    with (ROOT/'README.md').open('a',encoding='utf-8') as f:
        f.write('\n\n### Step 6 v2 numerical boundary policy\n\nUse [the current numerical stability report](docs/16_step6_numerical_stability.md) and [v2 gallery](results/step6_final_validation_v2_boundary_policy/index.html). Earlier Step 6 tables/ZIP are preserved v1 history. Angular comparisons reject the fixed ±0.00001 degree ambiguity band. No threshold retuning or real metric 3D claims.\n')
    with (ROOT/'docs/05_development_log.md').open('a',encoding='utf-8') as f:
        f.write('\n\n## Step 6 v2 angular boundary stability\n\nFixed conservative numerical boundary policy; frozen inputs/plan preserved. Audited 234 graphs against archived v1 source and current policy, regenerated affected outputs in a new version, checked +/-1e-12 degree decision perturbations and holdout_19. Full suite: '+json.dumps(totals)+'. Original data/results/ZIP unchanged. See docs/16_step6_numerical_stability.md. No commit/push or Step7.\n')
    parts=['<!doctype html><meta charset="utf-8"><title>Step 6 v2 numerical stability</title><style>body{font:16px system-ui;background:#111827;color:white;margin:25px}a{color:#84d5ff}img{max-width:100%;background:white}</style>',
       '<h1>Step 6 v2：保守角边界数值策略</h1><p>固定±0.00001度不确定带，拒绝边界；CALIBRATED SYNTHETIC / 真实仅AI DRAFT。</p>',
       '<p><a href="technical_report.md">技术报告</a> · <a href="comparison_metrics_v1_v2.csv">v1/v2指标对照</a> · <a href="graph_policy_audit.csv">234图审计</a> · <a href="holdout_19_roundoff.json">holdout_19</a> · <a href="tests/pytest_output.txt">完整测试</a> · <a href="verification/v2_saved_replay.json">v2重放</a></p>']
    for p in sorted((out/'figures').glob('*.png')):parts.append(f'<h2>{p.stem}</h2><img src="{p.relative_to(out).as_posix()}">')
    for p in sorted((out/'synthetic').glob('*/comparison.png')):parts.append(f'<details><summary>{p.parent.name}</summary><img src="{p.relative_to(out).as_posix()}"></details>')
    parts.append('<h2>真实12样本：DRAFT、非米制、未确认遮挡</h2>')
    for p in sorted((out/'real').glob('*.png')):parts.append(f'<h3>{p.stem}'+(' — 独立人工复核必需' if p.stem in {'R06N02','R08N02','R09N02','R10N02'} else '')+f'</h3><img src="{p.relative_to(out).as_posix()}">')
    study.write(out/'index.html','\n'.join(parts));study.verify_artifacts(out)
    if preservation_manifest:
        original=study.load(preservation_manifest);allowed={'src/apple_tree_project/completion.py','scripts/replay_step6_saved.py','README.md','docs/05_development_log.md','docs/16_step6_final_validation.md'}
        changed=[n for n,v in original.items() if n not in allowed and study.fingerprint(ROOT/n)!=v]
        if changed:raise RuntimeError('Protected historical files changed: '+repr(changed))
        study.save(out/'verification/preservation_after.json',dict(protected_files=len(original)-len(allowed),changed_files=changed,
                    allowed_source_document_updates=sorted(allowed),raw_tree_files=sum(n.startswith('data/raw/monash_y_tree/TreeID/') for n in original)))
    git=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
    study.write(out/'verification/git_diff_check.txt',f'Exit code {git.returncode}\n'+git.stdout+git.stderr)
    if git.returncode:raise RuntimeError('Whitespace check failed')
    study.save(out/'reproducibility.json',dict(utc=datetime.now(timezone.utc).isoformat(),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       frozen_plan_sha256=study.fingerprint(out/'frozen_experiment_plan.json')['sha256'],simulator_called=False,inputs_reused=78,
       old_graphs_replayed=234,new_graphs_replayed=234,changed_graphs=len([r for r in audit if r['changed_from_v1']]),
       decision_policy=completion.ANGLE_BOUNDARY_POLICY,guard_deg=completion.ANGLE_BOUNDARY_GUARD_DEG,tests=totals,
       calibration_invented=False,real_metric_accuracy_claimed=False,committed=False,pushed=False))
    target=archive(study,out)
    print(json.dumps(dict(output=str(out),zip=str(target),changed_graphs=sum(r['changed_from_v1'] for r in audit),tests=totals),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--legacy-source',type=Path,default=DEFAULT_OUT/'history/completion_v1.py')
    parser.add_argument('--preservation-manifest',type=Path)
    args=parser.parse_args();run(args.output,args.legacy_source,args.preservation_manifest)
