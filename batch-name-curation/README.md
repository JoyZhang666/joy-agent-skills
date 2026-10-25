# 批量命名整理 · batch-name-curation

**v1.1.0 · Windows · Python 3.10+ · 无需 API · MIT**

整理文件和文件夹名称中的广告片段、冗余后缀或有依据的乱码。先展示完整改名清单，由你批准后才执行；保留文件内容，提供核验和回滚入口。

## 输入与交付物

| 你提供什么 | 得到什么 |
|---|---|
| 本地目标文件夹、处理范围、希望保留/清理的命名规则 | 调查报告、完整新旧名称映射及逐处修改理由 |
| 对具体清单及计划摘要的确认 | 批准后执行的改名结果、完整性核验与恢复日志 |

计划产物是 `plan.json`、`rename-manifest.csv` 和 `preview.md`。JSON 是准确执行依据；CSV 的危险文本带 `[text] ` 显示标记，标记不进入真实文件名。软件不自动上传文件，也不调用转写或大模型 API。

## 新手安装

1. 安装官方 [Python](https://www.python.org/downloads/windows/)，使用 3.10 或更新版本。安装时勾选 **Add python.exe to PATH**，然后在新开的 PowerShell 中运行 `python --version` 确认。
2. 下载本仓库 ZIP 并解压，找到 `batch-name-curation` 文件夹。保留里面的脚本、说明和引用资料。
3. 将整个文件夹复制到你的 Codex Skills 目录，通常是 `%USERPROFILE%\.codex\skills\batch-name-curation`。如果有旧版，先在技能目录之外保留备份，不要混合覆盖文件；复制后重新打开 Codex。
4. 在 Codex 中输入下面的要求。若技能未被识别，先确认 `SKILL.md` 正好位于上述文件夹第一层。

```text
使用 $batch-name-curation 检查 D:\NamingDemo\source。
先只处理直属文件，保留原编号、正文标题和扩展名。
请先展示完整的新旧名称清单及修改理由，等我确认后再改名。
```

先使用自己创建的虚构样例文件夹尝试；不要把示例路径当成必须存在的目录。默认只处理直属文件；递归、目录改名和根目录改名需要明确选择。

## 手动使用示例

在解压后的技能文件夹中打开 PowerShell。下面假设你已创建 `D:\NamingDemo\source`，其中只有虚构文件 `001.示例课程【演示广告】.txt`；运行目录 `D:\NamingDemo\run-001` 位于源目录外，且尚未使用。

用 UTF-8 保存以下内容为源目录之外的 `D:\NamingDemo\rules.json`：

```json
[
  {
    "id": "remove-demo-suffix",
    "kind": "suffix",
    "match": "【演示广告】",
    "replacement": "",
    "target": "file",
    "reason": "仅删除已明确确认的演示广告后缀"
  }
]
```

调查并生成计划，均不改名：

```powershell
python -X utf8 -B scripts/batch_names.py audit D:\NamingDemo\source --output D:\NamingDemo\run-001\audit.json
python -X utf8 -B scripts/batch_names.py plan D:\NamingDemo\source --rules D:\NamingDemo\rules.json --output D:\NamingDemo\run-001\proposal
```

打开 `preview.md`、JSON 和 CSV 核对全部映射。你确认具体清单后，将下面的 `APPROVED_SHA256` 替换为已批准的 `plan_id`。**生成摘要不等于得到用户批准。**

```powershell
# 先预览；没有 --execute 不会改名
python -X utf8 -B scripts/batch_names.py apply D:\NamingDemo\run-001\proposal\plan.json --approved-plan APPROVED_SHA256 --journal D:\NamingDemo\run-001\events.jsonl

# 清单获批且预览无误后才执行
python -X utf8 -B scripts/batch_names.py apply D:\NamingDemo\run-001\proposal\plan.json --approved-plan APPROVED_SHA256 --journal D:\NamingDemo\run-001\events.jsonl --execute
python -X utf8 -B scripts/batch_names.py verify D:\NamingDemo\run-001\proposal\plan.json --state final

# 如需恢复，先预览
python -X utf8 -B scripts/batch_names.py rollback D:\NamingDemo\run-001\proposal\plan.json --approved-plan APPROVED_SHA256 --journal D:\NamingDemo\run-001\events.jsonl
```

确认恢复范围后，在最后一条命令加 `--execute`，然后运行 `verify ... --state original`。保留原 JSON、CSV 及日志；不要通过删除日志来强行再次执行。更多范围选项、规则与恢复说明见 [执行与恢复](references/execution.md) 和 [命名规则](references/naming-policy.md)。

## 保护机制与限制

- 支持后缀、字面量、正则和精确匹配；扩展名及原编号默认保护。重复内容不会自动删除。
- 拒绝覆盖、目录合并、跨父目录移动、链接/目录联接、大小写专用改名、循环交换及超出保守路径上限的计划。
- 执行前后核对路径集合、文件大小、SHA-256 和文件修改时间；范围或内容变化会阻断执行。不保证目录时间、访问时间、ACL 等全部元数据不变。
- 多项改名不是原子事务。并发写入、文件锁、外部冲突或日志损坏可能阻断恢复；应保留现场，不删除冲突文件。
- 目录改名可能影响播放列表、快捷方式和其他程序引用；本工具不自动修改外部引用或文件正文。
- 新计划为格式 2；旧格式 1 仍可执行/回滚，但旧 CSV 应只用纯文本编辑器查看。不要编辑后覆盖审批文件。
- 脚本只使用 Python 标准库，不需要 API 或运行时依赖下载；任意正则可能耗时，只运行已审阅和批准的规则。
- **运行产物含真实名称、绝对路径和哈希。请私密保存，不随技能分享，不直接粘贴到公开 Issue。** 附带 `.gitignore` 作为防误提交措施；网页上传仍须逐项检查，不能依赖它自动拦截。

## 测试与反馈

在一次性 Windows 虚拟机、虚构数据和受限网络环境中运行：

```powershell
python -X utf8 -B -m unittest discover -s tests -v
```

临时文件夹或虚拟环境本身不等于安全沙箱。反馈请到 [仓库 Issues](https://github.com/JoyZhang666/joy-agent-skills/issues)，仅提供虚构文件名、系统/Python 版本和脱敏错误信息。

## 来源与许可

维护者：**JoyZhang666**。本项目原创部分采用 [MIT](LICENSE)。设计参考与取舍见 [实践依据](references/practices.md)；这些来源作为方法参考，不表示官方合作或获得其背书。

更新内容见 [变更记录](CHANGELOG.md)。
