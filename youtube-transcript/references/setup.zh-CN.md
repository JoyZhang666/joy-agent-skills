# 新手安装与 API 配置指南

适用版本：2.2.1。官方资料核对日期：2026-09-28。以下以 Windows PowerShell 为主，按钮名称与费用以账号当前页面为准。顺序：选路线 → 安装 → 免费字幕 → 按需配置 API → 找到全文稿。

## 1. 先选路线

API 是程序调用服务的接口，API Key 是访问密钥。本项目免费开源，不代表第三方服务永远免费。下面的难度是面向新手的判断，综合账号申请与本机准备，价格单位为美元。

| 顺序 | 申请和准备难度 | 费用与建议 |
|---|---|---|
| ① 已有字幕 | 最简单，不申请密钥 | 无 AI API 费用；有可用字幕先选它 |
| ② Groq whisper-large-v3-turbo | 申请较简单，本机需音频工具 | 先看免费额度；标准付费参考 **$0.04 / 音频小时**，推荐的低成本语音路线 |
| ③ Groq whisper-large-v3 | 同一个 Groq 密钥 | 标准付费参考 **$0.111 / 音频小时**；可用于对准确率更敏感的内容，仍需核对 |
| ④ Gemini 视频链接 | Google 账号、项目、地区资格；需 yt-dlp 取时长 | 部分模型有免费层；付费按输入/输出 token 计算，没有统一每小时价，适合已有 Google API 条件者 |

默认建议：字幕 → Groq Turbo。Gemini 在免费额度内可能更省钱，但账号和用量规则较复杂，不能断言必然更贵。不必同时申请两家。

