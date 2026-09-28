# 必需依赖的检查、授权安装与配置（供 Agent 使用）

适用：mobile-pdf-report 1.0.4；资料核对日期：2026-09-28。以下是安装操作指引，不代表用户已经批准安装，也不代表已在所有平台实测。

## 1. 先解释清楚，再申请授权

本 Skill 不捆绑 WeasyPrint、Python、Pango、pypdf 或字体的安装包/二进制。requirements.txt 只是 Python 依赖清单，解压或安装 Skill 不会安装依赖。当前包装器必须使用 **WeasyPrint 70.0 的 Python API**，仅装 WeasyPrint 独立 EXE 或把 weasyprint 命令加入 PATH 都不够。

运行前必需：Python 3.10+、WeasyPrint 70.0、Pango 及其原生依赖、pypdf（范围见 requirements.txt），以及可显示正文的中文字体。Python Markdown 是可选增强；pdfinfo 仅为可选诊断工具。缺任何必需项，停止 PDF 生成，先解决依赖。

Agent 先只读检查现有解释器、版本/架构、可用磁盘和目标目录权限；优先复用兼容运行时，Python 包放专用虚拟环境。不要为了探测而运行可能自动下载运行时的裸 python/py 启动别名；先通过已知绝对路径或 Python 管理器的 list 查询确认已安装解释器。

向用户列明实际缺失组件、可信下载来源、具体展开后的安装路径、下载/磁盘开销（未知则说明）、是否需要管理员权限，以及哪些已有组件可能更新。下列为申请模板，替换括号后使用：

> 此 Skill 生成 PDF 必须使用 WeasyPrint 70.0 Python 库及 Pango；当前缺少【实际缺失项】。建议 Python 包装入【专用 venv 绝对路径】，原生库放在【MSYS2 路径或已确认系统包位置】，必要的 Python 放在【路径】。将从【来源】下载安装，可能影响【具体变更】。我将使用明确的解释器和进程级 DLL 配置，不擅自升级其他项目或修改全局 PATH。是否同意按这个方案安装配置？

收到明确同意后才下载、创建运行时、安装/更新组件。已有明确覆盖同一组件、位置及影响的授权可直接使用；沉默不是同意。用户拒绝则保留本地输入并说明暂不能生成。权限或路径变化超出批准范围时，先说明新方案，不能自行提权或换位置。缺少安全隔离环境另行说明；同意安装不等于同意修改网络、安装容器或执行恶意样本。

## 2. 安装位置建议

| 内容 | Windows 建议位置 | 理由 |
|---|---|---|
| Python 包/venv | %LOCALAPPDATA%\AgentRuntimes\mobile-pdf-report\weasyprint-70.0\venv | 用户级专用环境，不污染系统 Python、其他项目和 Skill 目录 |
| 新 Python（仅现有无合适版本时） | 同一 weasyprint-70.0 目录下 python 子目录 | 使用官方管理器目标目录安装；不改其他解释器 |
| 新 MSYS2 | C:\Tools\mobile-pdf-report\msys64 | 专用、短 ASCII 本地路径；先核实写权限及 NTFS，不存在时才安装 |
| 配置/安装记录 | 同一运行时目录下 runtime-local.md | 记录版本、解释器和 DLL 路径，含本机信息，不提交 GitHub |

这些都是通用默认建议，不是作者机器上的私人路径。MSYS2 路径不要含空格、中文、链接、subst 或网络盘。若 C 盘权限/容量不适合，可在用户批准后选另一块本地 NTFS 盘的同类 ASCII 路径。复用已有 MSYS2 前要检查版本；会更新已有包时，必须把更新影响写入授权方案，不静默升级共享环境。

Linux 建议 venv 放 ${XDG_DATA_HOME:-$HOME/.local/share}/agent-runtimes/mobile-pdf-report/weasyprint-70.0/venv；macOS 建议 ~/Library/Application Support/AgentRuntimes/mobile-pdf-report/weasyprint-70.0/venv。此处路径变量由使用者环境展开，不硬编码用户名。原生库走用户同意的系统包管理器位置；虚拟环境不隔离系统包变更，也不是安全沙箱。

## 3. Windows 11 x64：获准后按序执行

### A. 选择 Python，确定变量

