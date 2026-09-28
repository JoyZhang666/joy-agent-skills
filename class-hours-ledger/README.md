# Class Hours Ledger

**1.1.0 · MIT**。本地 SQLite 课程课时流水：购课、赠课、上课、调整、过期；整课时、每节一小时，不联动资金账本。

## 环境与使用

Python 3.10+ 标准库（需 SQLite 支持），无第三方 Python 依赖。将本目录放在支持 SKILL.md 的宿主中，或直接使用 CLI。跨宿主自动发现和真实业务环境未全面验收。

先在 Skill 目录之外创建一个专用数据目录，再将以下 `<data>` 替换为实际路径；带空格路径按本机 shell 规则加引号：

```text
python class_ledger.py --db <data>/classes.db init
python class_ledger.py --db <data>/classes.db add 2026-01-01 purchase 10 --paid 800 --valid-until 无限期 --request-id purchase-example-001
python class_ledger.py --db <data>/classes.db add 2026-01-02 attend -1 --request-id attend-example-001
python class_ledger.py --db <data>/classes.db verify
python class_ledger.py --db <data>/classes.db report
```

示例完全虚构；预期余额为 9 节。金额按分存储并以 JSON 输出。同一请求 ID 和相同字段重试不会重复记账；同 ID 不同字段会拒绝。每次操作仍应保管请求 ID。

退出码：0 成功；1 错误；2 已入账但备份失败（勿换 ID 重复入账）。备份采用 SQLite 一致性备份，文件名唯一，保留全部备份，用户自行审阅后清理。数据库和备份只留本地。

## 1.1.0 的兼容变化

必须显式 --db，新增 init、--request-id；新 schema 使用整数分，**不直接兼容 1.0 数据库**。迁移前备份，另行审查字段映射。此发布未读取或迁移任何真实数据库。

完整性检查是内部一致性核对，不是防篡改或漏录证明。负余额可记录但会警告。并发写入串行化；数据库仍应位于可靠的本地磁盘，不建议放网络共享盘。参考 [SQLite 接口](https://docs.python.org/3/library/sqlite3.html)。

流程与权限见 [SKILL.md](SKILL.md)。保留提供者原包的 [MIT LICENSE](LICENSE)，本次修订未复制外部项目代码。反馈请提交[脱敏 Issue](https://github.com/JoyZhang666/joy-agent-skills/issues)，不要上传实际数据库。
