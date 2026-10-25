# Step 6：最终验证、算法比较与性能优化

范围仅为 Y 树主干与两条主枝。三方法：visible-only、linear、quadratic least-squares。
本次不开始 Step 7、不提交或推送 Git。原 Step 3–5 数值算法完全保留。

## 实验依据与独立性

复用 Step 4 的 180 行（每补全方法 90 设置）和 Step 5 的 150 行深度/标定敏感性结果；独立重新汇总原 JSON，核对旧 summary。
从 Step 5 保存的 15 个图重新计算 3D RMSE、Chamfer、覆盖率；仅 9 个主要方法/场景组合用于三方法集成比较，另外 6 个 measured-only 版本单独保留。
未重新运行原有完整参数扫描。旧速度记录保留原测量范围，不冒充新端到端速度。

旧扫描反复使用少量树形，Step 5 仅三固定场景，无法支持对树形变化的泛化结论。
因此在运行前保存 frozen_experiment_plan.json：48 个新配置（种子 60261025..60261072），固定参数不调优；另有 20 个三维遮挡长度、10 个真实曲率系数诊断配置。
它们不参与方法/阈值调参。48 个配置是同一生成器的新配置，**不是 48 个真实树或统计独立的物理观测**。
树枝角度 25–60 度（相对竖直），三维曲率/姿态随机变化；遮挡位置 t=.22/.45/.72/.9、方形宽10/20/32/48px、主干/左右枝，四种 Z profile；
空间观测噪声0/.35/.8/1.5px、可见深度噪声0/.003/.015m。随机种子独立于旧实验，分组并非全因子设计，不能把因素混合作为单因素效应。
新补全使用原默认 max_gap=80px、angle=65deg、curvature screening=45deg、support=8、tangent_weight=1，未用结果选择参数。
所有新场景的输入、参考、标定与三个输出图均保存，拒绝案例不移除。

## 2D 与 3D 指标及分母

2D 全骨架对称 Chamfer 是预测点与干净栅格参考点双向最近**欧氏距离均值的平均**，单位 px；三方法在同一案例上可比较。
inferred Chamfer 只比较新增点与隐藏参考，未补全时 null。hidden_added_recall_2px 分母是 truth AND occlusion 的固定像素集合；无新增点为0。
另报告使用完整预测（包括可见端点邻域）的 hidden_full_recall_2px，不把它与新增补全召回混用。

3D 坐标为已知合成相机米制，X右/Y下/Z前。原解析三维曲线先投影/栅格化，生成器只将模拟可见深度提供给算法。
RMSE 使用每个有支持预测点到**投影2D最近解析采样点**的3D误差，不是3D最近邻RMSE，包含栅格量化及观测噪声。
3D Chamfer 是有支持预测点与逐栅格参考3D点的双向未平方距离均值平均；coverage 是参考点距预测<=.03m比例。
每例原始行保留预测/参考/隐藏/支持点数，缺失点不作零误差。RMSE对有支持点条件化，方法间点数不同；同时比较 measured RMSE、固定参考 Chamfer/coverage。
聚合为各案例指标的算术均值，不是把不同大小案例混池后算RMSE。每个聚合指标的有效案例数 n_* 明列。

all_cases 使用同一全部案例；own_accepted_cases 使用各自接受集合，因此**不能直接将两个各自接受均值作优劣结论**；
paired_both_completion_accepted 用二者共同接受的同一 case_id 子集，并保留该子集上的 visible-only。
baseline 不尝试补全，acceptance=N/A，而不是失败率100%。候选拒绝的分母是端点对，补全拒绝的分母是请求，案例未补全的分母是场景，三者分别报告。
incorrect_connections 用生成器真实枝条标签判定接受连接两端是否跨角色；incorrect_role_labels另计声明角色错误。
环秩 E-V+C 和分量验证图一致性，不等价于解剖学正确性。

## 独立48配置：全案例比较

