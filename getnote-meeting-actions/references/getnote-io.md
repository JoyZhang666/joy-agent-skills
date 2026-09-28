# Get 读取、归档与核验

已核对接口：官方 Get CLI 1.5.10，契约 2.2。先使用宿主当前的官方 CLI；参数有变化时检查对应 `--help`，不自动升级。Windows 常用 `getnote.cmd`，Python 辅助脚本可通过 `--cli` 指定其绝对路径。Python 3.10+，仅标准库。

## 解析与读取

```text
getnote capabilities -o json
getnote kbs --scope DEFAULT -o json
getnote search "指定会议标题" --kb VERIFIED_TOPIC_ID --limit 5 -o json
getnote note VERIFIED_NOTE_ID -o json
getnote note original VERIFIED_NOTE_ID -o json
getnote note transcript VERIFIED_NOTE_ID -o json
getnote note todos VERIFIED_NOTE_ID -o json
getnote note timeline VERIFIED_NOTE_ID -o json
getnote note quick-note VERIFIED_NOTE_ID -o json
```

只读已指定会议及完成其行动所需资料。查找时先列候选，唯一且语义吻合的结果可直接用；同名不猜。`note_id`、`topic_id` 全程为字符串。真实详情中的 `note_url` 才是结果链接；CLI 的 `task` 指异步保存任务，不是业务待办。

每条 API 命令必须同时检查退出码和 `success=true`。非 JSON 输出、超时、鉴权错误或 `success=false` 不是空内容。原文读取失败时不得静默用摘要冒充成功。

读取辅助命令（`SKILL_DIR` 为本技能目录，路径含空格时加引号）：

```text
python SKILL_DIR/scripts/read_meeting.py --note-id VERIFIED_NOTE_ID --out NEW_SNAPSHOT_DIR
```

默认 `--mode auto`：`plain_text`、`link`、`img_text` 走 original；其他类型或带 audio 数据走 transcript。类型不准确时可显式选择 `--mode original` 或 `--mode transcript`。空原文而存在正文时输出 `summary_only`；接口错误则失败，不静默降级。只有已明确接受摘要范围时才用 `--mode summary`。`--with-context` 额外读取 timeline 和 quick-note，缺失时记录警告。

输出包括 `raw/`（请求返回及退出状态）、`source.txt`（原字符串，无改写）、`metadata.json`（ID、类型、内容来源、范围、字符/行数、哈希、读取前后版本）。目标目录必须不存在，避免覆盖快照。脚本在读取后再次核对笔记版本；变化时退出失败，保留证据并在新目录重读。

脚本保留返回的原文格式，不试图猜测所有转写格式中的说话人。Agent 阅读原文并按段给出处；全量 JSON/文本留在本地，不需要在聊天展示私密全文。身份和时间戳缺失时不补造。

`data.meeting_todos` 在当前版本可为 `{ "source": "summary_markdown_rules", "items": [] }`，并非始终是数组。空 `items` 也须读取全文。时间线和快捷记录的结构保留原样，不虚构支持字段。

## 本地保存是默认终点

生成本地 `actions.json` 和可读清单；产生执行成果时另存完整的 `result.md`，包含原会议标题/链接、来源范围、批次编号、行动状态、已完成结果、可发送正文、未完成原因和下一步。`.ics` 等专用文件留本地并提供可点击入口。不需要成果知识库也能完成本地交付，不为完成流程主动上传。

## 可选：获明确授权后上传 Get

只有满足以下条件才能运行后面的保存命令：

1. 用户明确要求上传具体清单或成果；或者 Agent 确有必要时，先完成可审查的本地稿，说明目的、内容和目标，再获得用户明确同意。认为上传有必要不等于已经获准，也不例行询问每次是否上传。
2. 核对授权的会议/批次、内容范围与目标，记录用户原话。已配置知识库只帮助确定位置。上传稿只包含获准的必要内容；不附带整场转写、无关成果、凭据或额外附件。仅要求上传清单，不代表授权执行清单中的任务。
3. 写入前核对授权仍有效，将最终上传文件、SHA-256、标题、目标 `topic_id` 和幂等键记录在 `batches[].archive`。用户明确提前授权执行后上传的约定成果无需重复申请；更换接收目标或扩大内容范围需取得覆盖变更的授权。

