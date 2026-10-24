# Step 4: Occlusion-aware 2D branch completion

Implemented linear and least-squares quadratic gap completion in
`src/apple_tree_project/completion.py`, building on Step 3 `pixel_graph`.
Step 3 v4 remains the latest visible annotation source. Its 12 annotations are
AI drafts/pending; this implementation does not change review status or claim
real-tree hidden reconstruction accuracy. No Summer GT, depth, or winter image
is used by either inference method.

## Inputs and eligibility

Supply the native-grid Step 3 binary skeleton, a binary occlusion region mask,
and explicit gap requests, or screen endpoints with `detect_candidate_gaps`.
Branch identity should be assigned from RGB review; the skeleton alone cannot
establish trunk/left/right anatomy or occlusion.
Missing visible annotation is not automatically an occlusion.

Example gap JSON (coordinates illustrative only):

```json
{"gaps": [{"id": "trunk_gap_1", "branch": "trunk", "start": [15,20], "end": [29,20]}]}
```

Allowed identities: `trunk`, `left_primary`, `right_primary`. Each endpoint
must be a degree-one pixel in a different visible component, unused by earlier
accepted requests. At least three local unbranched support points are required;
the default window is eight graph nodes. Chord length must be >1 and <=80 pixels,
and both outward endpoint tangents must face the gap within 65 degrees.
These are configurable geometric heuristics, not biological confidence scores.

All newly rasterized pixels must lie inside the supplied occlusion mask.
Out-of-frame curves, paths that fail to reduce components by exactly one,
or paths that change cycle rank/junction count are rejected. Previously
accepted bridges participate in collision checks. Request order is explicit;
there is no globally optimal selection. No junction
completion, single-ended extrapolation, fine-twig reconstruction or 3D is done.

## Methods

Linear: `P(t) = A + t(B-A)`, 0 <= t <= 1.

Quadratic: `P(t) = A + t(B-A) + t(t-1)C`. Endpoints are exact. Project local
visible support onto the chord to obtain parameters outside [0,1]. Fit the
two-vector C by NumPy least squares to visible support residuals and endpoint
derivative residuals. Each group is normalized by its observation count;
`tangent_weight` (default 1) controls the derivative group. Endpoint tangent
directions come from a least-squares line against local cumulative arc length.
Target derivative magnitudes equal the chord length. Tangents are soft
constraints: a quadratic cannot generally match two arbitrary endpoint
directions exactly. A parametric curve avoids vertical-line singularities.

Samples are spaced at most 0.25 pixels by a derivative bound, rounded to the
native grid and rasterized. The original skeleton is retained unchanged.
Added pixels and all incident graph edges carry `inferred=True`; accepted
records include continuous curves and coefficients. Rejections contain reasons.
An inferred flag means estimated geometry, not verified hidden wood.

## Run and compare

```powershell
$env:PYTHONPATH='src'
python scripts/run_branch_completion.py --skeleton path/to/skeleton.png --occlusion-mask path/to/occlusion.png --gaps path/to/gaps.json --output results/step4_run_01
$env:PYTHONPATH='results/test_dependencies;src'
python -m pytest -q
```

The runner requires a new directory below results or data/processed and writes
both method skeletons, inferred masks, detailed graphs/decisions and a comparison
JSON with acceptance counts and runtime. Use the same requests and parameters
for comparison; inspect rejections as well as accepted cases. No branch width
is inferred: these are centerlines, not completed segmentation masks.

Synthetic tests check straight bridges, analytic curved-gap improvement over
linear interpolation, exact endpoints, rotation invariance, visible geometry
preservation, inference flags, unsupported gaps and crossing rejection.
The analytic comparison is a controlled numerical check, not evidence that
quadratic fitting wins on real trees. Both methods can be wrong under ambiguous
branch identity, noisy tangents, long gaps, S-curves or incorrect occlusion masks.
Independent reviewed real gap identities and held-out hidden references are
still needed for real reconstruction metrics and parameter sensitivity studies.

## 自动候选检测与不确定性

`detect_candidate_gaps` 枚举不同可见分量的端点，按距离、端点朝向、局部切向变化、
主干/两条主枝身份和 Y 树结构筛选。默认主干轴由图像下部 20% 骨架点的横坐标中位数估计，
轴附近为临时 trunk，左右两侧为临时 primary。该模型假设树直立、主干处于画面下方；
身份是几何假设，不能替代 RGB 审核。可通过 `endpoint_roles` 提供已审核身份。
多个空间分离的可见分叉超出主 Y 模型，拒绝补全；补全阶段不允许新增分叉或环。
同一端点有多个兼容对象时全部拒绝，不采用最近邻强行匹配。
默认局部切向变化阈值 45 度；三点局部切向与支持窗口另一端的三点切向比较。
每个候选携带 `occlusion_status=unverified`、身份来源与不确定性说明；
被拒绝者保留距离、方向、局部弯曲等可用数值和拒绝原因。

