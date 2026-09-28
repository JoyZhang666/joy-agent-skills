# 客户端 WARP-over-Hy2：YouTube/Google 出口方案

适用：Hy2 已实测可用，但 YouTube 播放或 Google 会话仍异常。先查 [F03–F07](troubleshooting.md)，排除 DNS、规则、账号和内容限制；不是所有播放失败都要加 WARP。

## 路线与前提

`目标应用 → 本机 Mihomo → 已有 HY2 VPS → WARP → 目标网站`。WireGuard 节点的 `dialer-proxy: HY2` 是链式关键；服务器本身无须安装 WARP 或更改 DNS／路由。经用户同意，Cloudflare 成为额外流量处理方。

用户需持有有效、获准使用的 WARP WireGuard profile；官方 WARP 应用并不等于一定能导出这种 profile。本包不注册账户。可在核查当前服务条款及风险后评估第三方 [wgcf](https://github.com/ViRb3/wgcf)，它并非 Cloudflare 官方项目；下载版本、来源和校验值需另行核实，遇限流停止，不批量注册或无限重试。无有效 profile 时不生成可用链式配置，保留 HY2 主线。

## 已包含的模板与参数

使用 [client-hy2-warp.template.json](../examples/client-hy2-warp.template.json)，由 [render.py](../scripts/render.py) 输出 `tunnel-client-warp.yaml`。模板只支持 IPv4，保留 TLS 校验和回环监听，不启用 TUN，不依赖 geosite/geoip 数据库。

| 用户私有 profile 字段 | 输入参数／处理 |
|---|---|
| Interface Address 的 IPv4 | `WARP_IPV4`，去掉掩码；不能用旧案例地址 |
| Interface PrivateKey | `WARP_PRIVATE_KEY`；仅在私密文件中读取填写 |
| Peer PublicKey | `WARP_PUBLIC_KEY`；使用同一 profile 的配套值 |
| Peer Endpoint | 拆成 `WARP_ENDPOINT_IP` 和整数 `WARP_ENDPOINT_PORT`；若给的是域名，先用可信解析核对数字 IPv4，记录来源与时间 |
| 如配置确实要求 reserved | 只采用本人配置的三个整数；在私有模板副本中新增 `reserved: "{{WARP_RESERVED}}"`，输入中填整数数组；不随意编造或用别人的值 |
| 客户端 MTU | `WARP_MTU` 整数；历史 IPv4 案例最终使用 1100，可与 1280 对照，按实际丢包和播放决定 |

`SERVER_HOST` 在此路线优先使用已核实的 VPS 数字 IPv4，SNI 使用证书域名。DNS 通过指定的 `#HY2` 加密解析；代理域名的引导解析单独设置，不能让“找到 HY2”依赖“HY2 已连接”。模板的 WireGuard 启用远端 DNS；需连同客户端 DNS 配置一起实测，不把 WireGuard 概括为“永远只能本地解析”。

## 将经验落实到配置

- **DNS 错误：** 模板为目标查询提供经 HY2 的 DoH，并设置代理服务器引导解析；不会更改操作系统 DNS。若应用自行 DoH 或在进入代理前解析，应另查该应用的真实请求路径，不能假定配置文件已接管它。
- **会话出口分裂：** 14 条显式域名后缀规则把视频、登录、静态资源和 API 统一送到 `GOOGLE` 组，位于最终规则之前。组内一次只选同一出口；普通流量保留 `SELECT`。这也会影响 Google 搜索等服务，须向用户说明。
- **规则覆盖：** 域名表是案例基线，不是永久完整清单。用连接记录查遗漏，按证据添加；不默认引入需下载的 geodata。已有国内直连规则须单独审阅后合并，保持 Google 规则在宽泛直连和 MATCH 之前。
- **MTU：** 将封装参数作为明确输入，不把一次成功值当成所有网络通用值。
- **QUIC：** 默认不拒绝 UDP/443。仅在证据表明业务 UDP 有问题时，评估临时 TCP 回退；如测试全局拒绝规则，应放在域名转发规则之前并说明会影响其他 QUIC 流量。确认应用实际回退、保留原规则，不要封掉 HY2 或 WARP 承载所需端口。

官方接口依据：[WireGuard 字段](https://wiki.metacubex.one/config/proxies/wg/)、[DNS 路由与引导](https://wiki.metacubex.one/config/dns/)、[dialer-proxy](https://wiki.metacubex.one/config/proxies/dialer-proxy/)。以上是接口依据，不代表当前网络已验收。

## 验收顺序

1. 私有目录内原生校验 YAML；导入后再检查 GUI 是否重写字段、配置是否实际生效。保留旧 YAML。
2. 同一设备、网络、账号和失败视频样本下做 HY2 基线；随后只切换整个 GOOGLE 组到 WARP。登录、视频和 CDN 连接都须命中预期组，避免只看首页。
3. 出口查询也必须走待测节点：普通 IP 查询域名默认可能走 HY2，不能据此断言 WARP 失败。用客户端可验证的节点测试，或在私有测试副本中临时添加单个查询域名的路由，确认命中后查询并移除。只在私密记录中保存出口 IP。
4. 测试至少 5 个此前失败的普通视频（起播、拖动、连续 5 分钟）、3 个音乐 MV、2 个直播（各 5 分钟）；账号不需要 Premium 才能测试。再检查非 Google 流量未误分流；若合并了国内直连，也核验国内样本。
5. 写明时间、应用与内核版本、规则命中、出口、三个播放类别的结果和未测项。历史案例成功不能替代当前结果；若用户无法执行，只交付“已生成／已解析、待实测”。

## 失败与回退

- 握手失败：核对自己的 Endpoint、地址、密钥、客户端内核、HY2 的 UDP 承载；先回到 HY2 基线，不改 VPS 网络栈。
- 播放失败：按故障索引查 DNS／会话出口／MTU，再判断候选出口问题。WARP 不是住宅 IP、匿名或永久解锁保证。
- 只改客户端时，通过切回旧 YAML 或整体切回 GOOGLE 组回退。`warp-cli disconnect/connect` 管理的是独立 WARP 客户端服务，**不能轮换 Mihomo 内置 WireGuard 节点**；本包不实现自动出口轮换或定时监控。
- 若用户愿意，可有限次数重新连接并记录出口是否真的变化，未变化就停止把它当换 IP；遇限流停止。其他独立出口或付费服务只在另行选择、确认费用与隐私后评估，不以更换服务器地区保证解决。
- 需要集中管理多设备时，才评估 [服务端 WARP 路线](optional-routes.md)；不与本客户端方案同时实施。
