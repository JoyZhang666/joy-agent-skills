# 验证与验收

分开记录三个层次：公开材料静态检查；虚构数据/命令模拟与原生解析；获授权环境中的真实运行验收。前两层通过不能替代第三层。

原生解析命令（对渲染后的文件）：

```text
sing-box check -c CONFIG
xray run -test -config CONFIG
mihomo -t -d PRIVATE_EMPTY_DIRECTORY -f CONFIG
systemd-analyze verify UNIT_FILE
```

Mihomo 模板不引用外部规则数据库，解析时无需下载 geo 数据。后续加入外部规则或 provider，重新核查解析过程可能产生的网络行为。Hysteria 本版未采用经确认的纯检查命令；不得执行 `hysteria server` 来冒充静态验证。此项在隔离 Linux 环境使用有效测试证书做真实启动验收。

真实环境验收清单：

- 新服务用户/权限/版本/监听符合计划，既有 SSH 和服务可用；运行配置残留占位符为零。
- 主线真实握手，正常证书校验；错误证书/SNI 必须拒绝。
- 显式代理应用的 DNS、HTTP、长连接和所需 UDP 可用，出口与计划一致；直连流量命中相应规则。
- 系统代理、TUN、IPv4/IPv6 分别实测。`ipv6:false` 只是客户端配置，不证明系统 IPv6 被封闭；不能据此宣称无泄漏。需要全系统范围时增加 DNS/IPv6/进程覆盖实验及断线行为验收。
- Reality 切换实测；WARP 按域名选择及未选流量实测；平台解锁只报告本次观测，不承诺长期有效。
- 验证 timer 真正触发恢复、缺失备份时拒绝、取消后的 `.timer`/`.service` 状态、恢复失败的非零退出；保留人工控制台恢复能力。
- 授权后重启验证持久化；transient timer 不承诺跨重启。

基线外部查询 `python scripts/baseline.py --external-ip` 会联系 Cloudflare，并输出该次请求的 IP（敏感证据）。它使用当前进程代理环境，只能证明这一次 HTTP 请求，不能证明整个系统路由。默认基线不查询公网。
