# 实践依据与适配取舍

检索核对日期：2026-09-11。下列为设计参考，不构成工具安装或远端执行授权。

| 来源 | 采用 | 不直接照搬 |
|---|---|---|
| [Composio File Organizer](https://github.com/ComposioHQ/awesome-claude-skills/blob/master/file-organizer/SKILL.md) | 分析、提案、审批、日志 | 整理时顺带移动/删除、自动去版本号 |
| [AlienHub File Organizer](https://github.com/AlienHub/file-organizer/blob/main/SKILL.md) | 规则与预览分离 | macOS 标签、全局配置和自动安装 |
| [Microsoft PowerRename](https://learn.microsoft.com/en-us/windows/powertoys/powerrename) | 逐项前后对照、限定范围、局部替换、撤销 | 仅依赖 UI 撤销，不保存长期恢复清单 |
| [repren](https://github.com/jlevy/repren) | 试运行、机器可读输出、恢复机制 | 正文重写、跨目录移动和自动备份文件散布 |
| [ftfy](https://ftfy.readthedocs.io/en/latest/) | 乱码优先恢复并减少误判 | 不将启发式修复当成事实或自动变更依据 |
| [Windows 命名规则](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file) | 保留名称、非法字符、大小写冲突和路径限制 | 不通过改注册表绕开路径检查 |

本地经验：保留逐文件 SHA-256、执行前全量漂移检查、标题保护、无操作行验证、失败恢复及 100% 阶段关口。对本次允许的广告/乱码修改，将“整个标题不可改”细化为“每处修改必须能由获批规则及完整差异重建”。

曾出现交接者找不到清单、README 示例与实际文件不一致的问题：因此清单必须在首次改名前落盘，最终交付验证链接存在。没有 CSV 时先调查是否实际改名及当时交付范围，不能直接推断遗漏或补造历史批准；用户放弃的旧任务不自动恢复。

技能保留按需执行原则：命名合理可以跳过改名，仅有命名需求不附加内容概述；本技能的审计哈希不能代替音频播放或 PDF 全文阅读。
