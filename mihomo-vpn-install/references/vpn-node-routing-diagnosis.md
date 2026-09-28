# 节点、订阅与路由诊断

## 先分层

| 观察 | 下一步 |
|---|---|
| HTTP/SOCKS 监听不存在 | 查看 mihomo 服务与配置校验结果 |
| 本地 controller 502 | 确认请求没有被环境代理转发，见[回环排查](localhost-proxy-loopback-bug.md) |
| 只有一个目标失败 | 对相同目标做多节点、多次对照，不把单一健康检查当全部业务 |
| 所有节点失败 | 核查共同入口、DNS、当前网络与目标策略，不立即判定供应商宕机 |
| proxy not exist | 核对组的实际 `all` 列表、provider、筛选规则和名称编码 |

API 查询使用实际 controller 地址并保持认证。`GET /proxies` 返回对象，节点在 `proxies` 字段内；history 是记录列表，不是全局 RTT 字典。返回内容仍可能包含敏感节点名，只在私有环境查看。

## 节点选择与刷新

节点名称必须与实际名称完全一致，存在 emoji 时保留，不能假定所有节点都有 emoji。路径中的组名和节点名使用 URL 编码，JSON 请求体用序列化器生成，不拼接不可信 Shell 字符串。

| 目的 | API 方法与路径 |
|---|---|
| 查看指定组 | GET `/proxies/{group}` |
| 选择节点 | PUT `/proxies/{group}`，JSON 字段 `name` |
| 测指定节点 | GET `/proxies/{node}/delay`，指定目标和超时 |
| 查看订阅集合 | GET `/providers/proxies/{provider}` |
| 刷新订阅集合 | PUT `/providers/proxies/{provider}` |

以上依据[官方 API](https://wiki.metacubex.one/api/)，实际字段与能力按目标版本确认。探活会联网，刷新会更新缓存；不能因使用 GET/PUT 就忽略副作用或授权。

筛选规则决定可用集合，不等于指定默认节点。用[官方 provider 配置](https://wiki.metacubex.one/config/proxy-providers/)中的筛选字段表达需求，并在目标版本校验；不要从旧文档复制未验证的正则技巧。

## 端口检查

本地 7890/7891 是客户端监听，远端节点端口是另一端。只有后者需要端点探测。使用[端口脚本](../scripts/diagnose-airport-server.py)，输入由用户提供的私有 JSON 列表；脚本不读取订阅、不拉取节点、不输出域名或密码。

全部端口不可达只说明当前来源到这些端点失败；DNS、路由、防火墙和对端服务都可能导致。端口 OPEN 也不证明协议、密码和业务正常。节点切换采用[切前切后对照](probe-baseline-switch-compare-workflow.md)，完成后确认当前选中状态。