真实数据专用图库模式把骨架外部视为 **未知区域**，仅渲染候选连接假设。
该模式并未确认遮挡；不能把粉线作为实测枝条或把缺口认定为遮挡。
常规 `complete_gaps` 接口仍要求调用方显式提供遮挡区域。

## 2026-10-24 实验结果

入口：[HTML 图库](../results/step4_occlusion_completion/index.html)，
[逐案例指标](../results/step4_occlusion_completion/synthetic_metrics.json)，
[敏感性图](../results/step4_occlusion_completion/sensitivity.png)，
[敏感性表及配对比较](../results/step4_occlusion_completion/sensitivity.json)。

构造已知干净真值的参数化 Y 树，对主干、左主枝、右主枝分别施加受控方形遮挡。
在施加遮挡前按 Step 3 细化，消除栅格化分叉处的 2×2 像素环。
真值只用于生成实验及评估，不传入候选检测或补全接口。
固定随机种子 42，噪声为平滑横向像素位移，非真实传感器噪声模型。
六组单因素扫描，每组五个值、每值三个枝条角色，共每方法 90 个设置。
基础设置会重复出现；这些不是 90 个独立随机树样本，不能作统计显著性推断。

| 合成评估 | 直线法 | 二次曲线法 |
|---|---:|---:|
| 接受并连通案例 / 90 | 63 | 67 |
| 各自接受案例的平均对称 Chamfer 误差，px | 0.373 | 0.480 |
| 所有设置的隐藏中心线 2px 召回率，拒绝计 0 | 0.674 | 0.735 |
| 接受案例的平均切向误差，度 | 7.983 | 3.918 |
| 错误枝条身份连接数 | 0 | 0 |
| 平均耗时，ms | 3.33 | 3.40 |

二者共同接受的 63 个设置中，直线/二次的 Chamfer 误差为 **0.373/0.485 px**，
切向误差 **7.983/3.929 度**，2px 召回率 **0.963/0.987**。
因此不能宣称二次法在总体几何误差上更优；它在本实验中改善了切向一致性和容差召回。
所有接受案例端点拟合误差均为 0、可见骨架保持不变、补全后连通且未新增环。
错误连接计数按已知合成角色检查，另报告偏离隐藏真值超过 3px 的新增像素数及比例；
0 次错误身份连接不代表不存在几何误差，也不证明复杂场景中的错误连接率为 0。
歧义诱饵、多余穿越结构、无显式遮挡支持等负例另由单元测试覆盖。

Chamfer 为新增像素与隐藏真值像素之间双向最近距离均值的平均；
无补全时误差记 null，不以 0 伪装正确。2px 召回分母是隐藏真值像素。
切向误差将拟合曲线端点导数与原始可见骨架八节点窗口估计方向比较；
它衡量可见端点的一致性，不等同于对隐藏真实切向的误差。
运行时间为三次补全调用耗时中位数再跨设置取均值，包含图构建，
不含检测、输入输出、绘图；未预热，仅作为本机描述性结果。

敏感性扫描：遮挡方形边长 8/16/24/40/64 px（并非实际曲线弧长）、
方向阈值 20/35/50/65/80 度、噪声幅度 0/0.5/1/2/4 px、
切向权重 0.1/0.5/1/4/10、支持点数 3/5/8/12/16、局部弯曲阈值 10/25/45/70/100 度。

- 遮挡边长 64px 时，二者均只接受三角色中的一个；该设置平均召回直线 0.041、二次 0.330。
- 噪声幅度 4px 时平均召回直线 0.639、二次 0.751；拒绝率受栅格边界影响并非单调。
- 支持点数 5 或 12 时二次法接受三角色全部案例；其他扫描值接受两个。不可据三个角色选定最优参数。
- 增大切向权重降低端点切向残差，但不保证几何误差下降。
- 本组基础场景对 20–80 度方向阈值及 10–100 度弯曲阈值没有响应；阈值均未成为限制因素，不能据此证明对方向/曲率鲁棒。
- 严格遮挡区域检查会拒绝部分仅偏出边界一个栅格像素的路径；这是已记录的保守性限制，未扩大区域以提高接受率。

12/12 个 Step 3 v4 真实 RGB 草稿均生成四联图及候选/拒绝记录。
两方法分别在 R06N02、R08N02、R09N02、R10N02 各保留一条几何假设，其余样本不强连。
青色为原始可见骨架，粉色为待核实的推断；原始 RGB 与输入骨架哈希及修改时间保持不变。
所有草稿继续为 pending，真实样本不计算准确率；没有读取 Summer whole GT、深度或冬季图。

复现完整图库需要可选绘图库 matplotlib（仅评估脚本需要）：

```powershell
$env:PYTHONPATH='src'
python scripts/evaluate_step4.py --output results/step4_occlusion_completion_new
```

完整测试结果：**79 passed**。覆盖原 63 项及新增 16 项，含候选检测、歧义拒绝、
曲率筛选、两种算法、已知真值 Y 树、推断标签、源骨架保持、穿越拒绝和 CLI 产物/覆盖保护。
未执行提交或推送；未生成相机标定或三维重建。
