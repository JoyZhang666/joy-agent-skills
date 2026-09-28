# 可选备线与 WARP

## 优先选择哪条路线

Hy2 已连接但 YouTube/Google 出口有问题时，先读 [故障索引](troubleshooting.md) 和 [客户端 WARP-over-Hy2](client-warp.md)。该方案已有独立模板，优先在一台客户端验证，无须改服务器。下面的服务端 WARP 是需要集中管理时的另一条路线，不要把两者的参数、回退命令或验证结果混用。


## Reality 备线

需要应对 UDP 不通等已确认问题时，再添加 Xray Reality：使用 `server-xray-reality.template.json` 和 `client-hy2-reality.template.json`，`SELECT` 手动选 HY2 或 REALITY。服务端 shortIds 与客户端 short-id 必须一致且非空。目标域名需从 VPS 实测，不把某个固定网站作为永久可靠前提。

Reality 模板默认直接访问公网，不接 WARP。两种协议在同一 VPS 上只能分散协议层故障；IP 封锁、主机故障、流量额度耗尽和供应商停机仍共同失效。主机级容灾需要另一个独立节点和单独授权。

## WARP 出口

仅当存在可重复的出口问题，并且用户同意让 Cloudflare 成为额外网络处理方时添加。WARP 不等于匿名、住宅 IP 或解锁保证；网站风控还受账户、地区、客户端、DNS、时间和行为影响。使用官方资料核查隐私与服务约束。

`server-singbox-warp.template.json` 使用 sing-box 1.14 的 WireGuard **endpoint**，不是已移除的 WireGuard outbound。`system:false` 在用户态运行，入站仅回环 SOCKS，模板不创建 TUN、不改系统默认路由。远程 DNS 经该 endpoint；peer 使用数字地址避免依赖自身 DNS。

先独立验证回环 SOCKS 的 DNS、TCP/UDP 和出口，再用 `server-hysteria2-warp.template.json` 替换已验收的 Hysteria 配置。ACL 形式是 `warp(suffix:domain)`，末尾 direct。这里只给两个域名后缀的示例，不是完整平台域名清单；客户端若已解析成 IP，服务器未必能按域名匹配。必须用路由日志或受控连接证明实际流量命中；必要时独立评估嗅探配置和隐私影响。不得把“加载了 ACL”写成“平台已从 WARP 出口”。

不默认封禁 UDP/443。如果业务要求用 TCP 回退验证，应把 reject 规则放在转发规则之前，并验证客户端确实回退；仅屏蔽一端端口不保证业务走 TCP。MTU 1280 是保守的模板起点，不是所有网络的最优值；以路径 MTU、分片和丢包实验决定调整。WARP IPv6 不在本模板支持范围。

WARP 注册不是本包能力。不接入来源不明的公共账号、共享私钥或把私钥发给第三方配置生成网站；若没有自己有效的配置，停在准备阶段。关闭/卸载 WARP 时只撤销本批新增服务和恢复已备份的 Hy2 配置，不能停掉用户本来已有的同名服务。