| method | cases | accepted_cases | mean_full_chamfer_px | mean_hidden_added_recall_2px | mean_rmse_3d_m | mean_chamfer_3d_m | mean_coverage_3cm | mean_components_3d |
|---|---|---|---|---|---|---|---|---|
| visible_only | 48 | 0 | 1.71092 | 0 | 0.0148606 | 0.0465991 | 0.771759 | 1.83333 |
| linear | 48 | 7 | 1.64084 | 0.122168 | 0.0160697 | 0.0451443 | 0.784401 | 1.6875 |
| quadratic | 48 | 7 | 1.62826 | 0.126176 | 0.0157002 | 0.0448874 | 0.784371 | 1.6875 |

## 同时接受的配对集合

| method | cases | accepted_cases | mean_full_chamfer_px | mean_hidden_added_recall_2px | mean_rmse_3d_m | mean_chamfer_3d_m | mean_coverage_3cm | mean_components_3d |
|---|---|---|---|---|---|---|---|---|
| visible_only | 7 | 0 | 1.02349 | 0 | 0.0116433 | 0.0275693 | 0.816636 | 2.28571 |
| linear | 7 | 7 | 0.542955 | 0.837726 | 0.0199346 | 0.0175941 | 0.903326 | 1.28571 |
| quadratic | 7 | 7 | 0.456664 | 0.865204 | 0.0174007 | 0.0158324 | 0.90312 | 1.28571 |

## 各自接受集合（分母不同，仅描述）

| method | cases | accepted_cases | mean_full_chamfer_px | mean_hidden_added_recall_2px | mean_rmse_3d_m | mean_chamfer_3d_m | mean_coverage_3cm | mean_components_3d |
|---|---|---|---|---|---|---|---|---|
| visible_only | 0 | 0 | None | None | None | None | None | None |
| linear | 7 | 7 | 0.542955 | 0.837726 | 0.0199346 | 0.0175941 | 0.903326 | 1.28571 |
| quadratic | 7 | 7 | 0.456664 | 0.865204 | 0.0174007 | 0.0158324 | 0.90312 | 1.28571 |

## 负例、失败及工程限制

8 种负例 x 两补全方法，包括无遮挡证据、穿越其他结构、歧义对象、未知角色、超长缺口、错误方向、外国树体对齐片段、深度锚点缺失。
negative_cases.* 保存输入决策及输出，failure_cases.* 包含未补全、低覆盖、错误连接及三维链拒绝案例。
其他树体负例故意提供错误角色声明和可通行区域；几何方法可能连接两棵树的对齐碎片。这是明确的输入真实性/木质身份限制，不能从零环/连通成功推出语义正确。
缺深度锚点可使2D补全成功但隐藏3D仍 unsupported。靠近分叉的遮挡、长缺口、高曲率/噪声会出现检测或显式区域支持拒绝；保守拒绝不是完美重建。
负例不能作为自然果园错误率的估计，正常合成场景的正确连接计数也不能排除真实错误。

## 敏感性与鲁棒性

Step 4 复用方向阈值、支持点数、切向权重、局部切向变化筛选阈值、2D噪声和遮挡宽度扫描。
旧 max_curvature_deg 是**筛选阈值**，不是实际树枝曲率，所以另补三维多项式曲率系数 -.8/-.4/0/.4/.8m、两个枝条角色，共10个目标诊断。
三维遮挡宽度8/16/24/40/64px，两个角色 x 线性/非线性深度，共20个目标诊断，补齐 Step 5 缺少的3D遮挡长度证据。
方形宽度不等于隐藏曲线弧长。现有深度噪声、丢深度、焦距/主点/尺度误差150行仅在旧 varying_z 场景上，联合误差和真实相机误差分布仍未验证。
深度缺失时条件RMSE可很低而覆盖下降、分量上升；必须联合读图。不同单位因素的扫描范围不同，不能据最大值排行推导一般“显著性”。没有进行统计显著性或真实相机不确定性推断。

## 性能与有证据的优化

计时为 perf_counter_ns，预热3次、重复15次；记录每次样本、中位数、p90和最小值。两种合成输入分辨率192x192、640x480。
阶段包括细化、像素图、候选、两种补全、向量反投影、三种完整 lifting，以及每方法 mask+合成depth→3D图的计算流程。
该“计算流程”不包括RGB分割（项目没有自动分割器）、人工标注、校准、读写、绘图和评估；不是原始RGB到机器人模型的端到端系统。
计时与 tracemalloc 单次峰值分开运行；峰值仅为追踪分配，不是总RSS或所有原生库内存。CPU/Python/依赖信息见 performance/environment.json。

