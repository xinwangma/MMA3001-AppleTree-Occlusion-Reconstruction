# Step 5 复核后修正与真实三维证据调查

本次工作仅修改重放验证与测试、补充文档。未修改重建算法、未开始 Step 6、未提交或推送 Git。既有数据、实验结果和 `results/step5_review_package.zip` 保留为历史记录；旧包中的“逐位完全相等”脚本不再作为当前数值复现标准。当前入口是 `scripts/replay_saved_synthetic.py`。

## 1. 数值重放验证修正

旧脚本将整个 JSON 用 `==` 比较。现在仅对节点 `xyz_m`、边 `length_m/length_px` 和 `total_length_px` 的数值允许：

`abs(actual - expected) <= 1e-12 + 1e-10 * abs(expected)`。

即 `atol=1e-12`、`rtol=1e-10`。米制坐标和长度的 atol 单位为米，像素长度的 atol 单位为像素；rtol 无量纲。约 3m 坐标允许差异为 3.01×10⁻¹⁰m，近零允许 10⁻¹²m，远小于本实验约 8mm 的栅格量化误差与 3cm 覆盖阈值。这是容纳 float64 运算及最小二乘后端舍入差异的**计算复现容差**，不是传感器精度或真实重建容许误差。

仍精确比较：字段集合、节点/边数量及顺序、节点 ID、整数像素坐标、边起止 ID、连通分量、端点/分叉列表、measured/inferred/unsupported 状态、布尔标记、拒绝原因、null、状态计数及完整标定输入。精确字段还检查基本类型，`True` 不能冒充 `1`、浮点 ID 不能冒充整数 ID。NaN/Infinity 拒绝。不同栅格路径或拓扑即使空间上很接近也必须失败，不使用最近邻重排来掩盖结构变化。

新增回归测试覆盖：允许的小浮点扰动、近零和相对容差边界、超限坐标/长度、非有限值、ID/像素/布尔类型变化、连接变化、节点重排、null 被替换、状态/计数变化、标定变化及缺失/额外字段。诊断中的最大绝对差跨米/像素字段，仅用于计算一致性诊断，不可当作物理重建误差。

