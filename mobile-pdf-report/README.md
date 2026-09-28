# 适合手机阅读的 PDF 生成器

版本：1.0.4。保留中文手机阅读排版，默认 105 × 180 mm，支持 Markdown、HTML 和明确授权的本地素材。

**验证状态：本版公开发布，但未完成 WeasyPrint 70.0 真实隔离渲染验收；中文视觉、实际素材显示、底层资源隔离及跨平台端到端行为尚未验证。不能将本版描述为生产验证通过。**

已完成静态内容复核；开发阶段 78 项纯逻辑、模拟接口及合成 PDF/验收收集器回归通过，Windows 依赖探针已通过。它们不替代真实渲染验收。本次发布明确豁免该验收门槛，保留运行安全边界。

## 运行环境

Python 3.10+；WeasyPrint 70.0 Python 包及其原生依赖；pypdf。可选 Python Markdown、pdfinfo、fc-list。推荐已有的 Noto Sans CJK SC 等中文字体。依赖清单见 [requirements.txt](requirements.txt)。**这些依赖没有包含在 Skill ZIP 内；requirements.txt 只是安装清单。缺失时必须先安装，不能直接运行渲染。** Agent 应先向用户说明具体路径和影响，经同意后按 [详细安装指引](references/dependency-installation.md) 执行；未经同意不安装。

~~~sh
python scripts/check_dependencies.py
python scripts/render_mobile_pdf.py report.md --output report.pdf
python scripts/render_mobile_pdf.py report.html --output report.pdf --assets-dir assets --width-mm 105 --height-mm 180
~~~

默认创建新输出采用原子硬链接提交，要求本地文件系统支持硬链接（例如 NTFS/ext4）；不支持时明确失败，不退回可能覆盖文件的操作。拒绝网络共享路径和 Windows 映射网络驱动器。已有输出需要显式 --overwrite。输入与输出必须不同；中间文件只在临时目录生成，失败不覆盖原件。素材以指定目录为相对引用基准，例如 assets 内的 chart.png 对应 HTML 中 src="chart.png"。

## 资源与内容边界

- 默认不读额外素材；--assets-dir 只允许 PNG/JPEG/WebP/CSS，单项 5 MiB、总计 20 MiB。
- 不联网下载素材，不允许 UNC、目录穿越、链接/联接资源、附件、SVG、活动嵌入和自定义字体文件。系统已安装字体作为渲染运行时依赖使用。
- CSS 间接引用同样走受控读取。违规读取会使整次生成失败，不交付丢素材的“成功”文件。
- 普通 HTTP(S) 超链接可以保留在 PDF 中，不会在生成时访问；这不授权自动打开这些链接。
- 保留后备 Markdown 转换，未闭合代码块会补全结束并保留正文。复杂 Markdown 不是完整规范实现，应使用已安装的可选 Markdown 包。
- 命令行尺寸强制应用于完整 HTML；宽 100–110 mm，高 100–500 mm。无法满足尺寸或正文提取检查时失败。
- 子进程超时 60 秒；Linux 另设 CPU/内存上限。子进程和临时目录均不等于操作系统沙箱。任意外部 HTML 必须在可验证的断网隔离环境中处理，不挂载私人目录或生产凭据。

## 成功条件

WeasyPrint 完成后由 pypdf 检查每页尺寸、页数、正文可提取性及无附件；通过后才原子保存最终 PDF。依赖检查通过只表示导入/API 可用，不代表渲染或沙箱通过。

中文字体与视觉排版仍须实际打开 PDF 检查；文字可提取不能证明字体没有方框。安全资源策略不能替代底层解析器的 OS 隔离。包装器错误返回通用原因；底层原生库可能输出环境诊断。诊断只留本地，提交 issue 前应脱敏，不粘贴原始私人路径或正文。

详见 [SKILL.md](SKILL.md)。MIT 许可见 [LICENSE](LICENSE)。

## 1.0.1 修订

补充依赖检查、用户授权、Windows/Linux/macOS 安装路径及验证指引；渲染子进程保留专用 WEASYPRINT_DLL_DIRECTORIES，支持已批准配置的 Windows Pango DLL 路径。未改变素材读取边界，未完成真实隔离渲染验收。

## 1.0.2 修订

技术标识与目录保持 mobile-pdf-report。本版更新展示名称，并在渲染器记录图片加载等 ERROR 时阻止交付，避免静默丢失素材；完整隔离渲染仍待验证。

## 1.0.3 修订

后备 Markdown 转换按围栏字符及长度识别代码块结束，支持波浪线围栏，保留代码行末空格和制表符，避免较短围栏提前终止代码正文。真实隔离渲染仍待验收。

## 1.0.4 修订

更新发布状态和验证限制；渲染代码与 1.0.3 相同。未执行真实隔离渲染，不宣称 F004/F006/F007 的集成行为已验证。运行隔离、用户授权安装、资源限制及文件保护规则继续有效。

问题反馈可使用仓库 Issues；仅提交虚构最小复现和脱敏信息。