| width | height | stage | median_ms | p90_ms | traced_peak_bytes |
|---|---|---|---|---|---|
| 192 | 192 | skeleton_extraction | 6.1286 | 6.91568 | 1730281 |
| 192 | 192 | pixel_graph | 0.3739 | 0.48572 | 509738 |
| 192 | 192 | candidate_detection | 0.5322 | 0.73732 | 546930 |
| 192 | 192 | linear_completion | 0.9707 | 1.35394 | 714034 |
| 192 | 192 | quadratic_completion | 0.9944 | 1.08618 | 714034 |
| 192 | 192 | vector_backprojection_only | 0.0276 | 0.03022 | 20868 |
| 192 | 192 | visible_only_3d_lifting | 4.5176 | 5.37694 | 509858 |
| 192 | 192 | visible_only_mask_to_3d_pipeline | 11.7508 | 12.2442 | 1730281 |
| 192 | 192 | linear_3d_lifting | 4.8438 | 5.7929 | 509858 |
| 192 | 192 | linear_mask_to_3d_pipeline | 12.9814 | 14.068 | 1730281 |
| 192 | 192 | quadratic_3d_lifting | 4.6765 | 6.25426 | 509858 |
| 192 | 192 | quadratic_mask_to_3d_pipeline | 12.7075 | 14.6285 | 1730281 |
| 640 | 480 | skeleton_extraction | 84.4525 | 87.2937 | 13896826 |
| 640 | 480 | pixel_graph | 2.7312 | 3.02482 | 3994922 |
| 640 | 480 | candidate_detection | 4.9873 | 5.35416 | 4302450 |
| 640 | 480 | linear_completion | 9.1086 | 10.5779 | 5484642 |
| 640 | 480 | quadratic_completion | 9.6704 | 10.2017 | 5484642 |
| 640 | 480 | vector_backprojection_only | 0.0385 | 0.0432 | 67722 |
| 640 | 480 | visible_only_3d_lifting | 17.8003 | 21.8534 | 3995042 |
| 640 | 480 | visible_only_mask_to_3d_pipeline | 104.168 | 108.969 | 13896826 |
| 640 | 480 | linear_3d_lifting | 19.6487 | 23.7181 | 3995042 |
| 640 | 480 | linear_mask_to_3d_pipeline | 121.127 | 124.821 | 13896826 |
| 640 | 480 | quadratic_3d_lifting | 19.3898 | 22.6016 | 3995042 |
| 640 | 480 | quadratic_mask_to_3d_pipeline | 119.116 | 124.664 | 13896826 |

原比较流程三次调用各自细化、两次调用相同候选检测。共享这些只读中间量是比较工作流优化，不改变任何阈值、拟合、像素图、补全或三维算法。
原 infer_one 仍保留作基线；infer_all 分享细化和检测。先记录原流程各阶段成本，再验证相同输入上三方法输出一致，按交替顺序做15对 before/after。
该速度收益只适用于一次比较三方法；不能声称单方法核心算法被加速，也没有实现自适应选择器或调参取胜。

| width | height | before_median_ms | after_median_ms | speedup | reduction_fraction | equivalence_verified |
|---|---|---|---|---|---|---|
| 192 | 192 | 36.119 | 23.4825 | 1.53812 | 0.349857 | True |
| 640 | 480 | 339.388 | 161.088 | 2.10684 | 0.525356 | True |

最大单阶段耗时（不包括复合流程，属于本基准而非一般结论）：

| width | height | stage | median_ms |
|---|---|---|---|
| 192 | 192 | skeleton_extraction | 6.1286 |
| 640 | 480 | skeleton_extraction | 84.4525 |

共享工作流相对原始逐方法流程的回归验证还覆盖全部78配置/234个图：读取保存的可见深度/掩膜/遮挡输入，以原逐方法 infer_one 重放；不调用模拟器，也不读取NPZ中的真值数组，精确检查结构/状态并按Step5容差检查几何。结果见 verification/saved_observation_replay.json。

## 真实12样本：只做定性复核

