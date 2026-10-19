# 横纵研究与商业尽调（Joy_Codex 版）

**从“这家公司是什么情况”，进一步走到“是否值得接触、还缺什么证据、下一步该问什么”。**

版本 **v1.0.0** · 维护者 **JoyZhang666** · [MIT](LICENSE) · [上游与改造说明](THIRD-PARTY-NOTICES.md)

这是一套交给 AI 助手阅读和执行的 Skill，附带本地数据汇总与可选 PDF 工具。继承 KKKKhazix 的横纵分析方法，整理为独立的 Codex 公开版本；所有随包案例均为虚构资料。

## 你给什么，拿到什么？

| 你提供 | 交付物 |
|---|---|
| 公司/产品/人物、想解决的问题、地域与截止日期；可附有权使用的文件 | 纵向发展、横向对比、交汇洞察的 Markdown 报告 |
| 是否合作、是否进入下一轮等决策问题 | 一页决策简报、风险与材料缺口、访谈问题和下一步 |
| 已整理的研究子问题 JSON（可选） | 保留原始数据的汇总 JSON、Excel 可打开的 CSV 和覆盖检查报告 |
| 定稿 Markdown 与明确授权的本地图像（可选） | 本地 HTML、A4 PDF；生成后仍需逐页检查 |

基础研究不需要知识库账号、飞书账号或本包专用 API Key。公开信息检索依赖你所用 AI 助手的搜索能力，费用按该服务规则计算。PDF 和数据脚本都在本机运行。

## 第一次开始

把下面这段话发给支持 Skill 的 AI 助手：

> 请从 https://github.com/JoyZhang666/joy-agent-skills 安装其中的 hv-analysis-codex。先检查文件，只安装这个目录；遇到同名版本先保留，不覆盖我的配置。安装后用包内虚构示例带我体验一次快速筛选，先不安装 PDF 依赖、不连接外部账号。

若助手无法访问 GitHub：在仓库首页点击 **Code → Download ZIP**，解压后找到直接包含 `SKILL.md` 的 `hv-analysis-codex` 文件夹，把完整位置告诉助手。不要把整个作品集合当作一个 Skill 安装。

安装后按助手提示刷新或新开对话，告诉它：

> 使用 hv-analysis-codex，研究我指定的公司，重点判断是否值得进入初次接触。先核实主体，只用我选定的材料与公开来源。没有依据的内容保留缺口，交付本地一页简报和证据清单。

AI 应先说明实际保存位置和已识别版本；仅复制文件不等于完成研究验证。[安装、Python 与 PDF 逐步指南](references/setup.md)提供具体命令及排错。

## 先看一份完整示例

[虚构供应商材料](examples/synthetic-supplier/materials.md) → [证据 JSON](examples/synthetic-supplier/raw/sq-evidence.json) → [一页决策简报](examples/synthetic-supplier/decision-brief.md) → [QA 与续接记录](examples/synthetic-supplier/run-record.md)

示例用 `example.com` 表示不存在的证据链接，便于练习结构，**不能作为真实公司研究或真实网页核验结果**。它同时展示母子公司客户混用、企业自述和同源转载三个常见问题。

## 有什么特点？

- 先核实主体，再分析，避免一开始就研究错公司。
- 比较财年、币种、集团/事业部范围和客户关系，减少看起来整齐、实际不可比的表格。
- 将合作吸引力与证据充分度分开，不用一个分数掩盖证据不足。
- 快速筛选、标准研究、深度尽调按问题选择；支持只做单轴或人物研究。
- 每条主要判断可追溯到事实、原文位置和待核验事项；部分失败可以续接。

## 工具、验证与限制

- **核心研究**：AI 按规程执行；研究质量仍取决于实际来源、检索能力和人工复核。本包不自动证明商业结论正确。
- **数据汇总**：Python 3.10+ 标准库即可使用；按实际计划 ID 检查缺失，兼容旧格式，保留原文，保护 CSV 文本单元格。不会将输入的 High/Medium 标记升级成事实验证。
- **PDF**：需可选依赖及本机浏览器；首版以 Windows Edge 为验证目标。受限 Markdown 支持标题、段落、列表、表格、链接与明确列出的本地 PNG/JPEG/WebP；原始 HTML、SVG、远程图片和主动内容会拒绝。复杂布局、跨平台及任意 Markdown 保真不作保证。
- **外部交付**：包内没有飞书推送能力。若需要在线文档，由当前环境可用的正式连接器在授权范围内处理。

确切验证范围见 [验证说明](VALIDATION.md)。[研究与尽调](references/research-method.md) · [证据格式](references/evidence-format.md) · [交付模板](assets/report-template.md) · [版本记录](CHANGELOG.md)

反馈请使用虚构或脱敏材料：[提交 Issue](https://github.com/JoyZhang666/joy-agent-skills/issues)。不要附上客户私稿、报价、个人路径、账号或密钥。运行资料保存到技能目录之外。
