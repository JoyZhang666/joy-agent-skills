# 计划、执行与恢复

## 命令接口

以下 `python` 应替换为已核实的 Python 3.10+ 可执行文件。`RUN` 必须位于源目录及最终源目录之外；每次 `plan` 使用全新输出目录。命令中的路径和摘要是占位参数，不是授权。

```text
python -X utf8 -B scripts/batch_names.py audit TARGET --output RUN/audit.json
python -X utf8 -B scripts/batch_names.py plan TARGET --rules RULES.json --output RUN/proposal
python -X utf8 -B scripts/batch_names.py apply RUN/proposal/plan.json --approved-plan APPROVED_SHA256 --journal RUN/events.jsonl
python -X utf8 -B scripts/batch_names.py apply RUN/proposal/plan.json --approved-plan APPROVED_SHA256 --journal RUN/events.jsonl --execute
python -X utf8 -B scripts/batch_names.py verify RUN/proposal/plan.json --state final
python -X utf8 -B scripts/batch_names.py rollback RUN/proposal/plan.json --approved-plan APPROVED_SHA256 --journal RUN/events.jsonl
```

最后一条仅预览恢复。用户要求或已批准失败回滚时，增加 `--execute` 才恢复旧名。恢复后 `verify --state original`。

范围选项：

- 默认：直属文件；直属目录只计入范围边界，不改名、不扫描其内容。
- `--recursive`：递归选择文件；目录名仍不改变。
- `--include-directories`：选择目录名；为保障目录改名完整性，扫描其后代，但不因扫描而自动选择后代改名。
- `--directories-only`：只选择目录改名；文件仍逐个验证。
- `--root-name NEW_BASENAME`：显式选择目标目录自身改名，最后执行；记录旧/新根路径，完整扫描后代。仅在审批覆盖根目录改名及依赖影响时使用。

根目录或子目录改名会改变外部引用路径。调查播放列表、旁车文件、项目登记和用户提供的引用范围；若依赖同步修改尚未获批，不实施会破坏依赖的目录批次。首版只列出这些依赖，不自动改文件正文或外部记录。

## 审批证据

`plan.json` 保存绝对旧/新根、范围、规则、基线、逐项旧/新相对路径、变化片段、执行顺序及 `plan_id`。摘要对除 `plan_id` 外的规范化 JSON 计算 SHA-256。JSON 不允许手工改后沿用旧批准。

`rename-manifest.csv` 使用 UTF-8 BOM，字段为旧路径、新路径、类型、文件大小、哈希、变化详情和提示。目录大小/哈希留空，完整性由文件后代记录和完整目录集合证明。`preview.md` 提供全部映射。JSON 与 CSV 必须保留在一起；加载时逐字符核对 CSV 与相应格式版本的 JSON 生成结果。

新计划使用格式版本 2：每个 CSV 单元格正确加引号、转义；公式前缀（包括全角形式、前导空白）或控制/格式字符相关文本加可见的 `[text] ` 标记，避免作为表格公式解释。该标记只用于 CSV 显示，准确原名及执行映射保留在 JSON。不要将 CSV 中带标记的路径直接当作真实路径，不要在表格软件中编辑后覆盖审批清单。

仍支持读取、执行和回滚格式版本 1，按旧版规则逐字核对原 CSV，保留原摘要及日志绑定。旧 CSV 没有上述防护，应使用纯文本编辑器查看。不要用表格软件直接打开旧 CSV，不自动改写旧 CSV 或沿用批准修改它。读取任一计划前先拒绝 JSON/CSV 及其祖先路径中的链接和重解析点，且两者必须为普通文件。

实际执行前将用户批准的摘要和会话确认写入运行记录；`--approved-plan` 必须是该摘要。脚本无法验证自然语言授权真实性，Agent 不能把“给我整理方案”解释为批准执行。仅有风格选择也不等于完整清单获批。

## 每阶段 100% 关口

1. 调查：文件/目录均有记录，数量和总字节闭合，每份文件有哈希，读取失败不得报通过；列出重复内容、缺号和乱码/广告候选。
2. 方案：完整映射、无操作行也覆盖，差异有理由，规则幂等，名称与路径唯一合法，核心信息保护和未决项已处理；只有完整清单获批才可进入执行。
3. 执行：重新核对范围、文件哈希和修改时间；一次只运行一个批次，暂停外部下载/同步写入。目录深层先于祖先，禁止交叉移动/合并/循环。日志独占新建，逐操作先落盘意图再落盘完成状态。
4. 交付：核对全部目标与后代路径、大小/哈希/修改时间、目录集合，CSV 与 JSON 一致，回滚预览可行，结果与恢复入口链接存在。只改名时不要求解析整个文件格式。

`apply` 与 `rollback` 默认预览，必须有 `--execute` 才改名。`verify` 默认检查最终状态，`--state original` 检查基线状态。已有日志禁止再次 apply，避免把部分完成任务当成新任务。

## 中断与局限

发生普通异常时，工具尝试从日志核对当前状态后逆序恢复。突然断电/进程被杀后，用原始 JSON、CSV 和日志先运行 rollback 预览。最后一项只有意图记录时，依据旧/新路径存在性与全量哈希核对判断是否已完成；两边都存在/都不存在、日志截断或哈希不符时停止，保留数据并报告具体位置。

Windows `os.rename` 使用不覆盖目标的语义。多文件批次不是原子事务，工具不能阻止其他应用并发写入。外部文件出现、内容变化、文件锁或日志损坏可能令自动回滚无法完成；此时不得删除冲突文件或宣称已恢复。该限制必须随恢复报告交接。

完整性核验包含文件大小、SHA-256、文件修改时间及路径集合；不覆盖目录修改时间、访问时间、创建时间、ACL、备用数据流等全部文件系统属性。规则来自用户审批的可信配置；任意正则表达式可能耗时，不应接收陌生人提供的规则并无人值守执行。

计划、预览、审计结果和日志会包含使用者的真实文件名、绝对路径及文件哈希，应保存在私有位置，不提交到公开仓库或问题反馈中。

保留清单、审批证据、日志和验收报告。不要删除它们来让重试通过；需要重新规划时用新运行目录。