Groq 单价来自[语音转写官方表](https://console.groq.com/docs/speech-to-text)：30 分钟标准付费估算约 $0.02 / $0.0555，不含税费、重试与其他服务。免费额度有限，见[限流说明](https://console.groq.com/docs/rate-limits)。

Gemini [价格表](https://ai.google.dev/gemini-api/docs/pricing)区分模型与输入类型。例如 gemini-2.5-flash Standard：每百万输入 token 文本/视频 $0.30、音频 $1.00，输出（含思考）$2.50；实际以所选路线和账单为准。[YouTube URL 功能](https://ai.google.dev/gemini-api/docs/video-understanding)处于预览且有特定免费说明，不等于所有输出、音频上传或未来请求都免费。

## 2. 下载与安装

### 下载项目

1. 打开[仓库首页](https://github.com/JoyZhang666/joy-agent-skills)，点 **Code → Download ZIP**，无需 GitHub Windows 客户端。
2. 对 ZIP 右键“全部解压”，进入 `joy-agent-skills-main`，再进入 `youtube-transcript`。
3. 应看到 README.md、SKILL.md、requirements.txt、scripts，不要只下载 README。
4. 在此文件夹的资源管理器地址栏输入 `powershell`，回车。下面命令在此窗口逐段执行。

### Python 与独立环境

```powershell
py -3 --version
```

显示 Python **3.10–3.14** 可以继续。找不到命令时，从 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/)安装此范围的版本，例如适合本机架构的 3.14 安装包；重开终端再检查。固定字幕依赖不支持 3.15+。若装了多个版本，先用 `py -3.14 --version` 确认，再将下一条命令中的 `py -3` 换为 `py -3.14`。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "youtube-transcript-api==1.2.4"
$env:Path = "$PWD\.venv\Scripts;$env:Path"
```

无错误并显示安装成功即可。这里直接使用环境内的 Python，不需要 Activate.ps1，也不必修改执行策略。每次重开终端，先回到此文件夹，再运行 `$env:Path = ...` 那一行。`.venv` 不要上传或发送。

macOS/Linux：用受支持的 `python3 -m venv .venv`，然后 `source .venv/bin/activate`；将下文 `.\.venv\Scripts\python.exe` 改为 `python`，路径和环境变量命令改为本机格式，参考 [Python 官方使用文档](https://docs.python.org/3/using/index.html)。后文可照做步骤针对 Windows。

## 3. 免费字幕首次试跑

选一个你有权处理、确认有字幕的 **1–3 分钟短视频**，将引号内中文换成真实完整链接，保留引号：

```powershell
.\.venv\Scripts\python.exe scripts\yt2md.py "这里换成完整的视频链接" --out "..\transcript-output"
```

无需 API Key 或 YouTube Data API。程序在项目旁边创建保存目录；成功会显示 `output` 路径和 `generated-needs-review`（等待人工核对）。没有字幕再考虑 Groq；限流或访问受限则先停止查明原因，不能以换服务绕过。

## 4. Groq：从申请到运行

### 4.1 注册与密钥

1. 打开 [Groq Console](https://console.groq.com/)，按页面方式注册/登录，完成验证及条款确认。
2. 进入 [API Keys](https://console.groq.com/keys)，找 **Create API Key** 或同义按钮。名称可填 `youtube-transcript-local`；需要项目时选自己的项目。
3. 创建后复制密钥，保存到自己的密码管理器。不要贴到聊天、代码、README 或群里。
4. 检查账号计划及剩余额度，先用免费额度。升级由你自己决定，付款方式见 [Billing FAQ](https://console.groq.com/docs/billing-faqs)。
5. 已付费且有组织所有者权限时，可在 **Settings → Billing → Limits → Add Limit** 设置自己能接受的月额度和提醒，保存。用量更新有延迟，不保证绝不超额，见[限额说明](https://console.groq.com/docs/spend-limits)。

申请与环境变量方式参考 [Groq 官方入门](https://console.groq.com/docs/quickstart)。布局变化时找 API Keys 页面，不要只停留在聊天 Playground。

### 4.2 私密配置到本机

在项目 PowerShell 执行下列命令；提示出现后才粘贴真实密钥并回车，输入会遮蔽。**不要把密钥替换进代码行里。**

```powershell
$env:GROQ_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host '请粘贴 Groq API Key，输入隐藏' -AsSecureString)).Password
.\.venv\Scripts\python.exe -c "import os; print('Groq: 已设置' if os.getenv('GROQ_API_KEY') else 'Groq: 未设置')"
```

“已设置”只表示当前进程能读到值，不代表密钥有效、余额充足或服务连通；后面的短视频试跑才验证真实调用。此窗口关闭后失效，下次重新输入即可。不要打印变量值排错，脚本不会自动读取 `.env`。

需要长期保存时：开始菜单搜索“编辑账户的环境变量”→ 用户变量 → 新建，变量名 `GROQ_API_KEY`、变量值填密钥，保存后重开终端/Agent。值以可读形式保存在账户环境，并会传给后续子进程；共享电脑建议用临时方式。另一个 Agent 进程不会自动继承当前终端的临时变量。

### 4.3 音频工具

```powershell
.\.venv\Scripts\python.exe -m pip install "groq==1.7.0" "yt-dlp[default]==2026.8.19"
```

FFmpeg 和 ffprobe 不是同名 Python 包，按下面安装：

1. 打开 [FFmpeg 官方下载页](https://ffmpeg.org/download.html)，选 Windows，进入页面列出的构建站点，例如 gyan.dev。
2. 下载适合本机的 release essentials ZIP，解压到自选工具目录，找到同时含 ffmpeg.exe 和 ffprobe.exe 的 **bin** 文件夹，复制完整路径。
3. Windows“编辑账户的环境变量”→ 用户变量 **Path → 编辑 → 新建**，粘贴 bin 路径；不要覆盖原有 Path。
4. 重开项目 PowerShell，重设第 2 节的 `.venv` PATH 和临时 API Key，再检查：

```powershell
yt-dlp --version
ffmpeg -version
ffprobe -version
```

三条应显示版本。YouTube 提取可能还需要 JavaScript 运行时，见 [yt-dlp 依赖](https://github.com/yt-dlp/yt-dlp#dependencies)。可按 [Deno 官方指南](https://docs.deno.com/runtime/getting_started/installation/)安装；选择其 Windows WinGet 方法时：

```powershell
winget install DenoLand.Deno
```

重开终端，运行 `deno --version` 确认可找到。没有 WinGet 时按官方指南其他方法操作，不必为此修改安全策略。

### 4.4 首次语音转写

确认同意把该视频音频交给 Groq，且已了解费用后：

```powershell
.\.venv\Scripts\python.exe scripts\yt2md.py "这里换成完整的视频链接" --out "..\transcript-output" --engine groq --allow-cloud --model whisper-large-v3-turbo
```

先用短视频检查文本及控制台用量。要试另一模型，只将最后模型名改为 `whisper-large-v3`，密钥不变。转写保留原语言，不自动译成中文。

## 5. Gemini：按需选择

Groq 已满足需要可跳过本节。

### 5.1 申请并核对计划

1. 先看[支持地区及账号条件](https://ai.google.dev/gemini-api/docs/available-regions)，用自己的 Google 账号打开 [AI Studio API Keys](https://aistudio.google.com/api-keys)。不符合资格时停止。
2. 完成首次确认。已有自动创建项目/密钥时选自己的项目查看；否则找 **Create API key**，按提示选择或创建项目，名称可填 `youtube-transcript-local`。
3. 按钮不可用时核对项目权限，组织账号找管理员，不借用别人密钥。[官方密钥指南](https://ai.google.dev/gemini-api/docs/api-key)列出权限和当前密钥类型；使用 AI Studio 正常创建的密钥，不手动取消 API 限制。
4. 复制到自己的密码管理器。检查项目 Free Tier / Paid Tier 和模型额度，网页聊天可用不代表 API 配额可用。
5. 免费层够用先不绑定付款。决定升级时，按项目 **Set up billing / Upgrade** 提示办理，可能涉及付款方式或预付余额，先读[结算说明](https://ai.google.dev/gemini-api/docs/billing)。按账号实际选项设额度/提醒，付款由自己操作。

免费/付费的数据使用政策可能不同，使用前读[服务条款](https://ai.google.dev/gemini-api/terms)，不要用敏感音视频首次测试。

### 5.2 私密配置与安装

```powershell
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host '请粘贴 Gemini API Key，输入隐藏' -AsSecureString)).Password
.\.venv\Scripts\python.exe -m pip install "google-genai==2.25.0" "yt-dlp[default]==2026.8.19"
.\.venv\Scripts\python.exe -c "import os; print('Gemini: 已设置' if os.getenv('GEMINI_API_KEY') else 'Gemini: 未设置')"
```

本项目优先取 `GEMINI_API_KEY`，没有时取 `GOOGLE_API_KEY`，建议只设一种。长期保存步骤与 Groq 相同，只换变量名。不要填入 Groq 密钥；“已设置”仍不是连通证明。

### 5.3 选模型与试跑

查[官方模型目录](https://ai.google.dev/gemini-api/docs/models)，确认支持视频输入、文本输出及当前账号访问，复制 **model ID** 而非展示名称。本项目用 `generate_content`，模型需支持此接口；先考虑符合条件的 Flash 系列，不默认选更贵的 Pro。

以下用价格页仍列出的 `gemini-2.5-flash` 举例，以你账号当前可用性为准，不保证永远可用：

```powershell
.\.venv\Scripts\python.exe scripts\yt2md.py "这里换成完整的视频链接" --out "..\transcript-output" --engine gemini --allow-cloud --model gemini-2.5-flash
```

URL 路线仍用 yt-dlp 取时长，必要时按 4.3 安装 Deno。不要把 `--duration` 随意写小跳过视频；只有查证真实总秒数后才可提供。

进阶音频上传：装好 FFmpeg，将 `--engine gemini` 改成 `--engine gemini-upload`，确认模型支持音频输入。该路线上传音频，不是免费自动备用路线；远程清理失败时根据 `remote-upload.json` 的 pending 记录及提供商文件管理方式处理，不能宣称已删除。

## 6. 找到并核对全文稿

1. 查看终端 `output`，打开上一级 `transcript-output` 中对应视频 ID 文件夹。
2. 用文本/Markdown 编辑器打开 `draft-....md`，应有来源、路线及正文，不是摘要。
3. 对照视频检查开头、中间、结尾、分片边界，数字和专有名词逐项核对；局部修复见 [README](../README.md)。
4. `status.json` 中 `generated-needs-review` 是待核对、`qc-failed` 是启发式告警、`incomplete` 是未完成，不要把旧稿当成本次失败任务成果。
5. 核对后可另存易懂的名字；不要把私人稿件、音频、缓存或密钥上传 GitHub。

已经理解费用与权限后，可选“无字幕才用 Groq”的自动模式：

```powershell
.\.venv\Scripts\python.exe scripts\yt2md.py "这里换成完整的视频链接" --out "..\transcript-output" --engine auto --fallback groq --allow-cloud --model whisper-large-v3-turbo
```

访问失败、限流或普通故障不会触发换路。

## 7. 遇到问题时

脚本避免打印完整提供商异常；错误类型与 status.json 是定位线索，不能单凭它断言是余额或密钥问题。

| 现象 | 处理步骤 |
|---|---|
| 找不到 Python / ModuleNotFoundError | 回到项目目录，核对版本，使用同一 `.venv` Python 安装和运行 |
| 找不到 yt-dlp / ffmpeg / ffprobe | 重开终端，重设 `.venv` PATH；FFmpeg Path 应指向 bin，逐个检查版本 |
| Key 显示未设置 | 在运行脚本的同一终端输入；独立 Agent 进程不自动继承本窗口的临时变量 |
| AuthenticationError / 401（若平台显示） | 检查服务、撤销状态、项目；不发送密钥 |
| 429 / 额度限制 | 查控制台速率、用量与计划，等待或自己决定调整计划，不自动升级和反复重试 |
| 模型不存在 / 403 | 查 model ID、输入能力、权限与地区，不随意换更贵模型 |
| YouTube 提取或 JS 失败 | 查官方提取器说明及 Deno；访问受限时停止，本脚本无 Cookie 登录配置流程 |
| FileExistsError 且有 runner.lock | 确认是否仍有任务运行；确认崩溃且无写手后才处理遗留锁 |
| incomplete / 只有缓存 | 先查失败原因；部分内容不是全文。Gemini URL 同配置可续接，其他路线可能重做并计费 |
| 有稿但文字不准 | generated-needs-review 不是准确性认证；对照来源修复，或明确授权后比较模型 |

求助时提供系统、Python 版本、路线、脱敏错误类型和状态值即可，不要发密钥、变量值截图或私人全文稿。

本教程经文档及命令路径检查，未替用户开户、安装依赖、付款或调用真实视频/API；真实使用以首次短视频验收为准。
