# 多 Agent CRM

多个 AI 助手可以共同维护一份客户台账。一个助手创建商机，另一个查询最新进展、更新阶段或登记下一步行动。如果两个助手同时修改同一版本，系统会提示后提交的一方重新核对；通过审计记录，可以查到谁在什么会话中、依据什么来源做了修改。

本版为 **0.1.0-rc1**。数据模型包括组织、联系人、产品、销售阶段、商机、行动、来源和审计八张表。[数据结构与字段](DATA-MODEL.md) · [机器可读结构](schema.json) · [Agent 使用手册](SKILL.md)

## 没有云服务器怎么用？

| 使用场景 | 部署方式 | 运行条件 |
|---|---|---|
| 多个 Agent 在同一台电脑 | 每个 Agent 使用自己的身份和会话，共用本机的协调器和数据库。协调器负责给写入请求排队。 | 使用 SQLite 可离线工作，电脑运行即可。 |
| 多个 Agent 在不同电脑 | 选一台常开的办公电脑作为协调主机，SQLite 文件放在它的本地磁盘。其他设备通过你已配置的身份验证连接，在这台主机上调用命令。 | 协调主机须在线。已入队的请求在重启后保留；断线设备须保存尚未提交的意图，恢复后重新核对。 |
| 希望办公电脑关机后仍可使用 | 可将同一套程序放到一台受信任的常开服务器。 | 租用云主机是可选项。 |

同一份 CRM 的所有写入应经过同一个协调器。把 SQLite 文件放入网盘同步目录、各机各建协调库，都会失去统一的排队顺序。当前版本需要另行配置跨机访问，不提供自动故障切换或离线多端合并。本机 SQLite 和同机双 Agent 写飞书已实测；跨机网络部署尚未实测。

## 第一次使用：在本机登记一条虚构客户记录

准备 Python 3.10 或以上版本。在技能包之外建立仅供指定系统用户访问的私有工作目录，用来存放数据库、密钥、请求文件、映射及备份。下列命令假设当前目录中可以找到 `crm.py`；在私有工作目录执行时，请将它换成脚本的完整路径。

**1. 管理员初始化数据库，为两个 Agent 分别登记身份。**

```text
python crm.py --db workspace.sqlite init
python crm.py --db workspace.sqlite register operator-a --key-file operator-a.key
python crm.py --db workspace.sqlite register operator-b --key-file operator-b.key
```

**2. 在各自会话中选择身份，读取手册，再查询组织。** 将 `CRM_ACTOR`、`CRM_KEY_FILE` 和 `CRM_SESSION` 分别设为该 Agent 的登记名、自己的密钥文件路径和真实会话标识。PowerShell 可用 `$env:CRM_ACTOR='operator-a'`，其他变量用相同方式设置；在 POSIX 系统中使用 `export`。能够直接修改协调库的系统账号也能绕过命令行检查，请限制该主机上的文件与终端权限。

```text
python crm.py --db workspace.sqlite handbook
python crm.py --db workspace.sqlite query organizations
```

**3. 先预检，再按授权提交。** 在私有工作目录将以下内容以 UTF-8 保存为 `example.json`。新建记录时，预期版本填 `0`，预期哈希填 `null`。

```json
{"request_key":"example-create-1","kind":"organizations","id":"org-example","expected_version":0,"expected_hash":null,"fields":{"name":"示例工坊"},"source_ref":"synthetic-example-1"}
```

```text
python crm.py --db workspace.sqlite sync example.json --dry-run
```

获得该项业务授权后，将 `--dry-run` 换成 `--authorization` 加实际批准记录的引用。提交后分别回读业务和审计。

```text
python crm.py --db workspace.sqlite query organizations org-example
python crm.py --db workspace.sqlite history organizations org-example
```

更新时使用刚查到的版本和哈希，只填写要改的字段。每个新意图使用新请求键；同一请求断线后，用原身份、原键续接。队首请求待处理时，后续写入排队。远端结果不明确时，先核对业务和审计，必要时交管理员处理。

## 使用飞书多维表格

准备独立空白测试库、已登录的飞书用户和官方命令行工具。初始化八张表，将返回的映射保存在技能包外，再用 `init --feishu-config` 指定映射文件，新建对应的协调库。飞书模式需要网络。审计中的 Agent 身份与访问飞书 API 的登录账号分别记录；多个 Agent 可在同一飞书用户授权下协作。[飞书配置步骤](FEISHU.md)

请成对备份协调库和飞书映射。丢失协调库会丢失请求归属、队列状态和本地审计索引。直接编辑飞书表格或让另一个协调器写同一份数据，都可能产生并发冲突。

本技能采用 [MIT 许可证](LICENSE)。