优先选已确认兼容且独立维护的 x64 CPython（例如已有 Python 3.12）；不要修改 Codex/其他应用自带解释器中的包。若只有应用自带解释器，需确认其用途和升级稳定性，不默认依赖它作为长期运行时。

如果没有合适 Python：从 [Python 官方安装说明](https://docs.python.org/3/using/windows.html) 指向的 python.org 或 Microsoft Store 安装 Python Install Manager（需要用户同意该应用安装影响）。使用其目标目录安装模式，例如获准后执行 pymanager install --target 【运行时根目录下的python绝对路径】 3.12。之后直接使用该目录的 python.exe，不依赖全局别名。此步骤需要网络；已有管理器时不重复安装，不使用 --force 覆盖现有运行时。

PowerShell 中由 Agent 填入已核实路径：

~~~powershell
# 以下路径占位符必须先替换；示例不是可直接整段执行的自动安装器。
$pdfSkillRoot = '【本 Skill 的绝对目录】'
$pdfBasePython = '【已确认的 x64 python.exe 绝对路径】'
$pdfRuntimeRoot = Join-Path $env:LOCALAPPDATA 'AgentRuntimes\mobile-pdf-report\weasyprint-70.0'
$pdfVenv = Join-Path $pdfRuntimeRoot 'venv'
$pdfMsysRoot = 'C:\Tools\mobile-pdf-report\msys64'
~~~

不要覆盖已有非本任务环境。每条外部命令检查退出码；任一步失败即停止后续安装并给出原因。

### B. Pango 原生库

按 [MSYS2 官方安装说明](https://www.msys2.org/docs/installer/) 选择当前稳定 x86_64 安装器，从官网指向的官方发布位置下载，并核对该版本官方 SHA-256（有可用签名验证条件时一并验证）。不要硬编码已经过期的下载版本或校验值。

确认批准目录可用且没有现存其他 MSYS2 后，可按官方 CLI 语法安装：

~~~powershell
$pdfMsysInstaller = '【已下载并校验的官方安装器绝对路径】'
& $pdfMsysInstaller in --confirm-command --accept-messages --root $pdfMsysRoot
if ($LASTEXITCODE -ne 0) { throw 'MSYS2 installation failed' }
~~~

若安装器或系统要求交互/管理员确认，按已批准范围办理，不能声称已自动完成。不要关闭杀毒、跳过证书验证或修改安全策略来绕过失败。

使用这个 MSYS2 实例的 **UCRT64 shell**，在批准范围内先完成该实例的正常更新，再安装 Pango。每条检查退出码；若更新要求关闭 shell，则关闭并重新进入同一实例后继续，不能只忽略提示。如果复用共享 MSYS2，此更新必须已获明确授权。

~~~sh
pacman -Syu
pacman -S --needed mingw-w64-ucrt-x86_64-pango
~~~

不要混用旧教程的 mingw64/bin 与本方案的 ucrt64/bin。检查已安装库真实位于：

~~~powershell
$pdfDllDir = Join-Path $pdfMsysRoot 'ucrt64\bin'
if (-not (Test-Path -LiteralPath (Join-Path $pdfDllDir 'libpango-1.0-0.dll'))) {
    throw 'Pango DLL is not ready'
}
~~~

WeasyPrint 的 Windows Python 库方案要求原生库，pip install 不能单独完成这一部分。依据：[WeasyPrint 官方 Windows 安装与 DLL 排错](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)。

### C. 专用 venv 中安装 Python 包

仅在虚拟环境不存在时创建；已存在时核对其解释器与用途，不能盲目重建。以下包安装命令只操作该 venv。所有路径与安装行为须已批准。

~~~powershell
& $pdfBasePython -m venv $pdfVenv
if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
$pdfPython = Join-Path $pdfVenv 'Scripts\python.exe'
& $pdfPython -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: -r (Join-Path $pdfSkillRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
& $pdfPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed' }
~~~

这里要求可用 wheel，避免无提示引入编译工具链。无匹配 wheel、网络不可达或证书错误时停止说明；不能自行安装编译器、换不明镜像或关闭 TLS 校验。可选 Markdown 包若需安装，也纳入用户批准的组件清单。

### D. 专用 DLL 配置与验证

使用 WEASYPRINT_DLL_DIRECTORIES 指向已验证的原生库目录；不要执行 setx 或持久修改全局 PATH。每次调用前在进程内设置，调用后恢复。1.0.2 包装器会将此变量保留到渲染子进程；其他无关凭据仍会过滤。

~~~powershell
$pdfOldDllDirs = $env:WEASYPRINT_DLL_DIRECTORIES
try {
    $env:WEASYPRINT_DLL_DIRECTORIES = $pdfDllDir
    & $pdfPython -m weasyprint --info
    if ($LASTEXITCODE -ne 0) { throw 'Native dependency check failed' }
    & $pdfPython (Join-Path $pdfSkillRoot 'scripts\check_dependencies.py')
    if ($LASTEXITCODE -ne 0) { throw 'Skill dependency probe failed' }
    # 实际生成时，也在此环境中使用同一 $pdfPython 调用安全包装器。
    # 不在这里自动开始渲染或直接调用 WeasyPrint 转换文件。
} finally {
    $env:WEASYPRINT_DLL_DIRECTORIES = $pdfOldDllDirs
}
~~~

--info 只作依赖诊断，不绕过资源安全包装器生成 PDF。不需要激活脚本，也不需要修改 PowerShell 执行策略。将确认的运行时路径写入私人 runtime-local.md，之后每次用相同解释器、相同 DLL 设置调用；不要写回 Skill、requirements 或发布仓库。

### E. 字体与隔离验收

只读确认系统已有可用中文字体；不因中文系统就假定渲染器一定能找到字体。缺字体时先说明拟安装字体、官方来源、许可证及用户级/系统级位置，经同意再安装。系统字体是运行时依赖；不要绕过素材规则用任意 @font-face 文件。

依赖 ready 只说明导入/API 可用，仍须在已验证的隔离环境中生成虚构中文样例，检查字形、文字提取、页面尺寸和无附件。本版按 README 披露的验证限制发布；安装成功不代表真实渲染验收通过。真实验收期间禁止网络、不挂载私人目录；下载和环境置备阶段与验收阶段分开。

## 4. Linux / macOS 分支

不要把 Windows 命令用于其他平台。先识别发行版、架构和已有 Python/Pango，复用可用组件；缺失安装须经过同样授权。

Debian 11+/Ubuntu 20.04+ 的原生依赖可按官方对应发行版指引使用 apt；一个适用于支持这些包名的环境的步骤是：

~~~sh
sudo apt update
sudo apt install python3-venv python3-pip libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
~~~

这会影响系统包，需在申请中明确列出；不默认执行整机 upgrade。其他发行版按 [WeasyPrint 官方平台步骤](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#linux) 查询本机适用包名，不猜测兼容性。

macOS 如已有 Homebrew，可在批准后安装 Pango 原生依赖（brew install pango）；Python 需先核实 >=3.10。不要用未指定版本的 brew install weasyprint 代替本 Skill 的 Python 70.0 基线。Homebrew 缺失时安装它属于额外变更，须说明后得到同意，不能偷偷引导安装。

随后在第 2 节选定的用户目录创建 venv，使用其绝对解释器执行 python -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: -r 【Skill目录/requirements.txt】，再执行 pip check、python -m weasyprint --info 和 scripts/check_dependencies.py。实际命令中的 python 必须替换为该 venv 的 bin/python，路径含空格时正确引用。不要使用 sudo pip 或升级系统 Python 包。若原生库仍不可见，按官方缺库排错定位，不自动写入全局环境。

这些分支是有来源的安装指引，尚未在本轮实际执行。依赖和原生库适配需在目标平台验证，不声称所有系统已支持。

## 5. 失败、记录与后续使用

- 网络失败：停止，说明下载受阻。不能声称 Skill ZIP 能离线补齐依赖；离线包需另按目标架构收集完整依赖及校验值。
- 用户未同意或安装失败：保留输入，不生成空白 PDF 冒充成功，也不改用不受控渲染路径。
- 成功记录：实际 Python/WeasyPrint/pypdf/Pango 版本、路径、安装来源、退出码、探针结果和剩余验收；真实路径/安装日志只留本机。
- 不自动卸载旧运行时、清理其他环境或删除安装记录。后续升级须重新核对兼容性与资源安全验收。
