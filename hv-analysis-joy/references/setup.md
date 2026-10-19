# 安装与可选工具：一步一步开始

## 1. 先识别 Skill，不急着安装依赖

请 AI 确认你使用的宿主、当前工作目录和实际 Skill 导入入口。支持 Codex 技能安装能力时，优先请它只安装 `hv-analysis-joy`；手工安装时依照当前宿主文档，把直接含 SKILL.md 的完整目录放入宿主指定的位置，不覆盖同名旧版。刷新或新开对话后，让 AI 报出识别到的名称与版本。

核心研究只需要 AI 和你提供的材料/可用搜索。没有知识库也可以开始。先用 examples/synthetic-supplier/materials.md 体验一页简报；示例是虚构的，不应对示例网址联网查证。

## 2. 需要汇总 JSON 时，再检查 Python

让 AI 检测已有 Python；3.10 或更高可用。本包数据汇总只用标准库，不需要 pip 安装。没有 Python 时，可从 https://www.python.org/downloads/ 获取官方版本，或请 AI 使用当前 Codex 提供的解释器。软件安装由你的实际环境和授权决定，不运行陌生安装器。

以下在 PowerShell 中操作。将示例位置替换为 AI 确认的真实绝对目录；`<...>` 是说明占位符，不可照抄：

```powershell
$skillRoot = '<解压后直接含 SKILL.md 的目录>'
$runRoot = '<本次研究的独立输出目录>'
# run.ps1 优先使用 RESEARCH_PYTHON，或包内 .venv，然后寻找已有 Python / Codex bundled Python
& "$skillRoot/scripts/run.ps1" "$skillRoot/scripts/check_runtime.py" --capability aggregate
& "$skillRoot/scripts/run.ps1" "$skillRoot/scripts/aggregate.py" --input-dir "$skillRoot/examples/synthetic-supplier/raw" --output-dir "$runRoot/aggregate-01" --expected-sq SQ-EVIDENCE
```

看到 `technical_status: complete` 表示示例结构与计划项齐全；`fact_verification: not_performed` 表示程序没有核验事实。新目录中应有三个输出文件。返回码 2 是缺少计划项，不要把它写成完整研究。再次运行用新目录，避免覆盖。

若普通 Windows PowerShell 的执行策略阻止 `.ps1`，不要修改系统安全策略：请 AI 用当前 Codex 可用的 PowerShell 7，或直接用已确认 Python 执行相同 `.py` 文件。

## 3. 按需安装 PDF 依赖

PDF 可选依赖为 Markdown、Playwright；Windows 使用已安装 Edge，不要求下载额外 Chromium。不需要 API Key、GPU、Office 或飞书账号。字体使用系统中文字体，不随包分发字体文件。

让 AI 先检查依赖；需要安装时说明位置和范围。推荐在此 Skill 的独立副本中建立 `.venv`，不修改全局 Python：

```powershell
python -m venv "$skillRoot/.venv"
& "$skillRoot/.venv/Scripts/python.exe" -m pip install -r "$skillRoot/requirements-pdf.txt"
& "$skillRoot/.venv/Scripts/python.exe" "$skillRoot/scripts/check_runtime.py" --capability pdf
& "$skillRoot/.venv/Scripts/python.exe" "$skillRoot/scripts/md_to_pdf.py" "$skillRoot/examples/synthetic-supplier/decision-brief.md" "$runRoot/brief-01.pdf" --title '虚构供应商决策简报'
```

`python` 替换为你已确认的实际解释器。不要照搬作者的电脑路径。本包不自动运行 pip 或浏览器安装；可另用当前会话的 `RESEARCH_PYTHON` 指定解释器。`.venv` 只隔离 Python 依赖，不是处理不可信文件的操作系统沙箱。

本地图片要逐个显式列出，例如 `--asset '<已确认图像绝对路径>'`；只支持 PNG/JPEG/WebP，图片必须位于 Markdown 同目录或子目录，禁止符号链接/重解析点、远程 URL 与 SVG。未列出的图片会被拒绝。每张最多 5 MiB，总计最多 10 MiB；Markdown 最多 2 MiB。

网页超链接保留 http/https 地址与页内锚点，但渲染时不访问它们；指向相邻 Markdown 等相对文档链接只保留显示文字，不读取或打开目标文件。

## 4. 常见问题与验收

- **缺模块**：使用同一个解释器安装 requirements-pdf.txt，再检查；不要安装名字相似的其他包。
- **没有浏览器**：安装官方 Microsoft Edge 后再试；`--browser-path` 仅用于已确认的浏览器可执行文件。首版没有 Linux/macOS 验收声明。
- **路径错误或中文路径**：让 AI 展示完整路径并加引号，确认原文件实际存在。
- **原始 HTML/远程资源被拒绝**：改成支持的 Markdown，用有权使用的本地图像并显式列出；不要关闭网络拦截来绕过。
- **目标已存在**：选新文件名；转换失败可能保留 HTML 以排错，使用新输出名重试。
- **生成了 PDF**：还需打开逐页检查中文、表格、分页、图片与文本；文件存在、页数和文字可提取都不替代视觉和业务验收。

运行材料、原始报告和 QA 留在本地研究目录；不要放入技能源码或提交到公开仓库。
