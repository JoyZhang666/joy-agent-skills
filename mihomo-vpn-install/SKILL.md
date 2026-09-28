---
name: mihomo-vpn-install
description: 在 Linux 上规划、安装和排查 mihomo 代理，处理订阅格式、节点切换、代理链、TUN/DNS 和回环连接问题。先定位故障层，再按用户授权变更；不自动获取订阅或重启服务。
license: MIT
metadata:
  version: "2.1.2"
  author: JoyZhang666
---

# mihomo 安装与运维

按用户目标选择下表中的资料，不把历史案例当成当前机器事实。这里只描述操作方法；安装、重启、节点切换、网络探测和删除都应落在用户已授权的对象与范围内。工具明确拒绝操作时遵循其审批流程，不通过换命令或 API 绕过。

## 处理顺序

1. 明确目标主机、现有服务、是否只诊断、允许的停机范围；不从历史路径推断当前主机。新安装先确认订阅或节点来源；缺少时主动询问，优先协助创建私有文件并给出具体打开、填写和保存步骤；文件操作不方便时，说明聊天留存风险，由用户选择在当前聊天提供订阅 URL。获取配置不等于获得任意下载或远程变更授权。未提供则标记“等待节点配置”，不以占位符启动或报告成功；已有获准读取的配置不重复索要。详见[安装流程](references/server-vpn-authorization-workflow.md)。
2. 只读确认版本、监听端口、进程代理设置、实际加载的主配置、TUN/DNS 状态和失败层。日志只输出必要的脱敏摘要。
3. 用同一目标与相同条件建立对照。HTTP 响应、TLS 连通、鉴权通过、业务成功分别记录。
4. 需要变更时，说明差异与回滚方式，沿用已有授权；先备份、校验，再应用最小变更。
5. 回读运行状态并做目标业务验证。配置写盘、API 返回成功和业务恢复不是同一件事。

## 资料路由

| 任务 | 包内资料 |
|---|---|
| 新安装、服务与回滚 | [安装流程](references/server-vpn-authorization-workflow.md)、[风险模板](references/risk-analysis-template.md)、[配置模板](references/mihomo-config-annotated.yaml) |
| 二进制来源、订阅格式与 403 | [下载及订阅检查](references/github-mirrors.md) |
| 切节点、延迟与多目标对照 | [节点诊断](references/vpn-node-routing-diagnosis.md)、[切前切后对比](references/probe-baseline-switch-compare-workflow.md) |
| TLS 故障、SS 接入与分批探测 | [服务连通性与订阅接入](references/codex-openai-ssl-issue.md)、[历史统计方法](references/airport-batch-probe-results.md) |
| 应用只有部分功能断联 | [进程与代理检查](references/feishu-feels-down-vpn-actually-down.md)、[Privoxy 错链](references/feishu-actually-privoxy-chain.md) |
| TUN 路由、DNS SERVFAIL、关闭 TUN | [TUN/TLS](references/feishu-gateway-tun-ssl-case.md)、[TUN/DNS](references/feishu-tun-dns-hijack-fakeip-trap.md)、[关闭 TUN 回归](references/tun-disable-regression-sop.md) |
| localhost 502、插件迁移 | [回环代理](references/localhost-proxy-loopback-bug.md)、[插件与代理职责](references/plugin-era-mihomo-rules.md) |
| 环境限制、Python 包安装故障 | [工具限制](references/hermes-terminal-restriction.md)、[依赖隔离](references/project-python-deps-install-when-env-broken.md) |

## 凭据与输出

- 订阅 URL 整体视为凭据，包括查询参数、路径中的密钥和嵌套编码；Base64、URL 编码都不是脱敏。
- Agent 不在回复中复述订阅 URL、订阅响应、节点密码、UUID、真实节点地址、完整环境变量、配置或鉴权响应，也不写入 Issue、Git 提交或公开日志。用户知情选择在当前聊天输入订阅 URL 的备用方式见安装流程；这不授权 Agent 再次回显。
- 真实订阅最终保存于访问受限的私有配置；可以由用户填写，也可以由 Agent 按用户授权写入。本包示例统一使用 `subscription.example.invalid`、`node.example.invalid`、`REPLACE_ME`。
- 读取现有配置时只报告数量、格式和错误类别；需要核对秘密时在本地比较，只返回相同/不同。
- 下载、解码、备份和临时配置都可能含凭据，使用限制访问的私有目录；清理应针对明确归属的文件，不按全系统进程名批量杀进程。

## API 与判断边界

本地 controller 请求应显式绕过环境 HTTP 代理；受 TUN 影响的路由仍需单独核查。controller 绑定回环地址；若启用认证，从私有配置提供凭据，不写进教程。

`PATCH /configs` 用于部分运行配置更新，`PUT /configs` 用于重载；不能从一次错误请求推断 PUT 永远无效。重载是否中断连接、systemd 是否支持 reload、哪些字段可热更新，都按目标版本与服务定义验证。详见[官方 API](https://wiki.metacubex.one/api/)。

HTTP 401/403 仅说明收到了 HTTP 响应，不能证明鉴权或业务可用；超时不能独自证明服务商宕机。节点名单、端口与计时均可能识别供应商，公开报告使用别名和汇总。

## 辅助脚本

脚本只依赖 Python 3.10+ 标准库，均可先运行 `--help`。默认不执行外部端口探测或文件删除。

- [回环对照](scripts/localhost-proxy-loopback-probe.py)：仅请求回环地址的指定健康检查端点，不读日志。
- [端口诊断](scripts/diagnose-airport-server.py)：读取用户指定的私有 JSON 端点列表；默认仅校验，显式 `--probe` 才联网；输出编号与状态，不回显地址。
- [临时配置清理](scripts/ss-probe-cleanup.py)：只处理指定目录的命名匹配文件；默认预览，`--apply` 才删除；不杀进程、不递归、不删来源包。

依赖、使用边界与版本整理说明见 [README](README.md)；第三方项目说明见 [NOTICE](NOTICE.md)。
