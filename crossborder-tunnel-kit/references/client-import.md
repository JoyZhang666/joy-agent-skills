# 拿到 YAML 后如何连接

## 交付前由 Agent 完成

1. 确认用户设备、客户端名称、版本及内置内核。交付格式为 **Mihomo 配置 YAML**；按路线支持 Hysteria2 或 VMess/WebSocket/TLS，选择客户端 WARP 链式方案时还需支持 WireGuard 与 dialer-proxy。不可拿其他软件的 WireGuard 原生配置导入入口来接收此文件。
2. 确认 VPS 已按授权部署、TLS 验证开启、对应服务及入口可用。Hysteria2 使用 UDP；CDN 使用限定 Cloudflare 来源的 TCP443。Hysteria2 默认无域名主线使用 `client-hy2-pinned.template.json`；域名直连使用 `client-hy2.template.json`；客户端 WARP 链式使用 `client-hy2-warp.template.json`；CDN 路线使用 `cdn.py`。先保留已工作的旧配置，再生成新文件。
3. Hysteria2 按 [inputs.md](inputs.md)、CDN 按 [cdn-warp.md](cdn-warp.md)，在私有目录生成 `tunnel-client.yaml`；检查残留占位符、两端参数和证书，执行 [verification.md](verification.md) 中的原生解析及真实线路探测。不能把模板或虚构测试配置交给用户当作可用节点。
4. 给用户真实可点击的文件路径、适用客户端、导入步骤、节点选择及验收结果。手机文件传输须选用户确认的私密方式，不能上传公开仓库、公共转换网站或在线 YAML 校验器。

## 用户在客户端中操作

1. **保留旧配置。** 记住原配置名称，先不要删除。桌面端打开“配置／Profiles”，找“导入本地文件／Import”；手机端通常在“配置／添加配置”中选择“从文件导入”。菜单随软件变化，由 Agent 对照实际界面指导。
2. **选择个人文件。** 选 Agent 交付的 `tunnel-client.yaml`。不是 GitHub 的 `.template.json`，也不是 VPS 服务端文件。如出现未知字段、解析错误或残留大括号，停止启用，按[故障 F01](troubleshooting.md)处理。
3. **启用配置。** 选中刚导入的配置，保持 Rule／规则模式。Hysteria2 主线 `SELECT` 组选 `HY2`；客户端链式方案另在 `GOOGLE` 组选 `WARP-via-HY2`；CDN 路线选择 `SILICON` 组中的 `SILICON-CDN-WARP`，双入口配置显示 `-A`、`-B`。不要切 Global 模式后还期待域名分流规则生效。
4. **让目标应用使用代理。** 配置默认只监听本机，TUN 关闭。桌面应用可使用客户端显示的本机 HTTP/SOCKS 代理；如用户同意全系统代理，再开启客户端的“系统代理”，并说明哪些应用可能不遵循它。手机“启动／连接”可能请求系统 VPN 权限，由用户确认。TUN、DNS 劫持和全系统 IPv6 处理须单独规划，不能默默打开。
5. **确认实际可用。** 打开目标应用，查看连接记录确实经过所选节点，再测试网页与视频。节点延迟显示数字、导入成功或图标变绿均不足以证明播放成功。链式路线按 [client-warp.md](client-warp.md) 做完整验收。

## 出错时怎么退回

先切回之前可用的配置，恢复原来的系统代理／应用设置。只回退本次改动；不要卸载客户端或删除密钥。链式方案也可将整个 `GOOGLE` 组选回 `HY2`，但这会恢复旧出口，未必解决平台风控。将脱敏后的错误类别交给 Agent，按[故障索引](troubleshooting.md)继续排查。

CDN 方案没有直出备选节点；WARP 失联时连接会失败。需要临时恢复其他网络时切回原订阅。
它与用于国内远控的回国出口配置作用不同，应按当前用途选择，不能期待境外出口呈现指定国内位置。
