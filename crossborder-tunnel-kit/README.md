![Crossborder Tunnel Kit：自有 VPS 必需，自有域名可选](https://raw.githubusercontent.com/JoyZhang666/joy-agent-skills/main/assets/brand/crossborder-tunnel-kit.svg)

# Crossborder Tunnel Kit

**v0.4.0 · 自有 VPS 必需 · 自有域名可选，默认无需填写**

让 Agent 为自有或获授权的 Linux VPS 规划、部署和维护私有隧道，交付 Mihomo 客户端的个人 `tunnel-client.yaml`、导入指引和恢复说明。实际安装与网络验收由 Agent 在授权范围内完成；本项目不是一键安装器，也不提供服务器或共享节点。

[第一次使用](https://github.com/JoyZhang666/joy-agent-skills/blob/main/docs/start-here.md) · [Agent 入口](SKILL.md) · [全部作品](https://github.com/JoyZhang666/joy-agent-skills) · [MIT](LICENSE)

## 选择路线

| 路线 | 自有域名 | 交付与边界 |
|---|---|---|
| **默认：Hysteria2 直连** | **不要求，也不默认询问** | 服务器 IP、自签名证书与 SHA-256 指纹固定校验、本地 YAML |
| 可选：域名直连 | 选用时提供 | 域名与公共 CA 证书，沿用旧模板 |
| 可选：域名/CDN + WARP | 选用时提供可管理域名 | VMess AEAD / WebSocket / TLS、双入口回退；可加私密订阅与入口维护 |

无域名直连的节点 IP 对客户端可见；域名本身不隐藏 IP，CDN 才参与保护源站入口。CDN 和网站看到的出口是不同层：当前 CDN 组合使用 WARP 本地代理，WARP 失联时失败关闭，不自动直出。Hysteria2 可另加 Reality 或 WARP，见[可选路线](references/optional-routes.md)。同一 CDN 的两个入口不等于两家独立线路。

新部署默认阅读[无域名路线](references/no-domain.md)。只在用户选择域名直连或 CDN 后询问域名；没有域名不阻塞基础路线，不自动改造已有节点。

## 准备与开始使用

1. **VPS 与授权：**自有或获授权的 Linux VPS，已验证的 SSH 主机身份、root/sudo 权限和云控制台恢复入口。核对系统、架构、网络和端口占用。Hysteria2 需要 UDP 可达，CDN 需提供商回源 TCP 443。
2. **客户端：**确认实际设备、软件和内核版本；Clash Verge Rev、Clash Meta for Android 等需支持所选协议。YAML 不是所有 VPN 软件通用格式。
3. **私有配置：**Agent 在私密目录生成认证与证书材料，准备[私有参数](references/inputs.md)，执行原生检查。默认无域名使用 `client-hy2-pinned.template.json`；域名直连沿用旧模板，CDN 使用 `cdn.py`。
4. **部署与导入：**按[部署说明](references/deployment.md)应用已获授权的服务器变更；客户端“配置/Profiles”导入并启用 YAML。Hysteria2 选择 `SELECT → HY2`；CDN 选择 `SILICON` 组中的 A/B 节点，详见[导入指南](references/client-import.md)。
5. **验收与恢复：**实际请求、出口和目标应用通过才算交付。按用户需要启用系统代理/TUN；保留旧配置与[恢复步骤](references/rollback.md)。节点出现延迟数值不等于视频成功。

**没有 VPS：**先指导用户申请获授权服务器或选择云服务商，费用与购买由用户确认。无法取得时说明部署和真实线路交付不能继续，仅提供准备清单，不用示例节点冒充服务。

Python 工具只需 **Python 3.10+ 标准库**。实际部署另需经校验的官方核心、Linux/systemd和OpenSSL；CDN 还需可管理域名、DNS-01证书及续期、官方 WARP 本地代理，见[CDN 工作流](references/cdn-warp.md)。默认客户端只监听回环，TUN关闭，不自动接管整机网络。

## v0.4.0 新能力

- 默认无需自有域名：证书指纹模板、严格渲染校验、证书轮换说明及真实 TLS 正反向测试。
- 可选 CDN：域名 TLS 与 WebSocket Host 一致；按接入网络实测的双入口回退和独立节点引导 DNS。
- 运维工具：生成、规划、检查、部署、导出、回滚、专用来源防火墙与证书切换，保留既有业务。
- 私密订阅：随机 HTTPS 链接、受限 SSH 发布、白名单与哈希校验、原子替换及上一版恢复。
- 入口维护：接入端每48小时巡检；现用入口异常5分钟后复核一次；全坏或发布失败保留原配置。

| 频率 | 对象 | 作用 |
|---|---|---|
| 60秒 | 客户端 fallback 组 | 按内核健康检查行为，在已下发入口之间回退 |
| 建议6小时 | 客户端订阅更新 | 下载服务端新配置；需在实际客户端设置 |
| 48小时 | 固定接入网络监测任务 | 检查有限候选池，需要时更新订阅入口 |

私密 HTTPS 订阅和入口更新是已跑通 CDN 路线的可选能力，详见[参数、安装契约与验收](references/private-subscription.md)。它们与隧道共享 CDN/源站，全部不可达时不能保证下载到修复配置。默认无域名路线交付本地 YAML。

## 工具与副作用

| 工具 | 用途 |
|---|---|
| `render.py TEMPLATE --values PRIVATE_JSON --output NEW_FILE` | 生成 JSON/YAML，拒绝覆盖；旧命令兼容 |
| `cdn.py --values PRIVATE_JSON --output NEW_DIRECTORY` | 生成 CDN 服务端与客户端配置，不启动服务 |
| `manage.py plan/apply/status/check/export/rollback --deployment PRIVATE_JSON --json` | 专用服务管理；apply/rollback 有变更，export 另需 --output |
| `firewall.py`、`renew_cert.py` | 专用来源规则、证书部署；按 CDN 工作流操作 |
| `probe.py` | 临时回环端口、TUN关闭的显式代理探测；指定物理接口区分已有VPN经转 |
| `subscription.py`、`edge_monitor.py` | 受限发布与接入端监测，调度由安装者配置 |
| `baseline.py`、`scan.py`、`verify.py` | 本地检查；baseline --external-ip 才访问公网；scan --runtime 仅查占位符 |
| `safety.py` | 默认审阅；Linux root 的 --apply 可修改配置/服务/timer，先完成恢复准备 |

公开包只有通用源码、模板、虚构测试与文档。真实 YAML、私钥、口令和私密订阅链接只保存到用户控制的私密目录；不放公开 Issue、日志或在线转换网站。扫描无发现不能代替人工审查。

## 验证与适用边界

2026-11-07，维护者确认参考部署运行正常并通过实际使用验收：Windows、Android、YouTube 播放和两端私密订阅导入/手动更新成功。公网 CDN、错误认证/路径、WARP失败关闭、订阅发布/读回/恢复、证书续期演练和真实调度触发另有工程记录。

发布回归覆盖 Windows/Linux，默认无域名路线在隔离 Linux 网络中检查真实 Hysteria2/Mihomo 握手、错误/缺失指纹、证书替换及同步轮换。版本及复现入口见 [versions.json](references/versions.json) 和 [测试说明](references/testing.md)。

用户实际使用验收、隔离测试与解析检查分别记录，不延伸为所有运营商、所有客户端、系统DNS/IPv6零泄漏、连续30分钟1080p或自动订阅刷新周期的独立测量结论。新部署须在自己的网络验收，不保证永久连通、解锁、匿名或无限视频流量。

视频失败先看[故障索引](references/troubleshooting.md)、[WARP链式说明](references/client-warp.md)和[实战经验](references/field-lessons.md)。向[仓库 Issues](https://github.com/JoyZhang666/joy-agent-skills/issues)反馈时只提供脱敏现象。来源及许可见 [LICENSE-NOTICE](LICENSE-NOTICE.md)。

从 v0.3.0 升级无需重新生成已有可用 YAML，新能力按需使用。封面和仓库导航为可选在线资源，核心说明可离线阅读。
