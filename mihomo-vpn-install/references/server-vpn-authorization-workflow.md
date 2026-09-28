# Linux 安装与配置工作流

适用于经用户授权的 Linux 主机。默认采用显式 HTTP/SOCKS 代理；已有运行服务时先审查差异，不能覆盖重装。配置示例使用标准安装路径，用户可选择其他路径。

## 1. 预检查

在目标主机核对 `uname -m`、`uname -r`、磁盘空间以及 `ss -ltn` 中的端口占用。7890、7891、9090 是本包示例端口，不是必须值。确认安装方式、服务运行用户与现有网络依赖。

只诊断时停在证据收集，不自动下载、安装或重启。必要的变更记录见[风险模板](risk-analysis-template.md)。

## 2. 获取二进制

从 [mihomo Releases](https://github.com/MetaCubeX/mihomo/releases) 选择与目标架构、CPU 指令集及系统兼容的明确版本。不要仅凭旧案例的内核号决定下载文件，也不默认追随 latest。

按[下载检查](github-mirrors.md)验证发布者与同一资产的校验信息，再解压、授权执行和查看版本。下载成功不等于内容可信；不要忽略校验失败继续运行。

## 3. 配置私有工作目录

1. 选择二进制位置（例如 `/opt/mihomo/mihomo`）与私有配置目录（例如 `/etc/mihomo`）。
2. 将[注释模板](mihomo-config-annotated.yaml)复制到私有配置目录，填写用户自己的订阅及独立 controller 密钥。文件只向服务用户开放，Linux 可使用目录 700、文件 600。
3. 模板中的 `.invalid` URL 不可用；真实配置不能存回 Skill 或 Git 工作目录。确认缓存目录也受限。
4. 使用 provider 的 `use` 引用；筛选前先在本地确认节点命名。`filter` 是筛选，不保证选中某个默认节点。
5. 明确是否使用 GEOIP/GEOSITE；如果使用，其数据库另行按可信来源配置。本包最小模板不依赖它们。

配置检查可能触发订阅或数据库访问，须在已授权主机与网络范围内运行，并保护输出：

```bash
/opt/mihomo/mihomo -t -d /etc/mihomo
```

## 4. 服务定义

以下是 systemd 单元示例，需要安装授权。没有 `ExecReload`，因此不能假定 `systemctl reload` 可用。

```ini
[Unit]
Description=Mihomo Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/etc/mihomo
ExecStart=/opt/mihomo/mihomo -d /etc/mihomo
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=multi-user.target
```

按主机安全策略配置服务用户及权限；TUN 权限要求与仅显式代理不同。保存单元后经授权执行 daemon-reload、启动服务；开机自启是单独的持久设置，按用户选择决定。

## 5. 验证与应用接入

- 服务进程、配置路径和监听地址符合预期，controller 仅回环可达。
- 对同一无凭据 HTTPS 目标分别做直连和显式代理测试，区分网络响应与业务成功。
- 应用代理设置按实际应用生效位置配置；交互 shell 的环境不代表 systemd 服务环境。
- 需要本机访问的地址配置合适的 `NO_PROXY`；它不能替代 TUN 路由检查。
- 启用健康检查会产生周期网络请求，应在确认目标、频率和流量后开启。

## 6. 重载、回滚与卸载

修改前保留私有备份；区分运行配置 PATCH、配置重载 PUT 和服务重启，按[官方 API](https://wiki.metacubex.one/api/)及当前版本处理。重载后回读 provider、selector 和目标应用状态，失败则停止扩大变更。

回滚恢复本次改动的字段或已确认的备份，再按同样验证流程检查。不能把 GET 返回的局部状态直接当完整配置备份。卸载时列明服务、文件和其他应用引用，取得该范围授权后逐项处理；不提供全目录递归删除的一键命令。
