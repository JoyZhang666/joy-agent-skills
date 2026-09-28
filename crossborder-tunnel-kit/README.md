# Crossborder Tunnel Kit

版本：**0.2.1** · 作者：**JoyZhang666** · [MIT](LICENSE) · 实验性

为自有或获授权的 Linux VPS 提供 Hysteria2 私有隧道部署准备、配置模板和检查工具，按需添加 Reality 备线与 WARP 出口。不是一键安装器，也不提供服务器、节点订阅、证书或 WARP 账号。

## 开始使用

1. 阅读 [SKILL.md](SKILL.md)，明确本次是只读核查、生成配置，还是已授权部署。
2. 按[部署准备](references/deployment.md)确认 VPS、恢复入口、客户端、域名和证书。先建立 Hysteria2 主线，再考虑可选路线。
3. 根据[输入说明](references/inputs.md)准备私有 JSON 参数。不会创建文件时，让 Agent 先确认当前系统和目标主机，在项目外的非共享、非自动同步目录准备空文件并给出真实可点击路径；再逐项指导填写，不能要求用户自行猜测复杂 JSON 或把示例占位符当真实值。无文件权限时按实际系统提供手动步骤，不假称已创建。
4. 参数是用户自己的服务器地址、证书路径和两端匹配的认证信息，不是机场订阅 URL。让 Agent 在获准环境协助生成密钥并保密写入，不把真实值贴入公开 Issue、聊天或日志。本机文件不会自动出现在服务器上，传输必须另有已授权的方式。
5. 按[验证说明](references/verification.md)校验，再在可丢弃 Linux 环境演练。服务器部署和系统代理/TUN 设置须分别属于用户授权范围。

## 工具及依赖

阅读仅需 Markdown；五个 Python 工具仅依赖 **Python 3.10+ 标准库**。实际运行隧道另需相应上游程序、Linux/systemd、按场景使用 dig/ip/ss 及用户自己的服务器与证书。WARP 是可选项，无有效自有配置时跳过。

在 Skill 根目录中，以下命令只读取本地信息或检查文件：

```text
python scripts/baseline.py
python scripts/scan.py .
```

扫描输出仍包含相对文件名，分享输出前检查路径。零命中只说明规则未匹配，不能代替人工隐私审查。真实配置应在目录外，不能用 runtime 模式作为脱敏检查。

| 工具 | 用途与副作用 |
|---|---|
| scripts/render.py | 从私有参数生成新 JSON，拒绝覆盖；用法见[输入说明](references/inputs.md)，之后必须原生配置检查 |
| scripts/scan.py | 只读扫描文本；默认公开模式，--runtime 仅检查占位符 |
| scripts/verify.py | 只读比较可信预期 SHA-256，不下载文件 |
| scripts/baseline.py | 默认本地元数据；--external-ip 才访问 Cloudflare 并输出敏感出口 IP |
| scripts/safety.py | 默认 review；--apply 可修改配置/服务/timer，仅限 Linux root，须先完成[恢复演练](references/rollback.md) |

工具加载不会自动部署，但运行带变更参数的命令可能中断服务。恢复工具不覆盖防火墙、路由、DNS 或整个 VPS；不把它当已验证的生产保命措施。

## 验证状态与限制

历史维护记录包含 Windows 合成测试和部分上游程序配置解析，具体版本及范围见 [versions.json](references/versions.json)。**尚未完成 Linux 服务权限、恢复 timer 实机演练、Hysteria 启动、真实 TLS/客户端握手及跨网验收。** 公开可阅读与可审查不等于生产可用；先在受控环境复验，不承诺解锁、匿名或无 IPv6/DNS 泄漏。

v0.2.1 补充独立使用入口、私密文件排除规则和 MIT 许可，澄清版本证据与使用边界；不改变 v0.2.0 的脚本与模板。

问题与改进可提交至[仓库 Issues](https://github.com/JoyZhang666/joy-agent-skills/issues)，仅附脱敏类别和复现步骤，不附凭据、服务器地址、配置正文或原始日志。第三方项目说明见 [LICENSE-NOTICE](LICENSE-NOTICE.md)。
