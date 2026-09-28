![Crossborder Tunnel Kit：实验性 · 自有 VPS 必需](https://raw.githubusercontent.com/JoyZhang666/joy-agent-skills/main/assets/brand/crossborder-tunnel-kit.svg)

# Crossborder Tunnel Kit

**技术工具 · 实验性 · 自有 VPS 必需**

| 你提供什么 | 得到什么 |
|---|---|
| 自有或获授权的 Linux VPS、域名/TLS 等条件，以及明确的部署范围。 | 一份可导入 Mihomo 兼容客户端的个人 YAML、导入步骤和故障指引；VPS 部署与实际连接验收通过后即可使用。 |

先准备：自备 Linux VPS、相关网络与证书条件。

[第一次使用 Skill](https://github.com/JoyZhang666/joy-agent-skills/blob/main/docs/start-here.md) · [部署准备入口](SKILL.md) · [返回全部作品](https://github.com/JoyZhang666/joy-agent-skills)

<details>
<summary>看一个虚构示例</summary>

> 虚构准备记录｜VPS：待提供｜证书：待确认｜状态：准备中，尚未部署。

仅示意输入或输出的形式，不是真实用户资料或运行结果。

</details>

---

版本：**0.3.0** · 作者：**JoyZhang666** · [MIT](LICENSE) · 实验性

**你最终拿到的是一份个人专用的 `tunnel-client.yaml` 配置文件，以及对应的导入、连接和故障处理说明。** 在你的 VPS 服务已部署、参数已填写并校验后，把这份文件导入电脑或手机上支持 Hysteria2 的 **Mihomo 兼容客户端**，选中配置和节点、启用已确认的接入方式，即可尝试连接自己的 VPS；完成实际连接和应用测试后才算交付成功。

**新手使用：** 在客户端找到“配置／Profiles”→“导入本地文件”→选择 Agent 交付的 `.yaml`→启用该配置→选择 `HY2`→按[图形客户端导入指南](references/client-import.md)连接并验证。菜单名称可能不同，Agent 应按你的软件名称和版本逐步指导。其他 VPN 软件（包括只接受 WireGuard/OpenVPN 配置的软件）不一定兼容，不能把 YAML 当成通用格式。

GitHub 中的是空白模板，不是已经能用的个人节点。Agent 根据你的私有参数生成 YAML；服务端配置由 Agent 管理，新手无需自行改写 JSON。真实 YAML 含密码和可能的 WARP 私钥，只应私密保存和传到自己的设备。

本项目为自有或获授权的 Linux VPS 提供 Hysteria2 部署准备、配置生成和检查工具，可选 Reality 备线、客户端 WARP 链式出口或服务端 WARP 分流；不提供 VPS、节点订阅、证书或 WARP 账号。

## 视频打不开？从这里排查

- **已连接 VPS，YouTube 部分视频仍无法播放：** 先查[故障索引 F03–F07](references/troubleshooting.md)，再按[客户端 WARP-over-Hy2 方案](references/client-warp.md)核验出口、DNS 和会话一致性。
- **配置导入失败／选了节点仍无网络：** 查[导入指南](references/client-import.md)和[故障索引 F01–F02](references/troubleshooting.md)。
- **小包可用但视频卡顿、Google 反复验证码：** 查[实战经验与适用边界](references/field-lessons.md)。每条经验对应证据、修复、验证与回退路径。

新增方案来自维护者的实战记录，经脱敏、纠错并整理为包内文档和模板；使用者无需访问私人笔记。当前公开版本仍须在自己的设备和网络上验收。

## 必要的外部条件是什么？

**一台你自己拥有或获明确授权管理的 Linux VPS，是实际部署和使用本项目的必要外部资源。** VPS 可以理解为租用的一台持续联网的远程电脑；Skill 提供方法和工具，不能替代服务器。

| 必要条件 | 需要具备什么 |
|---|---|
| VPS 与管理权限 | 运行 Linux/systemd，能通过 SSH 登录，并有 root 或 sudo 管理权限；操作系统和 CPU 架构须有对应上游程序发行包 |
| 公网与恢复入口 | 客户端能到达服务器的公网地址，Hysteria2 所用 UDP 端口可通，能管理云安全组和主机防火墙；SSH 失联时仍能进入云控制台恢复 |
| TLS 身份 | 默认路线使用可管理的域名与匹配的有效 TLS 证书、私钥及续期方式；本包不自动购买域名、申请证书或修改 DNS |
| 客户端与工具 | 一台实际用于连接的电脑或手机，以及支持 Hysteria2 的客户端；执行本包 Python 工具的环境需 Python 3.10+ |
| 费用与运行环境 | 用户自行承担 VPS、可能的公网地址、流量及域名等费用，并核对服务商使用条款；服务器还需能取得经核验的上游程序 |

Reality 和 WARP 都是可选项，不是开始的前提。证书信任的其他方案须单独核查，不能靠关闭验证代替。单纯阅读说明、检查公开模板不需要 VPS，但不能据此交付可连接的线路。

## 没有 VPS 时怎么办？

Agent 应先询问：“你是否已有自己拥有或获授权管理的 Linux VPS？如果没有，我可以先指导你获取；VPS 是本项目实际部署的必要资源。”

获取步骤：

1. **先明确需求。** 告诉 Agent 预算、使用设备、所在网络和目标服务器地区；不确定时说“不清楚”即可。先确认所选服务允许预期用途，并支持公网连接和所需 UDP 端口；不承诺购买后必然可达。
2. **获取自己的服务器。** 可以向组织管理员申请一台获授权的 VPS，或到云服务商官网注册并租用 Linux 云服务器。例如可参考 [DigitalOcean 官方创建指南](https://docs.digitalocean.com/products/droplets/how-to/create/)，它是操作示例，不是必须选择的服务商。购买与付费由用户自行确认，Agent 不默认代购或开通计费资源。
3. **创建前核对选项。** 在控制台选择地区、Linux 系统、CPU 架构和套餐，确认公网地址、流量额度、超额计费和续费方式；容量按使用人数和负载核对，不给未经实测的最低规格保证。首次演练优先使用无重要业务的测试机。
4. **设置登录和恢复方式。** 按服务商指南配置 SSH 登录；使用密钥时仅上传公钥，私钥留在自己控制的私密文件中。可参考 [SSH 密钥设置](https://docs.digitalocean.com/products/droplets/how-to/add-ssh-keys/)及[云防火墙说明](https://docs.digitalocean.com/products/networking/firewalls/how-to/configure-rules/)。确认云控制台可用；开端口时只处理本次必要规则。
5. **取得后再继续。** 让 Agent 在获授权范围核对登录权限、系统、恢复入口和网络条件。把真实服务器地址、私钥及口令留在私有配置中，不发到公开仓库、Issue 或聊天。资源具备后，再准备域名、证书与客户端。

如果用户无法取得 VPS，Agent 应明确、礼貌地说明：

> 很抱歉，VPS 是本项目实际部署的必要外部资源。由于目前无法取得可用且获授权的 VPS，本项目的部署和线路交付暂时无法继续。我们可以先停在这里，等你准备好 VPS 后再接着进行。

此时停止服务器部署、真实客户端配置生成和连通性验收，记录“缺少 VPS，待准备”。如用户愿意，可以解释概念或整理准备清单；不得用示例地址、他人节点或普通订阅 URL 充当 VPS。

## 用户输入是什么？

先用自然语言说明即可，不要求用户一开始填写 JSON：

| 输入 | 用户提供或确认的内容 |
|---|---|
| 本次目标与授权 | 只读检查、生成配置，还是部署及客户端接入；哪些服务器和设置允许修改 |
| VPS 情况 | 是否已有 VPS、系统和架构、是否能 SSH 登录、是否有管理权限和控制台；不会查看时由 Agent 指导 |
| 接入需求 | 电脑或手机的系统、客户端、要代理的应用；默认只处理明确指定的应用，系统代理/TUN 另行确认 |
| 网络与 TLS | 可用端口、域名及 DNS 管理能力、证书与私钥在服务器上的位置；具体值保存在私有文件 |
| 私有认证参数 | Hysteria2 两端一致的口令；由 Agent 指导在受保护环境生成并写入，无需用户自行编造。仅选用 Reality/WARP 时准备相应材料 |

确认这些信息后，Agent 按[输入说明](references/inputs.md)协助建立私有参数文件并逐项填写。本项目不以机场订阅 URL 作为输入；也不需要用户提供云服务商账号密码或付款信息。

## 最终的交付物是什么？

交付取决于用户授权的阶段；每项都应注明“已完成、未执行或待验证”，给出真实保存位置：

| 阶段 | 应交付的具体内容 |
|---|---|
| 只读检查／部署准备 | 条件核对清单、缺项及下一步、部署方案与变更／恢复计划；不声称已建成线路 |
| 生成配置 | 用户私密目录中的服务端 JSON 和匹配的客户端 `tunnel-client.yaml`、导入说明及已执行的解析检查结果；配置含凭据，不随公开包发布 |
| 获授权部署并验收 | VPS 上的 Hysteria2 服务、指定客户端和应用的接入说明，以及实际执行的握手、TLS、DNS、出口和应用测试记录 |
| 维护交接 | 文件和服务位置、证书续期方式、启动／停止及恢复步骤、未通过的项目与后续行动；凭据继续单独保密 |

目标是在资源、授权及验收均具备时，交付一条用户控制的可连接线路及维护说明。只有真实部署和测试完成，才能称为“已部署／已连通”；缺少 VPS 时只能交付准备清单和停止原因。本包当前仍为实验性，不能以模板解析成功代替实机验收。

## 开始使用

1. 先按上文确认 VPS 是否具备；缺失时先获取，无法取得时停止部署。阅读 [SKILL.md](SKILL.md)，明确本次是只读核查、生成配置，还是已授权部署。
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
| scripts/render.py | 从私有参数生成 JSON；输出文件名以 .yaml/.yml 结尾时生成 YAML，拒绝覆盖；用法见[输入说明](references/inputs.md)，之后必须原生配置检查 |
| scripts/scan.py | 只读扫描文本；默认公开模式，--runtime 仅检查占位符 |
| scripts/verify.py | 只读比较可信预期 SHA-256，不下载文件 |
| scripts/baseline.py | 默认本地元数据；--external-ip 才访问 Cloudflare 并输出敏感出口 IP |
| scripts/safety.py | 默认 review；--apply 可修改配置/服务/timer，仅限 Linux root，须先完成[恢复演练](references/rollback.md) |

工具加载不会自动部署，但运行带变更参数的命令可能中断服务。恢复工具不覆盖防火墙、路由、DNS 或整个 VPS；不把它当已验证的生产保命措施。

## 验证状态与限制

v0.3.0 已通过 7 项虚构数据渲染回归测试，以及 Mihomo 1.19.30 对主线、Reality 备线、WARP 链式三种配置的 JSON/YAML 共 6 份文件的原生解析。可在受控开发环境运行 `python -B tests/test_render.py -v` 复验渲染；新模板尚未进行真实 GUI 导入、WARP 握手或视频播放验收。

历史维护记录包含 Windows 合成测试和部分上游程序配置解析，具体版本及范围见 [versions.json](references/versions.json)。**尚未完成 Linux 服务权限、恢复 timer 实机演练、Hysteria 启动、真实 TLS/客户端握手及跨网验收。** 公开可阅读与可审查不等于生产可用；先在受控环境复验，不承诺解锁、匿名或无 IPv6/DNS 泄漏。

v0.3.0 新增 YAML 输出、客户端导入指南与 WARP-over-Hy2 模板，补齐 DNS、出口一致性、MTU 等实战故障索引；保留无 VPS 时的停止条件。

问题与改进可提交至[仓库 Issues](https://github.com/JoyZhang666/joy-agent-skills/issues)，仅附脱敏类别和复现步骤，不附凭据、服务器地址、配置正文或原始日志。第三方项目说明见 [LICENSE-NOTICE](LICENSE-NOTICE.md)。


封面和仓库导航是可选在线资源；本包的配置生成、导入与排障说明均在包内，离线阅读不依赖这些链接。
