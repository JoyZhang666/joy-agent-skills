# 上游来源与适配记录

上游作者：Zara（GitHub：`zarazhangrui`）。项目：[lark-minutes-tasks](https://github.com/zarazhangrui/lark-minutes-tasks)。
固定提交：[`72c9fe2e19637e355fda35ee38869d638098400b`](https://github.com/zarazhangrui/lark-minutes-tasks/tree/72c9fe2e19637e355fda35ee38869d638098400b)。许可证：[MIT](../LICENSE)，[上游原始版权与许可文本](https://github.com/zarazhangrui/lark-minutes-tasks/blob/72c9fe2e19637e355fda35ee38869d638098400b/LICENSE) 字节保留。
原版入口：[minutes.md 固定版本](https://github.com/zarazhangrui/lark-minutes-tasks/blob/72c9fe2e19637e355fda35ee38869d638098400b/minutes.md)。

可通过上述固定提交查看原始文件；下文记录参考文件的 SHA-256。本公开包不附带开发者的本地来源目录、运行记录、真实笔记、身份映射或凭证，也不复制上游示例中的私人租户链接。

## 继承与改动

| 功能 | 本版处理 |
|---|---|
| 全文阅读、元信息、AI 待办交叉核对 | 保留；来源更换为 Get CLI |
| 显式/隐含行动项、编号选择与逐项执行 | 保留；增加出处、稳定编号、执行记录 |
| Wake Word | 保留；默认关闭、本人身份按会议确认、原文不能扩大授权 |
| 消息、文档、调研、阅读、产品、会议、任务 | 保留全部分类；实际工具按本地能力映射 |
| 飞书日历、任务、文档 API | 去掉强依赖，分别用本地日历导入文件、行动清单与文稿；Get 成果笔记仅在明确获准后保存 |
| macOS 剪贴板 | Windows PowerShell 按需复制 |
| 自动写 memory | 改为项目配置；不修改系统记忆 |
| 重试与交接 | 增加内容指纹，分别记录执行和上传授权；获准上传时幂等保存并回读正文/归属 |
| HTML 界面 | 上游步骤实际为编号对话，本版保持编号对话，不另建 UI |

本版是改编作品，非 Zara 官方 Get 版本。保留主要任务处理流程不等于获得飞书等平台的 API 能力。Get 原生转写、时间线的返回结构随服务版本变化，以真实接口为准。

## 输入文件校验

```json
{
  "repository": "https://github.com/zarazhangrui/lark-minutes-tasks",
  "commit": "72c9fe2e19637e355fda35ee38869d638098400b",
  "files": {
    "minutes.md": "aadaf705b325c260a4f154359c980278824d23d2213aaf1a2a8cdc9dbe109676",
    "README.md": "f7993dae90c7ddf65b5ecef3b39e0f1001895b70cc68554daeef82ad35efb77d",
    "README_CN.md": "6992e27165d2b4f170070cb6721c4232fa1ef06bf4b6edbb2d2eb1b7e291975c",
    "LICENSE": "1126322e2cc8d165adc4c792eeb195717de2bcc7b39be1ce77959d78e87ef685"
  }
}
```
