# 适合手机阅读的 PDF 生成器

版本：1.0.5。保留中文手机阅读排版，默认 105 × 180 mm，支持 Markdown、HTML 和明确授权的本地素材。

**验证状态：本版公开发布，但未完成 WeasyPrint 70.0 真实隔离渲染验收；中文视觉、实际素材显示、底层资源隔离及跨平台端到端行为尚未验证。不能将本版描述为生产验证通过。**

已完成静态内容复核；开发阶段 78 项纯逻辑、模拟接口及合成 PDF/验收收集器回归通过，Windows 依赖探针已通过。它们不替代真实渲染验收。本次发布明确豁免该验收门槛，保留运行安全边界。

## 系统环境与平台状态

本 Skill 面向多平台桌面/服务器 Python 环境，并非 Linux 专用。“适合手机阅读”指生成的 PDF 版式，不是直接在 Android/iOS 上运行生成器。Agent 必须能在相应主机执行本地 Python 脚本；只有聊天界面、没有代码执行能力时不能运行生成器。

| 平台 | 配置路线 | 本项目验证状态 |
|---|---|---|
| Windows 11 x64 | x64 Python + 专用 venv + MSYS2 UCRT64 Pango DLL | 仅验证过 Python 3.12.14 / WeasyPrint 70.0 / Pango 1.58.2 / pypdf 6.19.0 的依赖加载；未完成真实 PDF 验收 |
| Linux | 发行版原生 Pango + Python venv；具体包名见安装指引 | 提供代码路径和配置指引，未在 Linux 实机验证；不承诺所有发行版或架构 |
| macOS（Intel / Apple Silicon） | 同架构 Python + Pango + venv；可用已获准的 Homebrew 安装原生库 | 实验性适配，未实机验证；原生库加载和资源限制兼容性需在目标系统核实 |

Windows 10、Windows ARM、其他 Unix、Android/iOS 不在当前已说明的支持范围内；上游库可能支持不等于本 Skill 已支持。没有任何平台获得本项目的完整端到端验证声明。WSL 属于 Linux 环境，不等于验证 Windows 原生路径。

必需依赖：**Python 3.10+、WeasyPrint==70.0 的 Python 库、Pango >=1.44 及其原生依赖、pypdf>=6.10,<7、可显示正文的中文字体**。Python、原生库和 wheel 架构须兼容，不混装 x64/ARM64。Python Markdown、pdfinfo、fc-list 为可选项。中文字体必须能被 Pango/Fontconfig 发现，字体文件存在不代表 PDF 已验证；可复用现有系统字体，不需要打包上传字体。

依赖清单见 [requirements.txt](requirements.txt)。**依赖未包含在 Skill ZIP 内；requirements.txt 仅安装 Python 包，不会自动安装 Pango 或字体。** Agent 先检测系统/架构、解释器和缺失组件，再说明路径和影响，获准后按 [详细安装指引](references/dependency-installation.md) 执行。仅安装 WeasyPrint 独立 EXE 不满足本包装器的 Python API 要求。

不要求 Linux 专用工具、GPU、Office、API Key 或云端 PDF 服务。安装依赖通常需要网络；依赖就绪后渲染不需要联网。虚拟机不是 WeasyPrint 本身的必需依赖，但处理不可信 HTML/CSS 仍须满足下文的隔离要求；本次发布验收豁免不取消运行安全边界。

下列命令需在 Skill 根目录运行，`python` 替换为实际 venv 解释器：Windows 为 `venv\Scripts\python.exe`，Linux/macOS 为 `venv/bin/python`（路径有空格时按所用 shell 正确引用）。

~~~sh
python scripts/check_dependencies.py
python scripts/render_mobile_pdf.py report.md --output report.pdf
python scripts/render_mobile_pdf.py report.html --output report.pdf --assets-dir assets --width-mm 105 --height-mm 180
~~~

默认创建新输出采用原子硬链接提交，要求本地文件系统支持硬链接（例如 NTFS/ext4/APFS；还须有目录写权限）；不支持时明确失败，不退回可能覆盖文件的操作。拒绝显式网络共享路径和 Windows 映射网络驱动器；Linux/macOS 的 NFS/SMB 挂载可能表现为普通绝对路径，脚本不识别其挂载类型，必须由调用环境保证输入、输出和素材位于本地文件系统。所有输入、输出及素材路径不得含符号链接/目录联接祖先；macOS 上需使用真实目录路径。已有输出需要显式 --overwrite。输入与输出必须不同；中间文件只在临时目录生成，失败不覆盖原件。素材以指定目录为相对引用基准，例如 assets 内的 chart.png 对应 HTML 中 src="chart.png"。

## 资源与内容边界

- 默认不读额外素材；--assets-dir 只允许 PNG/JPEG/WebP/CSS，单项 5 MiB、总计 20 MiB。
- 不联网下载素材，不允许 UNC、目录穿越、链接/联接资源、附件、SVG、活动嵌入和自定义字体文件。系统已安装字体作为渲染运行时依赖使用。
- CSS 间接引用同样走受控读取。违规读取会使整次生成失败，不交付丢素材的“成功”文件。
- 普通 HTTP(S) 超链接可以保留在 PDF 中，不会在生成时访问；这不授权自动打开这些链接。
- 保留后备 Markdown 转换，未闭合代码块会补全结束并保留正文。复杂 Markdown 不是完整规范实现，应使用已安装的可选 Markdown 包。
- 命令行尺寸强制应用于完整 HTML；宽 100–110 mm，高 100–500 mm。无法满足尺寸或正文提取检查时失败。
- 所有平台均设置渲染子进程约 60 秒的等待超时（终止收尾可能另需时间）。非 Windows 分支（包括 Linux/macOS）还尝试设置 60 秒 CPU 时间与 2 GiB 虚拟地址空间上限；不是 2 GiB 物理内存要求或保证。系统不支持、已有硬上限不允许或原生库无法在该地址空间内加载时，渲染会失败，不跳过限制。Windows 分支没有代码级 CPU/地址空间硬上限，不能宣称与 Unix 资源防护等价。子进程和临时目录均不等于操作系统沙箱。任意外部 HTML 必须在可验证的断网隔离环境中处理，不挂载私人目录或生产凭据。

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

## 1.0.5 修订

补充平台状态、架构/文件系统/字体要求，纠正非 Windows 资源限制及 POSIX 网络挂载说明。渲染子进程保留用户已配置的 DYLD_FALLBACK_LIBRARY_PATH 和 FONTCONFIG_FILE，修复 macOS 库路径及专用字体配置丢失；不扩大文件素材权限。仅用模拟环境回归验证配置传递，未进行 macOS 实机或真实 PDF 验收。
