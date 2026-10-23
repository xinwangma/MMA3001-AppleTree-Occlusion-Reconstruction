# Step 3 可见枝条标注修订与质量复核

日期：2026-10-23。本轮改进可见区域标注、编辑工具与二维诊断，未启动遮挡补全。

## 结论与入口

原来的 30 个 AI 草稿片区仅覆盖局部木质结构，并非整棵树的完整可见标注。
本轮逐一查看 12 张原始 RGB、原草稿叠加及放大局部像素图。
10 个样本补充／修订明确可见的小段；R03N02、R12N02 因植被、遮挡与结构身份歧义保留原掩膜。
修订仍不完整，不能称为人工审核完成，不能据此宣称重建精度提升。

- 最终对比：[`coverage_revision_v4/run/index.html`](../results/step3_real_validation/coverage_revision_v4/run/index.html)。
- [原始图库](../results/step3_real_validation/index.html)已增加最终修订入口，原始 draft_run 保留。
- 修订标注包：`results/step3_real_validation/coverage_revision_v4/annotations.json`。
- 覆盖审计：`results/step3_real_validation/coverage_revision_v4/coverage_audit.json`。
- 每样本保存掩膜、骨架、图 JSON、诊断、质量检查、四联图与 `before_after.png`。

最终采用 **v4**。v2 是放大复核中否决的初步候选，存在叶片／果实／植被误覆盖；
v3 是边界与拓扑预检查版本，R04N02 的窄条叠加产生微小环，R09N02 产生短刺。
两者均明确标为废弃／被取代，不能用于后续重建，仅作为本地失败记录保留。
最终对 R04N02、R09N02 显式重画了 RGB 支持的完整右枝多边形，没有执行自动填洞或剪枝。

## 实际观察与变化

坐标均为 640 × 480 原图整数像素。可见性由 AI 目视判断，仍需人工确认。

| 样本 | 修订／未修订原因 | 骨架像素 前→后 | 分量 前→后 | 端点 前→后 | 交汇像素 前→后 |
|---|---|---:|---:|---:|---:|
| R01N02 | 补充原 y=447 下沿附近短段树干；不延伸到草丛 | 295→297 | 2→2 | 4→4 | 0→0 |
| R02N02 | 补左主枝窄多边形遗漏的可见下侧表面，排除上方叶片 | 263→260 | 2→2 | 4→4 | 0→0 |
| R03N02 | 下部树干、支撑物与植被重叠，覆盖不足仍未解决 | 124→124 | 2→2 | 4→4 | 0→0 |
| R04N02 | 修订右主枝上部，以完整多边形替代窄条叠加 | 167→197 | 3→3 | 6→6 | 0→0 |
| R05N02 | 增加左上裸露木质段，叶片遮挡处仍断开 | 255→306 | 3→4 | 6→8 | 0→0 |
| R06N02 | 增加右侧短裸露段，原嫁接区域短刺留待复核 | 178→198 | 2→3 | 5→7 | 1→1 |
| R07N02 | 增加左主枝可见段，在果实上缘前停止 | 79→103 | 3→3 | 6→6 | 0→0 |
| R08N02 | 增加原来完全遗漏的左主枝裸露中段，不跨叶片 | 193→220 | 3→4 | 6→8 | 0→0 |
| R09N02 | 修订右主枝上部，在横向线材下方停止 | 225→240 | 3→3 | 6→6 | 0→0 |
| R10N02 | 增加左主枝裸露短段，保留叶片／果实间隙 | 247→260 | 3→4 | 6→8 | 0→0 |
| R11N02 | 增加左侧小段裸露木质，触发小分量提示 | 114→122 | 2→3 | 4→6 | 0→0 |
| R12N02 | 下部疑似延续被植被打断，不猜测连续路径 | 143→143 | 2→2 | 4→4 | 0→0 |

相对原稿新增 1,421 掩膜像素，边界修订移除 12 像素；片区总数 30→38。
12 个样本的输入分量在各自骨架中均一一保留；38/38 个草稿片区存在骨架像素；
骨架越界 0，所有样本环秩与孤立像素均为 0。
分量增加可能来自新增独立可见片段，不能擅自连接。R02N02 掩膜覆盖增加而骨架像素略少，
进一步说明像素数量不是质量评分。

每样本预热一次，再重复 3 次，仅计细化与像素图构建。
样本中位数的中位数为 188.2 ms，范围 115.1–266.4 ms，不是端到端 RGB 性能，
不能将前后计时差异解释为算法加速。12 张输入 RGB 的 SHA-256 与修改时间保持不变。

## 改进后的标注界面

工具只显示 RGB，不加载 Summer GT、冬季图或深度。加载 AI 草稿是有种子的人工修订，
不是独立盲标。必须保存到 `results/` 或 `data/processed/` 下的新目录。

```powershell
python scripts/annotate_visible_branches.py --rgb "data/raw/monash_y_tree/TreeID/Dataset (With Summer GT)/R08N02_Summer_RGB-13-25-57.png" --load results/step3_real_validation/coverage_revision_v4/run/R08N02/annotation.json --output results/step3_real_validation/human_R08N02_v1 --annotator "你的姓名" --notes "只标可见主干和主要枝条；记录覆盖、遮挡与歧义"
```

独立盲标使用新目录，并去掉 `--load`。

