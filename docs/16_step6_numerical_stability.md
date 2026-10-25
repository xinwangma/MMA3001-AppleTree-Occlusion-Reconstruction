# Step 6 v2：角阈值数值稳定性与重新验证

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

共审计234图，其中4图相对v1变化，230图保留。详情见graph_policy_audit.csv；v1在原算法源码下重放，v2在当前策略下重放；节点身份、像素、边、状态精确，几何使用atol=1e-12、rtol=1e-10。

所有新图还分别在角判据加/减1e-12度的受控扰动下检查，模拟已报告舍入尺度；这些是单环境故障注入，不是声称已在第二台机器或另一操作系统运行。未证明所有BLAS版本/任意病态支持点都逐位一致。

## holdout_19 专项

原观测mask有189个像素，原流程的thin_visible预处理后187个节点。复核必须保留这一步，不能把直接在原观测mask上建图的189节点结果与保存图比较。

| simulated_boundary_angle_deg | method | v1_nodes | v2_nodes | v1_inferred | v2_inferred | v2_accepted |
|---|---|---|---|---|---|---|
| 45 | visible_only | 187 | 187 | 0 | 0 | 0 |
| 45 | linear | 203 | 187 | 16 | 0 | 0 |
| 45 | quadratic | 203 | 187 | 16 | 0 | 0 |
| 45 | visible_only | 187 | 187 | 0 | 0 | 0 |
| 45 | linear | 203 | 187 | 16 | 0 | 0 |
| 45 | quadratic | 203 | 187 | 16 | 0 | 0 |
| 45 | visible_only | 187 | 187 | 0 | 0 | 0 |
| 45 | linear | 187 | 187 | 0 | 0 | 0 |
| 45 | quadratic | 187 | 187 | 0 | 0 | 0 |

原v1在本机已拒绝holdout_19，所以此例本机最终图可以不变；但v2明确拒绝两侧舍入值，不能据单例未变推断整个比较指标不变。

## 独立48配置：v1/v2对照

所有误差为各案例指标均值，RMSE以有支持点条件化，方法点数可能不同，不能孤立排序；Chamfer与覆盖使用每例固定参考。3D单位米，2D单位像素。新增隐藏中心线召回与完整预测的边缘邻域召回分开。

| method | accepted_cases_v1 | accepted_cases_v2 | mean_full_chamfer_px_v1 | mean_full_chamfer_px_v2 | mean_hidden_added_recall_2px_v1 | mean_hidden_added_recall_2px_v2 | mean_rmse_3d_m_v1 | mean_rmse_3d_m_v2 | mean_chamfer_3d_m_v1 | mean_chamfer_3d_m_v2 | mean_coverage_3cm_v1 | mean_coverage_3cm_v2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| visible_only | 0 | 0 | 1.71092 | 1.71092 | 0 | 0 | 0.0148606 | 0.0148606 | 0.0465991 | 0.0465991 | 0.771759 | 0.771759 |
| linear | 7 | 5 | 1.64084 | 1.67389 | 0.122168 | 0.0970395 | 0.0160697 | 0.0150518 | 0.0451443 | 0.045866 | 0.784401 | 0.780945 |
| quadratic | 7 | 5 | 1.62826 | 1.67388 | 0.126176 | 0.0986842 | 0.0157002 | 0.0150969 | 0.0448874 | 0.0458793 | 0.784371 | 0.779943 |

完整对照包含目标诊断和各接受子集，见comparison_metrics_v1_v2.csv。边界策略可能降低补全接受率和覆盖；这是明确数值政策的代价，不修改阈值把分数调回原结果。全案例和配对/各自接受子集必须分别解读。

## 真实数据与局限

12个真实样本重新评估候选/补全决策，仅为640x480图像像素示意；所有标注仍AI DRAFT/pending，未确认遮挡、未使用Summer GT计算精度，也没有真实米制3D。R06N02/R08N02/R09N02/R10N02继续要求独立人工复核。真实候选也可能因同一边界政策被拒绝，旧示意仍在v1保留。
本次数值修复不能认证树体身份、隐藏枝条真实性或真实深度标定。最终提交只能准确声明“校准合成验证与真实定性草稿”；若课程要求可靠真实米制3D，此项仍未满足。没有自动标记所有工程要求完成。

## 验证与复现

{"tests": 160, "failures": 0, "errors": 0, "skipped": 0, "passed": 160}

完整pytest、保存结果重放、Step5原15图重放、HTML/PNG检查、git diff --check及原数据/全部历史结果SHA256/大小/mtime检查见verification/与tests/。旧源代码和旧文档快照见history/。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python scripts/replay_step6_saved.py --results results/step6_final_validation_v2_boundary_policy
python scripts/evaluate_step6_boundary_policy.py --output results/step6_boundary_another_run
```

完整评估命令必须使用新目录，并需要保留的v1输入和旧源码history；解压后的project/可以用 `python scripts/replay_step6_saved.py --results ../results` 独立重放234个v2图，不需原始RGB-D。测试使用仅包含合成观测的holdout_19回归fixture，不读GT推断。
不提交/推送Git，不开始Step7。
