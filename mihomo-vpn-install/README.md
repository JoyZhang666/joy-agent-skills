![mihomo 安装与运维：进阶使用 · 自备节点](../assets/brand/mihomo-vpn-install.svg)

# mihomo VPN 安装与运维

**技术工具 · 进阶使用 · 自备节点**

| 你提供什么 | 得到什么 |
|---|---|
| 获授权管理的 Linux 环境、私有订阅或节点配置，以及本次操作范围。 | 安装检查、配置与排障记录、回滚指引；实际变更按授权执行和核验。 |

**先准备**：自备有效节点/订阅及上游 mihomo 程序；本项目不提供 VPN 或节点服务。

[第一次使用 Skill](../docs/start-here.md) · [安装与授权流程](references/server-vpn-authorization-workflow.md) · [返回全部作品](../README.md)

<details>
<summary>看一个虚构示例</summary>

> 虚构检查记录｜配置语法：通过｜节点连通性：未测试｜下一步：确认测试范围。

仅示意输入或输出的形式，不是真实用户资料或运行结果。

</details>

---

版本：**2.1.2** · 作者：**JoyZhang666** · 许可：**MIT**

面向使用 AI Agent 管理 Linux 代理环境的人，提供安装检查、订阅格式识别、节点对照测试、TUN/DNS 排障、应用代理链诊断与回滚方法。它是指南和辅助工具集，不是一键 VPN，不提供订阅或节点服务。

## 从哪里开始

1. 阅读 [SKILL.md](SKILL.md)，按问题选择专题。
2. 新安装从[安装流程](references/server-vpn-authorization-workflow.md)开始，使用[配置模板](references/mihomo-config-annotated.yaml)的私有副本。
3. 首次安装先准备订阅 URL 或独立节点配置。不会创建文件时，让 Agent 协助准备并给出具体位置；你用记事本打开、粘贴一行链接、保存关闭后回复“已保存”即可。文件操作不方便时，可在了解聊天留存风险后选择直接发送订阅 URL，详见[两种提供方式](references/server-vpn-authorization-workflow.md#如何提供订阅链接)。没有节点来源时应停在“等待节点配置”。本包 HTTP 模板需要有效订阅；独立节点配置需相应调整 provider 与策略组。
4. 需要 Agent 使用时，将整个 `mihomo-vpn-install` 目录放入该 Agent 明确支持的技能目录；加载方式按其文档确认。也可直接阅读，不依赖其他私人 Skill。

## 环境和依赖

| 使用方式 | 依赖 |
|---|---|
| 阅读指南 | Markdown 阅读器或支持 Skill 的 Agent |
| 包内三个辅助脚本 | Python 3.10+，仅标准库 |
| 实际安装与系统诊断 | Linux、用户选择的 mihomo 版本；按场景使用 systemd、curl、iproute2，DNS 检查可用 dig/resolvectl |
| 可选 SS 独立测试、应用联调 | 用户另行安装的 SS 客户端、对应应用或插件；本包不捆绑这些程序 |

所有本包文档与脚本均包含在目录内；实际代理运行必然依赖 mihomo、用户自己的订阅和网络环境，不能理解为零外部运行依赖。

## 示例与隐私

配置中的 `.invalid` 域名与 `REPLACE_ME` 都是不可直接使用的占位符。`127.0.0.1`、私网网段、系统标准路径是通用教学示例，不是作者的真实机器信息。填写凭据后的配置必须放在仓库外。

禁止公开订阅 URL、查询 token、节点密码/UUID、节点真实域名/IP、订阅缓存、服务日志、环境文件或鉴权响应。`.gitignore` 只是防误加入，无法清除已经提交的秘密或代替全文审查。

## 脚本用法

在技能根目录执行：

```bash
python3 scripts/localhost-proxy-loopback-probe.py --help
python3 scripts/diagnose-airport-server.py --help
python3 scripts/ss-probe-cleanup.py --help
```

端点 JSON 格式为 `[{"host":"node.example.invalid","port":443}]`，真实文件仅本地保存。默认只校验、不联网：

```bash
python3 scripts/diagnose-airport-server.py --input /path/to/private/endpoints.json
```

确认端点归属及探测授权后，添加 `--probe`。该脚本做 TCP 探测，不测试代理密码、TLS 或业务登录。失败只表示当前主机到该端点不可达，不直接等于供应商宕机。

临时目录清理默认预览；仅在核对目录、文件归属且对应进程已停止后使用 `--apply`。脚本接口详见 `--help`。

## 来源与许可

本包正文与脚本按 [MIT](LICENSE) 发布。mihomo 等第三方项目保留各自许可，本包未捆绑其源码或二进制；项目链接及引用边界见 [NOTICE](NOTICE.md)。
