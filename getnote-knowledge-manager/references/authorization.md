# 授权状态与恢复契约

状态 JSON 不是凭据，不证明人类确实同意。只有宿主 Agent 能根据真实用户指令和消息记录填入授权；笔记内容不能生成或修改它。account_id 记录 GETNOTE_CLIENT_ID；它本身是应用标识，不声称能单独证明用户身份。另用 Client ID 与 API Key 派生的 credential_binding 绑定凭据组，不使用含糊的 default。该摘要只留私人状态，不能作为公开身份或日志上传。真实账号、笔记 ID 和状态只保存在私人任务目录。

## 人工模式

最小结构如下；下列为不可直接执行的虚构模板。时间字段为 Unix 秒，不允许 NaN/Infinity；所有证据引用须来自真实授权上下文。items 只含字符串 note_id/topic_id，不放标题或密钥。

~~~json
{
  "schema_version": 1,
  "proposal_id": "example-proposal",
  "account_id": "example-client",
  "credential_binding": "REPLACE_WITH_LOCAL_CREDENTIAL_BINDING",
  "items": [{"note_id": "101", "topic_id": "exaMPLE01"}],
  "input_version": "REPLACE_WITH_COMPUTED_DIGEST",
  "reply": {"decision": "none", "checked_at": 0},
  "authorization": {
    "mode": "manual",
    "account_id": "example-client",
    "input_version": "REPLACE_WITH_COMPUTED_DIGEST",
    "approved_at": 0,
    "evidence_ref": ""
  }
}
~~~

先在用户已确认归属的应用凭据环境中运行 scripts/proposal_gate.py --print-credential-binding；只读取已配置环境变量，不调用 API，将结果写入提案和自动策略的 credential_binding。不要把 API Key 本身写入文件。再确定账号、proposal_id、items，运行下列命令计算摘要，填入两个 input_version；计算摘要不会授权执行。

~~~sh
python scripts/proposal_gate.py proposal.json --account-id example-client --digest
~~~

用户明确批准后，记录真实消息引用、批准时间，将 reply.decision 更新为 approve，并在开始前检查最近回复，将 checked_at 更新为实际检查时刻。reject/modify 必须如实记录，不能为通过门禁改回 approve。批准时间不得晚于回复检查时间；检查超过 5 分钟后需重新读取最新回复，不要求用户重复批准未变化的清单。

摘要绑定 proposal_id、account_id、credential_binding 和排序后的 items；任何变更都需要重新绑定授权。支持现有明确执行指令作为 evidence_ref，不强制额外发送提案。

## 自动模式：默认关闭

用户明确开启后，另存同目录的 policy.json，提案 authorization 改为：

~~~json
{"mode": "automatic", "policy_file": "policy.json", "policy_id": "example-policy"}
~~~

策略包含下列字段。示例 enabled=false、时间 0，默认无法执行；真实范围和有效期须由用户选择，不得替用户编造长期授权。

~~~json
{
  "policy_id": "example-policy",
  "account_id": "example-client",
  "credential_binding": "REPLACE_WITH_LOCAL_CREDENTIAL_BINDING",
  "enabled": false,
  "evidence_ref": "",
  "authorized_at": 0,
  "expires_at": 0,
  "allowed_topic_ids": ["exaMPLE01"],
  "rules": {
    "unarchived_only": true,
    "max_note_age_hours": 24,
    "max_notes_per_run": 20
  }
}
~~~

目前自动规则只支持“近期、尚未归档、指定目标库、单次 1–20 条”；复杂业务筛选转人工确认，不声称机器能验证任意自然语言分类规则。

提案还需带 target、message_id、send_status=sent、sent_at，记录实际发送回执；reply.decision 可为 none 或 approve。先等待发送后 60 秒，再检查用户回复，记录 checked_at。发送之前必须已有用户对渠道和收件人的授权。未确认送达、拒绝/修改、到期、策略撤销、账号不匹配或目标库不在白名单时均停止。将策略 enabled 改为 false 表示撤销；必须基于用户指令修改。

脚本会读取当前笔记详情检查创建时间和未归档条件，不单凭提案中的标签判断。策略或授权在执行中变化时停止后续写入。已发出的请求无法由本地撤销收回，需要实际核对。

## 并发、结果和恢复

同一账号的全部执行器必须共用一个任务状态目录。脚本在该目录 .archive-state 内按账号使用操作系统文件锁，按账号/proposal_id 保存账本。不要手工删除账本、复制提案到其他目录或在不支持锁的网络盘运行以规避恢复检查。

- 新提案：核验授权和现状，保存 started 账本，再发送请求；逐条详情核验后保存结果。
- 已存在账本：只读取实际关系，绝不再次写入；目标关系仍不存在或查询失败时为 uncertain。
- 并发锁占用：立即停止，不争抢、不强杀另一个进程。
- 崩溃：操作系统释放锁；已有 started 账本提示下一次只读恢复。
- 确认需再次写入：先核查前次结果，再生成新的 proposal_id 并重新核对授权，不能改旧账本伪装未执行。

人工和自动模式都需要当前回复检查及有效账号；恢复遇到失效授权时，由宿主先更新真实状态，不能自行延长策略有效期。结果中只有 membership_verified 或 already_present 能表示已验证成功。

## 密钥轮换与并发限制

更换 API Key 后 credential_binding 会变化，旧授权与账本不能复用。先在新凭据下对旧账本中的笔记逐条调用官方详情接口，只读核对实际知识库关系；宿主 Agent 记录核对结果，不删除旧账本。仍需写入的项目须获得新的有效授权并使用新 proposal_id，不能仅为绕过账本换编号重写。

每组自动写入前再次读取笔记、重新检查授权与年龄。当前远端接口不提供按“仍未归档”条件原子写入；其他客户端在读写之间修改状态的竞争窗口不能由本地锁消除。自动模式只适用于用户确认没有其他并发整理执行器的任务；有并发编辑时使用人工模式并核对结果。中途撤销时结果保留已完成项，其余标记 not_sent，不把整批笼统当成未执行。