从仓库根运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='results/test_dependencies;src'
python -m pytest -v -p no:cacheprovider
python scripts/replay_saved_synthetic.py
```

默认读取现有 `results/step5_3d_reconstruction/synthetic`，只读，不重写结果。可显式指定 `--source-root`、`--evidence-root`；`--report` 必须是不存在的新文件。本次日志保存在新的 `results/step5_followup_20261025/`。旧审阅包也可用新脚本复核，例如 `--source-root results/step5_review_package/project --evidence-root results/step5_review_package/evidence/step5/synthetic`。

## 2. 一手来源调查范围与结果

访问日期：2026-10-25，Australia/Sydney。以下是本次实际读取范围，不把检索摘要、出版物记录或无法打开的全文当作完整技术资料。

| 来源 | 实际检查范围 | 已验证内容 | 未得到的内容 |
|---|---|---|---|
| [S1 Monash 2022 发布页](https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction) | 发布页正文及其下载链接 | 页面描述 435 个 RGB-D Y 树样本，三季节；列出三类二维标签及 Drive 链接 | 本地文件版本映射、相机数值内参、深度解码、配准、三维 GT |
| [S2 Monash HOB-CNNv2 发布页](https://www.monash.edu/engineering/lmga/news/y-shaped-apple-tree-public-dataset-for-hob-cnnv2) | 可访问的索引正文；直接打开有超时 | 发布页指向另一 Drive 文件和作者仓库，研究夏冬二维枝条检测 | 适用于本地 PNG 的标定或深度转换公式 |
| [S3 作者 HOB-CNN 原文](https://arxiv.org/html/2208.00002) | 可访问完整 HTML，重点为第 2、3 节和全文相关术语 | 第 2.1 节明确描述 Intel RealSense D435；第 2 节说明网络输入中心裁方后缩放至 256×256；标注为图像位置/掩膜 | 没有给出可直接绑定本地导出 PNG 的 fx/fy/cx/cy、深度尺度/传递函数、导出配准证明或独立三维坐标 GT |
| [S4 作者 HOBCNN-v2 仓库](https://github.com/ZijueChen/HOBCNN-v2) | 完整递归文件树、README 与全部 28 个 notebook 代码单元；不运行外部 notebook | 当前树 SHA `cff66f0d4b144648be626c44c154f7d2603c1548`；1500 个 PNG，另有 notebook、README、LICENSE、requirements；代码为二维训练/位置预测和图像归一化 | 未找到可用的物理深度解码、数值相机标定、配准实现或三维 GT；文件名重合不证明同一归档 |
| [S5 HOB-CNNv2 论文记录](https://research.monash.edu/en/publications/hob-cnnv2-deep-learning-based-detection-of-extremely-occluded-tre/) | Monash 出版物元数据与摘要；期刊正文访问返回 403 | 正确作者、题目、DOI 10.1016/j.compag.2024.108727；研究二维预测及季节参考 | 全文/补充资料未审计，不能断言其中没有标定 |
| [S6 OBR 三维重建论文记录](https://research.monash.edu/en/publications/obscured-tree-branches-segmentation-and-3d-reconstruction-using-d/) | Monash 元数据/摘要和实验室新闻；期刊正文访问返回 403 | 作者为 Eugene Kok、Xing Wang、Chao Chen，DOI 10.1016/j.compag.2023.107884；确有作者自己的三维研究 | 未取得其全文/三维数据，未建立与本地数据逐样本对应；文献精度不能作为本项目实测 |
| [S7 RealSense 官方投影文档](https://github.com/realsenseai/librealsense/wiki/Projection-in-RealSense-SDK-2.0) | 内参、外参、深度格式与配准章节 | SDK 的内参、深度尺度和流间外参有明确独立接口；标准 Z16 是逐像素 uint16 深度 | 这只是 SDK 一般格式说明，不是本地 uint8 PNG 的解码规范 |

S4 代码树未截断，1512 项（含目录），1504 个文件。notebook blob SHA 为 `41ff5048f86383dc9ba57be108a7b278b5077c2a`。代码没有提供物理标定；将网络输入除以 255 只代表强度归一化，不能把 `stored_code/255` 当作米或可验证的距离。外部 notebook 没有被执行。

两个官方链接分别为：

- [S1 数据包](https://drive.google.com/file/d/1-6akVXezq26ihtDrVH9czGUQDFd8Py81/view)
- [S2 数据包](https://drive.google.com/file/d/1nIdYBXdbXle7Id8HDgRbolTlGeVUJRJ5/view)

Drive 元数据工具均返回 404，公开预览页面直接读取也均为 HTTP 404。故没有下载/解压这两个远程原包，没有核查其内部 README 或标定附件；404 只能说明本次访问不可用，不能区分删除、权限、迁移等原因，更不能证明数据从未含有校准。期刊全文返回 403，因此未把全文或补充资料标为已检查。已将访问结果和作者代码审计信息保存在本次新结果目录，未联系或代用户发送邮件给作者。

## 3. 数据来源映射：明确分开事实与推断

**本地已验证事实**：现有全量扫描覆盖 4987 个 PNG，2212 个深度文件；深度为 640×480、RGB uint8、通道相同，本地没有标定/说明/点云文件。两目录分别有 544 与 562 个树 ID，均为夏冬配对；与 S1 页面列出的三季节 435 样本不是直接等同的文件清单。详细原始证据见 `docs/09_real_dataset_inspection.md` 与现有 `calibration/depth_investigation.json`，本次不改写旧扫描结果。

**文献已验证事实**：S3 对其研究数据说明 D435 采集，其交叉验证 Table 3 第一组恰有夏103/秋89/冬243，与 S1 的 435 组成一致。论文第 2 节的中心裁方说明也是其训练预处理事实。

**仅为线索/推断**：S1 可能只发布了 S3 一个交叉验证组；本地夏冬数据可能与 HOB-CNNv2 的季节数据库相关。没有可访问的原包清单、下载出处/版本记录或哈希逐文件对应，不能把这些可能性升级为确定来源。论文中夏季总量的段落/表格还存在不一致，也不应靠数量巧合做身份确认。

**不能迁移的假设**：不能因为相关研究用了 D435，就猜本地相机的 fx/fy 或把 principal point 设为图像中心；不能因为 SDK 标准 Z16 通常可通过尺度转换，就把当前重复三通道 uint8 导出当作原始 Z16、默认毫米或拼成 24 位；不能把论文的中心裁剪预处理当作当前 GT 掩膜的已验证变换。这里不更改原 Step 3 对齐结果。

## 4. 最终工程证据状态

| 项目 | 当前状态 | 工程含义 |
|---|---|---|
| 合成相机与解析三维参考 | CALIBRATED SYNTHETIC，已验证 | 支持反投影数值验证与已设场景下的方法比较 |
| 真实内参 fx,fy,cx,cy | MISSING / 未验证 | 不产生真实米制 XYZ |
| 真实深度单位、比例、偏置、非线性映射 | MISSING / 未验证 | 灰度码不等于物理距离 |
| 轴向 Z / 欧氏 range、无效值约定 | MISSING / 未验证 | 零值计数不是已验证传感器失败率 |
| 深度/RGB 配准、畸变、流间外参 | MISSING / 未验证 | 相同尺寸和名字不证明同像素对应 |
| 独立真实三维 GT | MISSING / 未验证 | 无法报告本项目真实 3D RMSE/Chamfer/枝长精度 |
| 实测表面与木质中轴对应 | 未验证；真实可见标注仍 AI/pending | 深度可能属于叶片、背景或树干表面，不能直接声称中轴测量 |
| 隐藏枝条深度 | 单视图不可直接观测 | 双锚点插值是明确假设，标定齐备也不会使其成为 measured |

目前所有真实节点继续 `xyz_m=null,status_3d=unsupported`，没有 VERIFIED REAL METRIC 3D 结果。没有应用演示/合成内参至真实图像，也没有虚构任何标定值。

## 5. 可靠真实三维重建还需要什么

1. **确认当前指定数据的身份**：从课程提供者或数据作者取得确切发布版本、有效原包链接/文件清单、采集与导出过程，并与本地文件哈希或可靠样本映射核对。不要将两个 U/N 目录、不同发布版或不同季节默认为相同视点/树体。
2. **取得可恢复物理距离的深度**：原始高精度深度/录制文件与实际尺度，或本地 8 位导出的完整传递函数（是否归一化、逐帧范围、反相、截断、偏置等）、单位、Z/range、无效码及置信度。如果已不可逆归一化或截断且映射未保留，现有 PNG 无法唯一恢复距离，需要原始深度或重新采集；即使映射可知，也要量化量化误差是否满足任务精度。
3. **取得对应设备与分辨率的几何标定**：实际 fx,fy,cx,cy、畸变模型/系数、整流/裁剪/缩放过程；若 RGB/depth 独立成像，取得旋转/平移、同步信息和注册方法，或可核验的已对齐深度及其输出坐标网格。相机型号和一般 SDK 默认值不是替代品。
4. **确认木质深度归属与有效观测**：独立审阅真实可见枝条掩膜、排除叶片/支架/背景与错配深度，检查重复冬季深度，明确表面点到中轴骨架的建模偏差。不能把无效观测静默插值成 measured。
5. **用独立度量验证可靠性**：提供同一树/时刻/坐标系的标尺、实测控制点/枝长、已标定多视图或高精度参考点云；若要声称三维精度，需要独立三维参考、配准误差和评估协议/样本数。三维 GT 不是运行反投影的输入前提，但它或其他独立物理验证是可信精度声明所需证据。二维 whole-branch GT、未注册的冬图和其他论文的误差均不能替代。
6. **验证隐藏几何并报告不确定性**：多视图/补充测量验证推断枝条，扩大遮挡长度和非线性 Z 场景，评估覆盖率、拓扑、拒绝率和端到端运行时间。机器人/世界坐标应用还需相机位姿及外部坐标标定；仅相机坐标输出不自动具备这些信息。

如果无法取得以上资料，应将工程交付明确限定为“已标定合成三维验证 + 真实二维定性补全”，而非真实米制三维重建。Step 5 总体工程目标仍为 **PARTIAL**；自动化测试通过证明实现与约束的一致性，不证明果园测量精度。Step 6 尚未开始。


## 本次安装后的实测验证

完整仓库测试：127 passed，0 failed，0 errors，0 skipped。15 个现有合成结果通过容差重放；原审阅包的 15 个结果也由新验证器通过复核。实际最大浮点差为 0；这不改变允许舍入差异的验证政策。`git diff --check` 返回 0。数据、旧结果、原 ZIP 及重建算法的保护清单无变化。
首次安装后测试为 111 passed/16 errors，均为默认临时目录 PermissionError；第二次为 126 passed/1 failed，因为当前工作区位于 data/raw 下，原有 baseline 输出保护正确拒绝测试临时输出。两次日志均保留。最终在全新系统临时目录指定 --basetemp，完整重跑通过。最终日志为 pytest_complete_final_output.txt、pytest_final_junit.xml；没有忽略或跳过任何测试，未放宽原数据保护。
