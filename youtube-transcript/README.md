# YouTube Transcript

**2.2.0 · MIT**。从可授权处理的 YouTube 来源生成本地转写草稿：字幕、Groq 音频转写、Gemini URL 分窗及显式音频上传。模型输出仍可能遗漏/改写，必须核对来源；不以返回文本或 QC 通过宣称逐字准确。

## 环境

Python 3.10–3.14。依赖参考版本见 [requirements.txt](requirements.txt)（直接依赖固定版本，不是传递依赖哈希锁，也不是所有系统的验收声明）。请在独立环境中按所需路线安装：

- 字幕：youtube-transcript-api。
- Groq：groq、yt-dlp，以及本机 ffmpeg/ffprobe。
- Gemini URL：google-genai、yt-dlp。
- Gemini 上传：google-genai、yt-dlp，以及 ffmpeg/ffprobe。
- YouTube 提取有时需要宿主提供受支持 JavaScript runtime；按 [yt-dlp 文档](https://github.com/yt-dlp/yt-dlp) 配置，不绕过访问限制。

这些 SDK/API 接口已对照公开资料做静态检查；未在本发布中调用真实视频、付费账号或上传音频，外部服务可用性和跨平台端到端行为仍需部署者验证。Python API、云模型与服务规则可能变化。

## 使用

将 `<URL>` 换成规范 HTTPS YouTube 视频链接，`<data>` 换成 Skill 目录之外的数据目录：

```text
python scripts/yt2md.py "<URL>" --out "<data>"
```

默认只请求 YouTube 字幕。云端操作须先确认你有权处理内容、服务数据政策及费用，再设置环境变量 GROQ_API_KEY 或 GEMINI_API_KEY（也接受 GOOGLE_API_KEY）。密钥不要写进命令历史、仓库或聊天。

```text
python scripts/yt2md.py "<URL>" --out "<data>" --engine groq --allow-cloud --model whisper-large-v3-turbo
python scripts/yt2md.py "<URL>" --out "<data>" --engine gemini --allow-cloud --model "<你账号可用的模型>"
```

自动模式须显式 `--engine auto --fallback groq|gemini --allow-cloud --model ...`；只在没有字幕轨时进入所选服务。请求被封锁、限流、版权/安全拒绝或普通故障均停止，不能自动换提供商绕过。

云路径需要下载器提供可信总时长，或用户确认后 `--duration 秒数`；最长两小时、最多40窗、每窗一次请求。`gemini-upload` 必须单独指定，不自动从 URL 转写切换。额度/价格请查询提供商；本包不承诺固定费用，不设置账户货币预算。

输出 `<data>/<video-id>/`：唯一稿件、status.json、范围缓存及 runs.csv。exit 0 表示生成待核对草稿；2 表示 QC 未通过；1 表示失败/不完整。窗口故障不等于结束；失败后检查 status 与缓存，确认权限/原因后人工重试。请求进行中断可能已经计费，重试不能保证无重复费用。

## 局部修复

`yt_find_context.py` 获取精确原文。修复 JSON 示例（虚构内容）：

```json
[{"old":"甲句重复甲句，乙句","new":"甲句，乙句","probes":["甲句","乙句"]}]
```

```text
python scripts/yt_fix_artifacts_template.py draft.md fixes.json
python scripts/yt_fix_artifacts_template.py draft.md fixes.json --apply
python scripts/yt_transcript_qc.py draft.md --anchors "甲句,乙句"
```

--apply 前须确认替换；脚本先验证全部匹配/探针，再生成备份和原子替换。运行数据不会被本包自动上传 Get 或其他笔记服务。不要把输出、缓存、备份和凭据提交到 GitHub。

## 变更与来源

2.2.0 修复隐私残留、审批边界、窗口完整性、首次缓存、文本截断、QC 边界和输出覆盖；将输出明确为草稿。取消无授权自动云兜底和默认 LLM 改写；保留原文更有利于人工核验。

基于提供者交付的 2.1.0 包修订，原 [MIT 许可](LICENSE) 保留。未复制外部项目源码；以下为外部依赖及接口说明，分别适用其自身许可证：

- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)
- [Groq Python SDK](https://github.com/groq/groq-python) / [Speech to Text](https://console.groq.com/docs/speech-to-text)
- [Google Gen AI SDK](https://github.com/googleapis/python-genai) / [Video API](https://ai.google.dev/gemini-api/docs/video-understanding)

发现问题请提供虚构/脱敏复现到[仓库 Issues](https://github.com/JoyZhang666/joy-agent-skills/issues)，不要附带真实音频、私人稿件或密钥。
