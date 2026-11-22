# 多 Agent CRM

多个 AI 助手可以共同维护一份客户台账。一个助手创建商机，另一个查询最新进展、更新阶段或登记下一步行动。如果两个助手同时修改同一版本，系统会提示后提交的一方重新核对；通过审计记录，可以查到谁在什么会话中、依据什么来源做了修改。

本版为 **0.1.0-rc1**。数据模型包括组织、联系人、产品、销售阶段、商机、行动、来源和审计八张表。[数据结构与字段](DATA-MODEL.md) · [机器可读结构](schema.json) · [Agent 使用手册](SKILL.md)

## 你提供什么、你将得到什么

| 你提供什么 | 你将得到什么 |
|---|---|
| 想管理的客户、联系人、产品、商机或待办，以及对应的原始资料或来源引用。初次体验可直接使用下文的虚构样例。 | 一份可查询的结构化台账。接手的 Agent 能沿关联找到客户、商机阶段、待办与来源，继续跟进。 |
| 已登记的 Agent 身份和当前会话标识。更新既有记录时，先查询当前版本和哈希，再准备要改的字段。 | 可先预检，再由多个 Agent 经过同一协调器顺序写入。遇到旧版本修改时，系统提示冲突，便于核对后再提交，避免覆盖别人刚保存的进展。 |
| 对具体写入的授权及其可定位引用，和每项业务请求的原始请求键。 | 写入后可回读业务和审计，核对经办 Agent、会话、版本、授权和来源。遇到中断可用原键续接或对账，重放已核验的请求不会重复写入。 |

## 环境与依赖

| 使用方式 | 需要准备什么 |
|---|---|
| 阅读说明或交给 Agent 使用 | 浏览器或 Markdown 阅读器。让 Agent 实际操作时，需要它能访问技能目录、私有工作目录和本机终端。 |
| **同机本地 SQLite（入门）** | 一台电脑、完整的技能目录，以及 Python 3.10 或以上版本（含标准库 `sqlite3`）。准备一个仅供获准账号访问的本机目录存放数据和密钥。下载后即可离线使用，无需飞书账号、云服务器或额外 Python 包。已在 Windows 实测。 |
| 飞书多维表格（可选） | 同样需要 Python 和本机协调库，另需联网、安装官方 `lark-cli`，用有权限的飞书账号登录，并准备一份可建表、建字段和读写记录的专用空白 Base。各 Agent 共用协调器，飞书存放业务数据。详见[飞书配置指南](FEISHU.md)。 |
| 多台电脑协作（可选） | 一台可持续访问的协调主机，可以是常开的办公电脑或云主机。其他设备须已有可调用该主机的身份验证连接，协调库放在主机本地磁盘。跨机连接需自行配置，当前版本已验证同机协作。 |

## 没有云服务器怎么用？

| 使用场景 | 部署方式 | 运行条件 |
|---|---|---|
| 多个 Agent 在同一台电脑 | 每个 Agent 使用自己的身份和会话，共用本机的协调器和数据库。协调器负责给写入请求排队。 | 使用 SQLite 可离线工作，电脑运行即可。 |
| 多个 Agent 在不同电脑 | 选一台常开的办公电脑作为协调主机，SQLite 文件放在它的本地磁盘。其他设备通过你已配置的身份验证连接，在这台主机上调用命令。 | 协调主机须在线。已入队的请求在重启后保留；断线设备须保存尚未提交的意图，恢复后重新核对。 |
| 希望办公电脑关机后仍可使用 | 可将同一套程序放到一台受信任的常开服务器。 | 租用云主机是可选项。 |

同一份 CRM 的所有写入应经过同一个协调器。把 SQLite 文件放入网盘同步目录、各机各建协调库，都会失去统一的排队顺序。当前版本需要另行配置跨机访问，不提供自动故障切换或离线多端合并。本机 SQLite 和同机双 Agent 写飞书已实测；跨机网络部署尚未实测。

## 第一次使用：在本机登记一条虚构客户记录

**下载完整目录。** 从仓库首页点击「Code → Download ZIP」，解压后找到 `multi-agent-crm` 文件夹。也可以用 Git 克隆整个仓库并进入同名目录。请保留该目录内的全部文件，程序运行时会读取同目录的 `schema.json` 和 `SKILL.md`。

**确认 Python 能运行。** 需要 Python 3.10 或以上版本，并能加载标准库的 SQLite 模块。先运行：

```text
python --version
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

Windows 上，即使能找到 `python.exe`，也可能只是会打开 Microsoft Store 的执行别名。如果命令无版本输出、跳出商店或返回 9009，试用 `py -3` 或当前工具环境中已安装的 Python 的完整路径，并用上面两条命令核验它。后续命令中的 `python` 都换为同一个可用解释器。如果使用 PowerShell，带空格的可执行文件路径可写成 `& "解释器完整路径"`。电脑没有可用解释器时，可从 [Python 官方下载页](https://www.python.org/downloads/) 安装后重试。

**单独存放测试数据。** 在技能包之外创建一个新的私有目录并将终端切到该目录，用于保存数据库、密钥、请求文件和备份。以下命令均在该私有目录中执行，请把 `crm.py` 换成刚下载的脚本的带引号完整路径。这样命令中相对的数据库和密钥路径都留在私有目录内。

**1. 管理员初始化数据库，为两个 Agent 分别登记身份。**

```text
python crm.py --db workspace.sqlite init
python crm.py --db workspace.sqlite register operator-a --key-file operator-a.key
python crm.py --db workspace.sqlite register operator-b --key-file operator-b.key
```

**2. 在各自会话中选择身份，读取手册，再查询组织。** 将 `CRM_ACTOR`、`CRM_KEY_FILE` 和 `CRM_SESSION` 分别设为该 Agent 的登记名、自己的密钥文件路径和真实会话标识。在 PowerShell 中，从上述私有目录运行以下命令。将最后一项换成当前的实际会话标识。

```powershell
$env:CRM_ACTOR = 'operator-a'
$env:CRM_KEY_FILE = (Resolve-Path -LiteralPath './operator-a.key').Path
$env:CRM_SESSION = '填写当前会话标识'
```

在 POSIX 系统中使用 `export` 设置相同的三个变量。能够直接修改协调库的系统账号也能绕过命令行检查，请限制主机上的文件与终端权限。

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

空库查询返回 `not_found`；预检返回 `dry_run` 和 `write_ready=true`；提交成功返回 `saved_and_verified`。用 `query` 查到刚写入的记录后，再用 `history` 核对请求键、经办人、会话、版本和写入后哈希。写入后哈希应与查询中该版本的哈希一致。

更新时使用刚查到的版本和哈希，只填写要改的字段。每个新意图使用新请求键；同一请求断线后，用原身份、原键续接。队首请求待处理时，后续写入排队。远端结果不明确时，先核对业务和审计，必要时交管理员处理。

## 使用飞书多维表格

准备独立空白测试库、已登录的飞书用户和官方命令行工具。初始化八张表，将返回的映射保存在技能包外，再用 `init --feishu-config` 指定映射文件，新建对应的协调库。飞书模式需要网络。审计中的 Agent 身份与访问飞书 API 的登录账号分别记录；多个 Agent 可在同一飞书用户授权下协作。[飞书配置步骤](FEISHU.md)

请成对备份协调库和飞书映射。丢失协调库会丢失请求归属、队列状态和本地审计索引。直接编辑飞书表格或让另一个协调器写同一份数据，都可能产生并发冲突。

本技能采用 [MIT 许可证](LICENSE)。
