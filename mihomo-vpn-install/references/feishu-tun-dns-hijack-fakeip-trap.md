# TUN DNS 接管与 SERVFAIL

出现 NameResolutionError、SERVFAIL 或应用重连时，同时检查系统解析和本地 TUN/DNS 接管，不能只怀疑上游解析服务器。

## 诊断

- 查当前主配置中的 DNS 开关、监听地址、nameserver，以及 TUN 的 dns-hijack、路由与接口。
- 查看 controller 已暴露的字段。GET 响应缺少 DNS 字段不等于 DNS 模块关闭，须结合主配置、监听与实际查询。
- 查看系统解析服务及路由，核对 DNS 查询究竟到哪里。接口名不一定是 Meta，fake-IP 范围也可能自定义。
- `198.18.0.0/15` 可作为 fake-IP 示例，但发现此网段不等于已定位故障；检查 listener、查询响应与路由证据。

DNS 接管到无法提供解析的路径可能造成故障；是否涉及 mihomo、系统解析器、其他 VPN 或防火墙，需要逐层验证。

## 修复选择

在授权范围内选择：修正 DNS 配置与接管规则，或临时停用 TUN 并确保依赖应用已有可用的显式代理。DNS 监听端口不冲突只是前提，还要验证实际查询结果。

部分运行配置更新使用 PATCH，配置重载使用 PUT，按[官方 API](https://wiki.metacubex.one/api/)和所用版本确认支持字段。没有独立的 undo 端点不表示只能重启；可恢复已保存的相应字段或经验证的私有配置备份。

验证系统解析、代理请求和目标应用，观察变更之后的新错误。零日志错误不等于业务成功；新错误也需要关联证据才能归因于本次变更。

来源：[官方 TUN 配置](https://wiki.metacubex.one/config/inbound/tun/)。关闭 TUN 的细化流程见[回归 SOP](tun-disable-regression-sop.md)。