没有有效授权时不调用 `save`、`note update` 或其他上传入口。尚未提交的批次保持 local_only/awaiting_consent/declined；已提交请求保留真实的 pending/uncertain/verified 等状态，仅只读查证，不补传或重试。历史授权证据缺失时在 history 记录缺失，不补造授权状态。用户只说“保存一下”“继续”“全部做”不能脱离上下文解释成新增上传许可；如果回复明确是在同意一项已展示内容与目标的上传申请，则按该申请范围记录。未回复或含糊回复不构成同意。

每个授权批次创建一篇独立笔记，不覆盖原会议。内容型成果写入正文；附件另需相应授权及可用接口支持，未上传时明确“附件仅保存在本地”，不把本机路径当作云端可访问附件。若全文超限或重要附件缺失，保留完整本地稿，不能声称云端完整交付。

已尝试保存的批次其正文与幂等键保持不变；后续工作产生新批次并重新核对授权范围。可用 UUID 生成幂等键，无需在通用技能内保存个人 ID。

```text
getnote save --content-file RESULT_FILE --title RESULT_TITLE --topic-id VERIFIED_TOPIC_ID --idempotency-key PERSISTED_BATCH_KEY -o json
getnote task RETURNED_TASK_ID -o json
getnote note RETURNED_NOTE_ID -o json
getnote note original RETURNED_NOTE_ID -o json
getnote kb VERIFIED_TOPIC_ID -o json
```

`getnote task` 仅在保存返回待处理或结果不确定时查询。没有任务 ID 时检查原请求证据和目标库最近结果，不重新创建。无法确认原操作是否完成时，归档保持 `uncertain`，不盲重试。

结果验收必须满足：

1. 退出码 0、`success=true`、非空字符串 `data.note.note_id/title/note_url`。
2. 用 `original` 回读，与本地正文比较。仅统一 CRLF/LF，不去除文字、段落或空白来掩盖截断；任何其他差异先核查，未证明完整不通过。
3. 回读目标知识库直到找到该字符串 ID 或查完全部；当前 CLI 用 `getnote kb VERIFIED_TOPIC_ID --all --no-content -o json` 自动翻页并省略其他笔记正文，不凭首页缺失判断失败。目录被指定时再核对真实目录归属。
4. 记录真实返回、回读哈希、归属证据，再标记批次归档 `verified`。

当前 `note update` 没有 `--content-file` 或增量追加语义，本技能不以覆盖原会议方式模拟追加。原会议不更新；相同批次只保存一次。读取成功但归档失败，不撤销已完成的本地工作。

## 可选的只读回读工具

保存命令运行后，将实际退出码及 stdout 解析出的 JSON 包装为 `receipt.json`，结构为 `{ "exit_code": 0, "payload": { "success": true, "data": {} } }`，其中 data 必须是原命令完整返回，不能填示例空对象或自行构造成功字段。

```text
python SKILL_DIR/scripts/verify_result.py --receipt RECEIPT_FILE --content-file RESULT_FILE --topic-id VERIFIED_TOPIC_ID --out NEW_VERIFICATION_DIR
```

[verify_result.py](../scripts/verify_result.py) 只读 Get，不保存或重试创建。它拒绝 pending/非零退出的保存回执，比较回读原文（仅允许 CRLF/LF 差异），并读取指定知识库确认成员关系。输出独立验证记录；状态未到 verified 就不能声称归档验收完成。

保存回执可能包含正文，验证目录可能包含库内其他笔记的标题/ID，这些均留在本地运行目录，不打包进通用技能或公开报告。