1. **Draw**：点击顶点，Enter 完成多边形，Backspace 撤销当前顶点；不要重复首点闭合。
2. **Zoom**：1–6 倍最近邻显示；滚动条／中键拖动平移。保存仍使用原图整数坐标。
3. **Edit**：右侧选中多边形，拖动黄色顶点；边附近右键插入顶点；Delete 删除选中多边形。
4. **Mask overlay**：切换半透明实际栅格掩膜；角色包括 trunk、major_branch、uncertain_fragment。
5. **Visible checkpoint**：在明确可见主干／主枝放检查点；**Occluded checkpoint**：在明确遮挡点放排除点。
   绿色十字为可见必需点，红色十字为遮挡排除点；按钮可撤销最后一个检查点。
6. Ctrl+Z / Ctrl+Y 撤销／重做完成的几何与检查点；未完成顶点使用 Backspace。
7. 填写覆盖／歧义说明，Ctrl+S 保存 JSON 与二值掩膜；未完成多边形不能保存。
   退出有未保存内容时提示。几何修改与保存均重置 pending，不保留审核／批准状态。

按 RGB 中可见的每一段逐段描绘；遇叶片、果实、线材或邻树身份不清时停止。
用独立多边形表示被遮挡分隔的片段，不沿“应有的树枝方向”连线。
工具拒绝越界、非整数、退化、重复顶点和自交多边形，但不能判断木质身份和真实可见性。

## 草稿、人工复核与批准

`provenance` 记录来源，`review_status` 记录工作流。当前 12/12 均为 AI DRAFT / pending，
人工复核 0，批准 0。

| 状态 | 必要记录与含义 |
|---|---|
| pending / DRAFT | 来源、标注者、说明、RGB 哈希；未完成审核 |
| reviewed | 实际 reviewer、reviewed_utc、review_notes；尚未批准，保留 AI 父来源 |
| accepted | reviewed 后由另一人明确 approved_by、approved_utc、approval_notes |
| rejected | 否决者与原因；不允许进入诊断运行 |

只有人在真实查看后才可执行以下命令，脚本不会自动审核。

```powershell
python scripts/review_visible_annotation.py --annotation results/step3_real_validation/human_R08N02_v1/annotation.json --output results/step3_real_validation/human_R08N02_v1/reviewed.json --status reviewed --person "实际复核者" --notes "实际观察、未覆盖区域和接受范围"
python scripts/review_visible_annotation.py --annotation results/step3_real_validation/human_R08N02_v1/reviewed.json --output results/step3_real_validation/human_R08N02_v1/approved.json --status accepted --person "另一位实际批准者" --notes "批准依据与保留问题"
```

每次写新文件并记录父文件哈希。这些记录是人的声明，无法自动证明身份或标签独立性。
复核 AI 种子仍不是独立盲标真值，批准也不自动授权精度评估。
旧 JSON 仅写 accepted 而缺日期、说明或批准者时，新校验会拒绝，需要真实补齐工作流。

## 再生成与质量检查

批处理支持 `samples` 标注包，也支持编辑器的单个 JSON。未批准标注需显式 `--include-drafts`；
rejected 不允许运行。

```powershell
python scripts/validate_visible_baseline.py --annotations results/step3_real_validation/human_R08N02_v1/annotation.json --output results/step3_real_validation/human_R08N02_diagnostics_v1 --include-drafts --repeats 3
```

`quality_checks.json` 包括：

- **漏标**：显式 visible_required 点必须位于掩膜内，可指定主干缺失段；无点时 coverage_check_available=false，不能声称覆盖完整。
- **遮挡误标**：occluded_excluded 点必须在掩膜外；只检验该像素。本批没有人工确认的遮挡检查点。
- **碎片候选**：分量 ≤12 骨架像素；R11N02 触发，不自动删除。
- **短刺候选**：端点到交汇的终端路径 ≤8 px；R06N02 触发，回看嫁接区域。
- **端点与连接**：端点坐标、边界标志、分量大小；不同分量端点距离 ≤12 px 仅提示 RGB 复核。本批 R05N02、R10N02 触发，绝不自动连线。
- **拓扑**：环秩、孤立／交汇像素；diagnostics 另检查分量一一保留与骨架越界。

阈值是原图像素单位的启发式提示，不是生物学判定或“质量通过”标准。
10 个 AI 可见点由修订前未覆盖变为修订后覆盖，但修订直接围绕这些点进行，不能当作独立验证。
R03N02、R12N02 无可见检查点，“0 条失败”不能表示无漏标。
只靠掩膜／骨架无法自动发现全部缺失枝条，仍需要人在 RGB 中检查覆盖与设置检查点。

复现本轮坐标和处理（必须新输出目录），或仅刷新报告：

```powershell
python scripts/revise_step3_drafts.py --output results/step3_real_validation/coverage_revision_another_run --repeats 3
python scripts/revise_step3_drafts.py --report-only
python scripts/build_step3_gallery.py
```

`--report-only` 复用保存的掩膜和图，不重新细化。

## 测试与仍未完成的工作

完整测试 **63 passed**，包括原有 50 项与新增 13 项。

```powershell
$env:PYTHONPATH='results/test_dependencies;src'
python -m pytest -q
```

新增测试覆盖漏标／遮挡点、无点时不能声称覆盖、非法点、小分量／短刺／邻近端点提示不修改图、
自交多边形、缩放坐标、草稿→人工复核→不同人批准、编辑撤销批准等约束。
另检查 CLI、Python 编译、12 样本图像／指标／相对链接与源文件哈希。
实际鼠标／键盘交互尚未由人验收，后端测试不代表人工可用性验证。

独立人工完整标注与审核仍待完成。未用 Summer GT 作为 visible-only 真值，未跨遮挡补枝，
未更改原始 RGB-D，未提交或推送。未开始 Step 4，不报告重建准确率。
