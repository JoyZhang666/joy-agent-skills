# Full Book Deep Reading Workflow

将用户选定的书籍或章节范围整理成可续接的精读项目：原文定位、逐章笔记、进度记录、主题讨论与范围明确的综述。

版本：**2.0.1**。这是对 2.0.0 的隐私与质量修订：去除私人经历；统一状态；修复全文拆分遗漏、路径边界、覆盖检查和打包范围。保留原 MIT 许可与匿名版权署名。

## 使用条件

- 支持加载 SKILL.md、读取用户授权文件并写入项目目录的 Agent。
- 辅助脚本需 Python 3.9+，仅用标准库；无必需第三方 Skill。
- AI 阅读由宿主 Agent 完成。PDF/OCR、自动调度、云端交付取决于宿主实际能力和另行授权；本包不提供这些服务实现。
- 未完成各宿主、Windows/macOS/Linux 的端到端实测，不保证任意 Skill 框架直接兼容。采用通用 Agent Skills 元数据；按宿主文档安装本目录。也可让 Agent 读取本目录 SKILL.md 后按授权范围操作。

## 最小示例

准备自己有权处理的 UTF-8 文本，然后在 Skill 目录运行（用本机 Python 命令替换 python）：

```text
python scripts/create_reading_project.py "book.txt"
python scripts/split_markdown_chapters.py "book.txt" "reading-project/chapters"
```

此示例假设 book.txt 在当前目录。之后对 Agent 说：

> 按 SKILL.md 精读这个文件的前两章，建立 manifest 和进度，笔记保存在书旁；本次只在当前会话处理，不上传、不安排后台任务。

Agent 按 references/durable-continuity-protocol.md 初始化状态并逐章写笔记。完成后可检查：

```text
python scripts/build_reading_index.py "reading-project"
python scripts/validate_reading_project.py "reading-project"
```

输入缺失、状态不一致或覆盖不完整时应报告实际错误。结构校验不能证明模型理解正确，笔记仍需核对原文。

## 内容与边界

15 份专题参考、10 份空白模板、6 个辅助脚本。入口见 [SKILL.md](SKILL.md)。不包含书籍全文、私人书库、历史聊天、账号配置或凭据。

源码与笔记默认仅本地。扫描件无 OCR 工具时明确等待可读文字，不能编造原文；调度不可用时手动续接。复验记录采用静态审查，未宣称真实整本书、外部接口或跨平台验收通过。

## 来源、许可与反馈

本目录由提供者提交的 2.0.0 包修订而来；原包带 MIT 许可，版权行原样保留于 [LICENSE](LICENSE)。本次没有复制第三方书籍或外部 Skill 的正文/代码。通用结构参考 [Agent Skills specification](https://agentskills.io/specification)，标准库接口参考 [Python 文档](https://docs.python.org/3/library/)。宿主相关能力由其自身文档和许可决定。

问题可通过 [仓库 Issues](https://github.com/JoyZhang666/joy-agent-skills/issues) 反馈。请只提供虚构或脱敏的复现资料，不上传书籍原文、私人笔记和凭据。