复用 Step 3 v4 可见草稿与 Step 4 两方法图，逐样本核验RGB哈希、重新检查候选决策及补全图一致性。
图示只有原生640x480像素坐标，非米制三维。所有12标注保持 AI DRAFT/pending，human accepted=0。
R06N02、R08N02、R09N02、R10N02 在表格/图库显式标为 independent manual review required。
R06的短刺/嫁接区、R08新增碎片、R09线材附近枝条、R10近端片段需人在RGB中确认；脚本不修改或批准标注。
没有将未标区域称为确认遮挡，没有使用未核验 Summer GT 对齐或真实3D准确率。因为再分发许可未核实，ZIP和图库不复制原始RGB/深度，仅包含骨架示意及来源/哈希。
木质表面、中轴及叶片/邻树身份仍是实际工程障碍。

## 最终方法选择与工程意义

不宣称普适胜者：visible-only 是保守的可观测参考和无法确认缺口时的回退；linear 简单透明，适合近直线连接假设；quadratic 能表示弯曲并提供软切向一致性，但可能离开受控区域或拟合错误局部方向。
是否改善必须根据上面的同分母配对结果；更高覆盖率可能伴随更大条件误差。不能为了降低误差而删去拒绝案例。
建议交付保留三方法及显式接受/拒绝记录，以 quadratic 作为需要曲率假设时的候选、linear 作为简单基线；未经人工确认的真实缺口不自动补全成事实。没有实现未验证的自动方法选择。
同案例同时接受集合的逐例优胜计数（无统计显著性声明）：

| metric | paired_cases | quadratic_better | linear_better | tied |
|---|---|---|---|---|
| full_chamfer_px | 7 | 3 | 1 | 3 |
| chamfer_3d_m | 7 | 2 | 2 | 3 |
| hidden_added_recall_2px | 7 | 2 | 0 | 5 |

工程上关键是“改善可解释的补全完整度并能拒绝不支持输入”，不是漂亮的连续图；没有真实校准不能用于毫米定位或机器人避障。

## 复现与验证

