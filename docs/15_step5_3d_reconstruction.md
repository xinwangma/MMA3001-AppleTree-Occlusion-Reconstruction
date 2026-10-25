# Step 5：深度辅助三维苹果树骨架重建

本阶段实现显式标定条件下的相机坐标反投影、已知相机的合成三维验证，
并对真实数据提供非米制展示。真实数据的米制三维重建仍不受现有证据支持。
Step 3/4 算法和已提交的 Step 4 结果不修改；不执行 Step 5 提交或推送。

## A. 标定与深度调查

本地先读 `docs/09_real_dataset_inspection.md`、`docs/10_annotation_alignment.md`、
`docs/13_step3_annotation_revision.md`、`docs/14_step4_branch_completion.md`、
数据清单、标定演示文件及实现。`data/demo/calibration.json` 是人为构造的演示参数，
**不能用于真实 Monash 数据**。

再次只读检查实际深度 PNG 的维度、容器、通道关系、像素范围、零值占比和元数据。
零值仅作为存储值计数，不假定其含义是无效深度。
下列公开一手来源已查阅，访问日期 2026-10-25（Australia/Sydney）：

- [Monash 2022 数据集页](https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction)：介绍 RGB-D 和标签类型，未在该页面提供数值标定或深度传递函数。
- [Monash HOB-CNNv2 数据集页](https://www.monash.edu/engineering/lmga/news/y-shaped-apple-tree-public-dataset-for-hob-cnnv2)：指向另一下载链接和作者代码，未在该页面提供可用于本地数据的标定。
- [作者 HOBCNN-v2 仓库 README](https://github.com/ZijueChen/HOBCNN-v2)：说明二维枝条预测与安装，未给出本地深度图解码/内参。
- [HOB-CNNv2 论文可访问摘要/预览](https://www.sciencedirect.com/science/article/pii/S0168169924001182)：说明二维预测与季节配对；所查阅部分没有可用标定。没有将未读取的全文或远程压缩包当作已审计材料。

公开 2022 页描述的数量/季节与本地文件分布不同，不能建立精确版本映射。
未发现标定不等于证明作者没有标定；未联系作者、未下载另一个完整数据包。

| 项目 | 证据状态 |
|---|---|
| 存储深度形式 | 本地 PNG 为 RGB uint8，三个通道相同，640×480；复核结果见 JSON |
| RGB/深度配对 | 文件名和尺寸支持名义配对，不证明逐像素配准 |
| 深度尺度/偏置/传递函数 | 未解决；不能把 uint8 数值直接当作毫米、米或线性距离 |
| 轴向 Z / 欧氏距离 range | 未解决 |
| 0 或其他无效代码 | 未解决 |
| 相机内参、畸变、外参、配准 | 未解决；相同分辨率不等于已配准 |
| 独立真实三维参考 | 未提供 |

结论：不对真实数据输出米制物理坐标，也不从相机型号/FOV猜测内参。
真实米制重建的解锁条件包括：可靠标量深度解码、单位与无效值约定、对应分辨率下的
内参和畸变处理、RGB/深度空间注册证明，以及可见木质身份/深度归属复核。

## B. 实现及状态约束

`src/apple_tree_project/reconstruction3d.py`：

- `Calibration` 要求显式 `width,height,fx,fy,cx,cy,depth_unit_to_m,depth_kind,invalid_values,registered_to_skeleton,rectified,evidence`。
  可选 `depth_offset_m` 默认 0。调用者声明及证据字符串不会自动证明校准真实有效。
- `backproject` 使用标量解码 `d_m = raw*scale+offset`。对轴向深度，
  `XYZ = ((u-cx)/fx,(v-cy)/fy,1)*Z`；对欧氏 range，先将射线归一化再乘 range。
  非线性/伪彩色编码必须先用独立验证的外部解码器处理。RGB 深度容器不被自动转灰度后当作米。
- 像素索引是像素中心；相机坐标 X 向右，Y 向下，Z 向前。坐标以米为单位，
  不是世界坐标。实现不估计相机姿态，不自动缩放、配准或去畸变。
- 不修改输入骨架、节点、边、深度或支持掩膜。保持全部二维节点/边和推断标记。
  深度及支持区域必须在同一明确标定网格。

三维状态：

| `status_3d` | 含义 |
|---|---|
| measured | 原始可见节点、显式木质深度支持、有效标量深度及已声明注册/标定同时成立 |
| inferred | Step 4 推断链，两个端点都有 measured 深度，通过显式深度插值假设获得 |
| unsupported | 缺失/无效深度、没有木质支持、隐藏深度未授权或锚点/拓扑不满足；`xyz_m=null` |

可见中心线像素的深度是可见表面代理，并不直接测量木质中轴或枝条半径。
**隐藏节点永不读取该像素深度值**，即便它是有效非零的叶片/背景深度。
默认关闭隐藏深度推断；显式启用后，只允许内部度数为 2、恰好两个 measured 边界的
简单推断链。按图像骨架累积弧长线性插值端点轴向 Z，再沿相应相机射线放置。
默认端点 Z 跳变上限 0.5m；缺锚点、跳变或分叉保持 unsupported，并给出原因。
不是对真实隐藏深度的观测；无法恢复真实非线性深度、分叉遮挡或全隐枝条。
该阈值是合成实验工程参数，不声称适用于实际果园。

边也标记 measured/inferred/unsupported，只有两端有坐标才记录 `length_m`。
另计算受支持三维子图连通分量，避免将二维连通当成三维已恢复。

`scripts/run_3d_reconstruction.py` 提供显式文件输入 CLI，支持 Step 3 graph.json
或 Step 4 completion.json，输出 graph3d.json 和 points.csv。输出必须是 results/
或 data/processed/ 下的新目录。示例（参数必须来自可信标定，不能使用真实数据的猜测值）：

```powershell
$env:PYTHONPATH='src'
python scripts/run_3d_reconstruction.py --graph graph.json --depth registered_scalar_depth.png --calibration verified_calibration.json --support verified_visible_branch_support.png --output results/calibrated_run_new
# 若研究假设允许，可显式追加 --infer-hidden-depth；结果仍标为 inferred。
```

## C. 合成评估与真实非米制展示

`scripts/evaluate_step5.py` 先构造解析三维主干与两主枝，再用已知相机投影，
经栅格化和 Step 3 细化构成可见骨架；已知方形遮挡截断左主枝。
三类三维参考为恒定 Z、变化 Z、曲面深度弯曲；只在评估端使用完整参考。
相机为人为规定的合成参数：192×192，fx=fy=140px，cx=cy=96px，轴向深度米制。
这套相机与实际 Monash 数据无关。遮挡图中放入 0.4m 前景值，验证它不会被赋给隐藏枝条。

比较 visible-only、Step 4 linear、Step 4 quadratic，后两者分别关闭/开启隐藏 Z 推断。
保存标定、输入深度 NPY、可见/遮挡/完整参考掩膜、解析参考点、二维候选决策、
三维节点/状态、静态三维图及 JSON/CSV 指标。
RMSE 的对应关系取最近的投影解析采样点，包含栅格量化误差；
另报告三维参考点 3cm 覆盖率、支持比例、measured/inferred 分开误差、连通分量、环秩及边长。
条件 RMSE 不掩盖缺失节点，不把 unsupported 当作零误差。
三维参考是理想中心线，合成表面/中轴一致的理想化设定不能代表真实表面误差。

单因素扫描深度噪声、焦距误差、主点误差、尺度误差和深度丢失，三随机种子。
运行时间为三次 lift 调用的中位数，不含二维补全、I/O和绘图，无预热；
确定性标定设置重复种子不是独立树样本。对 RMSE 必须同时检查覆盖和拒绝信息。

12 个真实草稿的 linear/quadratic 结果仅作 **non-metric image/code relief**：
显示坐标为 `(u/(W-1),1-v/(H-1),stored_code/255)`，第三轴只是存储灰度编码，
**不代表物理深度、大小或真实形状**。采样是名义同像素关联，并未验证 RGB-depth 注册。
隐藏推断仅放在显示平面上，不读隐藏像素深度码，不与未知灰度高度强行连接。
每个真实节点 `xyz_m=null,status_3d=unsupported`，不宣称任何真实 measured 三维点。
草稿仍是 AI / pending；可见骨架位置和深度归属本身也未获独立验证。

复现（依赖 NumPy、Pillow，绘图使用已有可选 matplotlib）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python scripts/evaluate_step5.py --output results/step5_3d_reconstruction
$env:PYTHONPATH='results/test_dependencies;src'
python -m pytest -v -p no:cacheprovider
```

所有输入原始数据和既有 results 文件在执行前建立 SHA-256/大小/修改时间清单，
执行后重新核验；新实验输出位于全新目录，不覆盖 Step 4 或原始数据。
本报告后续附加本次实测统计、图库及完整测试结果。

## 本次执行结果

[HTML 主图库](../results/step5_3d_reconstruction/index.html) · [覆盖/连通性补充图](../results/step5_3d_reconstruction/evaluation_notes.html) · [深度调查 JSON](../results/step5_3d_reconstruction/calibration/depth_investigation.json) · [三维指标 CSV](../results/step5_3d_reconstruction/synthetic_metrics.csv) · [敏感性 CSV](../results/step5_3d_reconstruction/sensitivity.csv)。

实际复核 4,987 个原始数据文件中的 **2,212 张深度 PNG**；全部 640×480 RGB uint8、通道相同，无深度图 EXIF 或其他标定元数据。四个目录/季节组范围为 Dataset 夏季 0–245、冬季 0–244，With Summer GT 夏季 0–194、冬季 0–242，与先前记录一致。三个通道不是独立精度字节，不能拼成 24 位深度。

合成主实验包含 3 类解析三维 Y 树、每类 5 种输出（visible-only，linear/quadratic 的 measured-only 与 inferred-Z），共 **15 组指标/三维图**。遮挡方形边长为 16px。隐藏 Z 插值仍是明确假设，不把图像中的 0.4m 前景值赋予隐藏枝条。

| 合成场景 | 方法（启用隐藏 Z） | 可见 RMSE (mm) | 推断 RMSE (mm) | 支持分量 | 3cm 参考覆盖率 |
|---|---|---:|---:|---:|---:|
| constant_z | linear | 8.251 | 8.132 | 1 | 1.000 |
| constant_z | quadratic | 8.251 | 10.050 | 1 | 1.000 |
| varying_z | linear | 8.475 | 10.442 | 1 | 1.000 |
| varying_z | quadratic | 8.475 | 10.741 | 1 | 1.000 |
| curved_z | linear | 8.121 | 18.973 | 1 | 1.000 |
| curved_z | quadratic | 8.121 | 18.715 | 1 | 1.000 |

变化 Z 场景中不补全/不推断隐藏 Z 时，支持三维子图为 2 个分量、参考覆盖率 0.882；授权推断后为 1 个分量、覆盖率 1.000，仍未新增环。端点深度插值不保证恢复真实曲面 Z，二次二维补全也未在这些场景上普遍降低三维误差。

敏感性包括深度高斯噪声 σ=0/0.002/0.01/0.03/0.08m；焦距相对误差 −10/−5/0/+5/+10%；主点 x/y 同时偏移 −8/−4/0/+4/+8px；尺度误差 −10/−5/0/+5/+10%；深度丢失率 0/5/15/30/60%。三种种子 17/29/43，共 **150 行**，仅基于变化 Z 场景，不是实际相机不确定性估计。

关键趋势（各值三种种子的均值）：

- `depth_noise_m=0.08`，quadratic 支持点 RMSE 84.0mm，3cm 参考覆盖率 0.572，支持分量均值 1.0。
- `focal_error_fraction=0.1`，quadratic 支持点 RMSE 71.7mm，3cm 参考覆盖率 0.913，支持分量均值 1.0。
- `principal_point_error_px=8`，quadratic 支持点 RMSE 242.2mm，3cm 参考覆盖率 0.070，支持分量均值 1.0。
- `scale_error_fraction=0.1`，quadratic 支持点 RMSE 310.8mm，3cm 参考覆盖率 0.000，支持分量均值 1.0。
- `depth_dropout_fraction=0.6`，quadratic 支持点 RMSE 8.7mm，3cm 参考覆盖率 0.705，支持分量均值 51.3。

丢失深度时条件 RMSE 可能保持很小，但支持分量急增、参考覆盖下降，不代表算法更准确。缺失的可见点深度没有被 Step 4 隐藏链插值机制自动填充。

- `linear` 在扫描设置上的平均 lift 耗时 7.84ms，范围 5.60–12.83ms；不含二维补全/文件操作/绘图。
- `quadratic` 在扫描设置上的平均 lift 耗时 8.02ms，范围 6.02–12.76ms；不含二维补全/文件操作/绘图。

12 个真实草稿 × 两种方法共 **24 张非米制图/JSON**。每个真实三维坐标均为 null/unsupported；没有真实三维准确率、物理枝长或相机标定结果。图中灰度码不是深度，隐藏注释平面不是三维估计。

执行前后核验 **6929** 个原始/既有结果文件的 SHA-256、大小及修改时间：**0 改变**。详细清单在 `results/step5_3d_reconstruction/preservation_manifest.json`。

测试结果以 [完整日志](../results/step5_3d_reconstruction/tests/pytest_complete_output.txt)、[JUnit XML](../results/step5_3d_reconstruction/tests/pytest_junit.xml) 为准。新增覆盖已知三维树投影/反投影、轴向/range 差异、标定拒绝、单位误差、无效深度、隐藏前景不泄漏、输入保持、无支持/缺锚点/分叉/深度跳变拒绝、非米制真实输出和 CLI 覆盖保护。

完整测试实测结果：**97 passed**（原 79 项 + 新增 18 项），见上述完整日志与 JUnit。


## 独立审阅后的最终修正与证据边界（2026-10-25）

当前结论仍为 **PARTIAL**：合成已标定三维已验证，实际 Monash 米制三维尚无充分证据。
详见 [Step 5 最终来源调查与工程限制](step5_calibration_followup.md)。

已新增 `scripts/replay_saved_synthetic.py`，替代旧审阅包的 JSON 严格相等判定。
仅几何浮点字段使用 `abs(a-b)<=1e-12+1e-10*abs(b)`；节点 ID、像素位置、连通性、
状态/布尔标记、缺失值和标定输入继续精确比较。容差是计算复现标准，不是传感器精度。
旧 review package 与 ZIP 不改写，其严格比较脚本仅保留历史；当前复现命令以本节为准。

本次读取 HOB-CNN 原文第 2 节，确认其研究数据描述 D435 采集与网络输入中心裁方；
这不是本地 PNG 的数值标定，也未验证当前 GT 的变换。作者 HOBCNN-v2 仓库完整代码树和
28 个 notebook 代码单元未提供可用于本地数据的物理深度解码、内参、配准或三维 GT。
两个官方 Drive 数据包链接本次返回 404，两篇期刊全文返回 403，因此远程原包和全文附件未获审计。
不得把“当前未取得”写成“所有来源均不存在”，不得根据 D435 型号、FOV 或合成相机猜内参。

可靠真实三维仍需要：当前数据版本映射、可物理解码的深度及无效值约定、实际分辨率内参/畸变、
RGB-depth 注册/外参证明、木质深度归属复核，以及独立物理参考/三维验证。
单视图无法观测隐藏枝条；双锚点 Z 插值即使有标定也仍是 inferred。
所有真实物理 XYZ 继续 null/unsupported，演示和合成内参从未应用到真实图像。

本次新增日志与来源审计位于 `results/step5_followup_20261025/`，与原实验及审阅包分开。
完整测试数值以该目录的 `test_totals.json`、JUnit 和完整日志为准；包含原有测试与新增验证策略回归测试。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='results/test_dependencies;src'
python -m pytest -v -p no:cacheprovider
python scripts/replay_saved_synthetic.py
```

注意原 C 节的固定输出路径已有历史结果，完整 evaluator 重跑必须改用不存在的新路径，
例如 `python scripts/evaluate_step5.py --output results/step5_new_run`，不能覆盖旧结果。
本次不重新采集/转换原始数据、不修改重建算法、不开始 Step 6、不提交或推送 Git。


## 本次安装后的实测验证

完整仓库测试：127 passed，0 failed，0 errors，0 skipped。15 个现有合成结果通过容差重放；原审阅包的 15 个结果也由新验证器通过复核。实际最大浮点差为 0；这不改变允许舍入差异的验证政策。`git diff --check` 返回 0。数据、旧结果、原 ZIP 及重建算法的保护清单无变化。
首次安装后测试为 111 passed/16 errors，均为默认临时目录 PermissionError；第二次为 126 passed/1 failed，因为当前工作区位于 data/raw 下，原有 baseline 输出保护正确拒绝测试临时输出。两次日志均保留。最终在全新系统临时目录指定 --basetemp，完整重跑通过。最终日志为 pytest_complete_final_output.txt、pytest_final_junit.xml；没有忽略或跳过任何测试，未放宽原数据保护。
