# 来源、版本与替代方案

核查日期：2026-09-10（Asia/Shanghai）；解析验证：2026-09-11。下面是本次固定的兼容性基线，不代表将来自动追随 latest。

| 组件 | 固定版本 | 验证覆盖 |
|---|---|---|
| Hysteria | app/v2.12.2 | 官方配置/ACL/CLI 文档与源代码核对；未实际启动 |
| sing-box | v1.14.0 | 官方 Windows amd64 包，`check` 通过 |
| Xray-core | v26.3.27 | 官方 Windows 64 包，`run -test` 通过 |
| Mihomo | v1.19.30 | 官方 Windows amd64 compatible 包，两份模板 `-t` 通过 |
| systemd | 目标 Linux 发行版自带版本待确认 | 本次只有模拟测试；须在实际目标环境执行 unit 校验和恢复演练 |

发行版本、校验值与验证范围见随包的 [versions.json](versions.json)；上述为维护者在所注明日期记录的解析结果，原始本地执行日志不随包提供；使用者应按 [verification.md](verification.md) 在自己的授权环境复验。本 skill 发布包不带任何第三方可执行文件。部署包应单独选择 Linux 架构并核验哈希，不混用测试包。

官方技术来源：

- Hysteria [服务端配置](https://v2.hysteria.network/docs/advanced/Full-Server-Config/)、[ACL](https://v2.hysteria.network/docs/advanced/ACL/)、[JSON 支持](https://v2.hysteria.network/docs/misc/Hate-YAML/)、[发行版](https://github.com/HyNetworks/hysteria/releases/tag/app/v2.12.2)。ACL 参数顺序、SOCKS 映射、监听字段和 TLS 均以此核对。
- sing-box [WireGuard endpoint](https://sing-box.sagernet.org/configuration/endpoint/wireguard/)、[DNS HTTPS](https://sing-box.sagernet.org/configuration/dns/server/https/)、[迁移说明](https://sing-box.sagernet.org/migration/)、[发行版](https://github.com/SagerNet/sing-box/releases/tag/v1.14.0)。旧 WireGuard outbound 已淘汰，不能用于本基线。
- Xray [Reality](https://xtls.github.io/config/transports/reality.html)、[发行版](https://github.com/XTLS/Xray-core/releases/tag/v26.3.27)。短 ID 和密钥配对须与客户端一致。
- Mihomo [TLS](https://wiki.metacubex.one/en/config/proxies/tls/)、[Hysteria2](https://wiki.metacubex.one/en/config/proxies/hysteria2/)、[VLESS](https://wiki.metacubex.one/en/config/proxies/vless/)、[发行版](https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.30)。
- systemd [service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)、[systemd-run](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)。恢复使用 transient timer，不承诺跨重启。
- Cloudflare [WARP 隐私](https://developers.cloudflare.com/warp-client/privacy/)、[常见问题](https://developers.cloudflare.com/warp-client/known-issues-and-faq/)。WARP 新增信任方和可见元数据范围，不提供匿名或业务解锁保证。

## 同类成熟方案比较

以下是选型判断，不是对用户当前网络的实测排名。部署可行性还取决于地域、网络、客户端及服务器系统。

| 项目 | 适合什么 | 与本包的差别 |
|---|---|---|
| [Amnezia](https://docs.amnezia.org/documentation/instructions/install-vpn-on-server/) | 已有 VPS，希望从客户端完成自建和维护 | 集成产品路径、安装与客户端体验更完整；若优先省维护，应先评估它。本包保留对 Hy2/Reality/WARP 的细粒度控制，维护负担更高 |
| [Outline](https://getoutline.org/) | 简单私有访问、分享访问密钥、图形化管理 | Manager/Client 工作流成熟；传输特征、适配和实际跨网可用性需单独测试，不保证适合所有网络 |
| [wg-easy](https://github.com/wg-easy/wg-easy) | 标准 WireGuard 管理、可信网络/远程访问 | 易管理，但直接 WireGuard 的可达性不能从协议安全性推导出来；管理界面也增加需要保护的入口 |
| [Algo](https://github.com/trailofbits/algo) | 可重复部署个人 VPN | 自动化工程更成熟；其设计目标不能等同于所有网络限制环境的可用性 |

结论：本包是 Agent 辅助操作与核查工具，不是与上述成熟客户端产品同等完整的软件。用户已选择保留原技术路线，所以只借鉴其最小步骤、版本约束、权限与验收方式；不暗中改成另一个产品的安装流程。

## 授权与第三方材料

本包正文、模板与辅助脚本由作者授权采用 [MIT 许可证](../LICENSE) 发布，公开署名 JoyZhang666。各第三方项目遵循自己的仓库 LICENSE；本包只链接文档并编写自己的模板与说明，不打包第三方代码或二进制，也不替第三方重新授权。

## v0.3.0 新增经验与接口来源

维护者原创实战记录《YouTube 云 IP 风控解决方案 v1.1》（2026-09-06）经全文阅读后提炼为 [field-lessons.md](field-lessons.md)，纠正过度归因与配置隐患；私人笔记正文、ID、链接和基础设施信息不随包发布。使用不依赖原笔记。历史案例的业务验收与本包新模板验证分别记录。

2026-09-29 核查官方 [Mihomo WireGuard](https://wiki.metacubex.one/config/proxies/wg/)、[DNS](https://wiki.metacubex.one/config/dns/)、[dialer-proxy](https://wiki.metacubex.one/config/proxies/dialer-proxy/) 与 [YouTube 错误排查](https://support.google.com/youtube/answer/3037019?hl=en)。接口参考不等于长期服务承诺。wgcf 只作为可选第三方工具链接，不打包或自动执行。