从仓库根：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python scripts/evaluate_step6.py --output results/step6_another_run
```

必须使用不存在的新 results 子目录。默认完整运行含所有生成、计时、复核、完整pytest、文档及包创建；若自定义输出，ZIP使用相应输出名加 _review_package.zip。
依赖为 pyproject.toml 的 numpy/Pillow，以及 study matplotlib 和 dev pytest；复用来源路径需存在，不包含在原始数据之外的假造备选值。
tests/ 的新单元测试覆盖距离定义、空预测、分母/配对、共享流程等价、负例、推断接口不接收真值及输出保护。
完整测试日志、JUnit、源码/结果保护清单、PNG和HTML链接检查、git diff --check、ZIP CRC与SHA256验证均保存在本次结果及ZIP旁的完整性记录。
独立重放：`python scripts/replay_step6_saved.py --results results/step6_final_validation`；在解压后的 project/ 运行时改用 `--results ../results`，无需原数据或旧结果。
真实度量校准缺口与 Step 5 最终文档一致；Step 6不修复深度解码或标注真实性。

## 本次完整测试

{"tests": 139, "failures": 0, "errors": 0, "skipped": 0, "passed": 139}


## 中断恢复后的最终验证

# Step 6 最终恢复与验证补充

恢复时确认原归档命令未执行、case_id/cohort修正尚未安装；只恢复系统临时目录中的修正，原地继续10个已存在的Step 6文件。没有执行任何结果目录的移动、删除或覆盖。
原冻结计划、复用表、初始保护清单保持不变。48个独立配置、30个目标配置、16个负例方法记录、12个真实草稿比较以及分阶段性能测量均已完成。

首次完成分析后的139项测试全部通过；其后只修复Windows ZIP写入句柄内读取导致的路径分隔符校验问题，并新增ZIP完整性回归测试。最终测试结果如下（旧139项日志仍保留）：

{"tests": 140, "failures": 0, "errors": 0, "skipped": 0, "passed": 140}

独立源码快照完整测试同样通过；Step 5原有15图重新重放通过；Step 6全部234图已从保存的visible/depth/occlusion输入使用原始逐方法流程重放通过，未调用模拟器或读取GT数组，最大浮点差0。

独立48例，两补全方法各接受7例、41例无补全；所有48例留在统计中。7例配对集合中linear/quadratic的全2D Chamfer为0.542955/0.456664px，新增隐藏中心线2px召回为0.837726/0.865204；不能将此接受子集结果当作48例或真实精度。
两方法在holdout_15、holdout_39均出现跨参考枝条角色连接标记，两者均涉及靠近Y结点的主干遮挡（t=.9）。这是按最近投影解析枝条角色的评价标记，需要检查隐藏结点/分叉身份；不得将“连通”视为正确解剖重建。补充图由保存的预测重绘，未重新推断或调参。
负例foreign_aligned_fragment中，两种方法都接受了来自不同树体的对齐碎片连接：错误/未核实身份输入无法靠当前几何规则认证。这不是自然场景错误率估计。

共享预处理只优化一次同时比较三方法的工作流，不改变Step 3–5算法：

| width | height | before_median_ms | after_median_ms | speedup | reduction_fraction |
|---|---|---|---|---|---|
| 192 | 192 | 36.119 | 23.4825 | 1.53812 | 0.349857 |
| 640 | 480 | 339.388 | 161.088 | 2.10684 | 0.525356 |

真实12样本仍AI DRAFT/pending，R06N02/R08N02/R09N02/R10N02明确待独立人工复核；没有确认真实遮挡或度量3D。校准与真实GT限制仍存在。

未完成的旧ZIP保留为results/step6_review_package_incomplete_20261025.zip；最终包使用原要求的step6_review_package.zip。最终校验以SHA256SUMS_final.txt、ZIP_MEMBER_SHA256.json及ZIP外部integrity.json为准；早期SHA256SUMS.txt作为中断打包记录保留（当时控制台日志仍在写入）。

没有重跑已完成的合成实验或性能计时；没有修改Step 3–5算法、原始数据或之前实验结果，没有开始Step 7，没有提交/推送Git。


## 最终性能解释审计

# 性能解释审计：空请求与成功补全必须分开

最终检查确认，原192×192与640×480性能场景均检测到0个候选缺口。因此原stage_runtime中的linear_completion、quadratic_completion计时只覆盖空请求路径，未执行成功连接的拟合/栅格化/拓扑检查，不能解释为成功拟合成本。对应mask-to-3D流程和共享预处理加速比也只代表这些无候选输入；不能外推到成功补全或真实RGB系统。
原计时真实有效且完整保留，没有重测或覆盖。另仅补充一个已有Step 5 varying_z可见骨架及其显式候选请求，原默认补全参数不变，两方法确实接受缺口。此微基准不包含候选检测、lifting、I/O或绘图，不用于调参或新的准确率声明。

成功补全微基准（预热3次、重复15次、perf_counter_ns；内存另一次tracemalloc）：

| method | width | height | supplied_requests | accepted_requests | inferred_pixels | median_ms | p90_ms | traced_peak_bytes |
|---|---|---|---|---|---|---|---|---|
| linear | 192 | 192 | 1 | 1 | 28 | 2.5665 | 2.70526 | 1028501 |
| quadratic | 192 | 192 | 1 | 1 | 27 | 2.8463 | 3.13942 | 1029419 |

来源和每次测量值在positive_successful/中；这只是一个已知可接受场景，不是跨全部树形的平均性能。原共享流程的35.0%/52.5%时间减少仍成立，但仅限所记录的三方法无候选比较工作流。

复现只补这一项，使用新目录：

```powershell
$env:PYTHONPATH='src'
python scripts/evaluate_step6.py --positive-completion-benchmark --output results/step6_positive_timing_new
```

独立合成评估、拒绝/失败计数、234图重放和旧性能数值均未改变，未修改Step 3–5算法。

最终完整测试与源码快照：{"tests": 141, "failures": 0, "errors": 0, "skipped": 0, "passed": 141}。


## Step 6 v2 数值边界策略（最新结论）

原表格是v1历史。当前版本采用阈值±1e-5度保守拒绝带；全234图重放、指标变更和提交范围见[数值稳定性报告](16_step6_numerical_stability.md)，图库位于results/step6_final_validation_v2_boundary_policy/index.html。完整测试：{"tests": 160, "failures": 0, "errors": 0, "skipped": 0, "passed": 160}。
