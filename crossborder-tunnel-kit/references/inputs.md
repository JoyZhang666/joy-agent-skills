# 模板输入与秘密管理

参数文件是一个 JSON 对象，键名对应 `{{UPPER_SNAKE_CASE}}`。仅填本次路线需要的字段。真实文件不得进入 Git、聊天、订阅网站或诊断附件。

| 参数 | 类型与约束 |
|---|---|
| SERVER_HOST | VPS IP 或已解析域名；示例使用保留域名，不复用别人地址 |
| HY2_UDP_PORT / REALITY_TCP_PORT | JSON 整数，1..65535；相同数值可分别用于 UDP/TCP，仍须核查占用 |
| HY2_PASSWORD | 用户本地生成高熵口令；客户端与服务端相同 |
| TLS_SERVER_NAME | 有效证书 SAN 中的域名 |
| TLS_CERT_PATH / TLS_KEY_PATH | Linux 绝对文件路径，服务用户可读，私钥不可公开 |
| REALITY_UUID | 本地生成 UUID，两端同一用户标识 |
| REALITY_TARGET | 经 VPS 实测支持所需 TLS 特性的目标域名，无 scheme、路径或端口 |
| REALITY_PRIVATE_KEY / REALITY_PUBLIC_KEY | Xray 本地一次生成的 X25519 配对材料，URL-safe Base64；服务端用私钥，客户端用对应公钥 |
| REALITY_SHORT_ID | 非空、偶数长度十六进制串，最多 16 字符；两端一致 |
| WARP_IPV4 | 客户端 WARP 的 Interface IPv4，不带 `/32`；与自己的 profile 一致，不能照抄他人地址 |
| WARP_MTU | 客户端 WARP 的 JSON 整数；仅 IPv4 模板可从案例值 1100 对照 1280 测试，不是通用最优值 |
| WARP_IPV4_CIDR | 用户自己注册并合法持有的 WARP 配置分配的 IPv4/CIDR |
| WARP_PRIVATE_KEY / WARP_PUBLIC_KEY | 配置中本地私钥与 peer 公钥，标准 Base64 编码 32 字节；不是 Reality 密钥 |
| WARP_ENDPOINT_IP / WARP_ENDPOINT_PORT | 配置中的 peer 数字 IP / 整数端口，使用 IP 避免引导 DNS 循环 |
| WARP_RESERVED | 配置所需的 3 个 0..255 整数列表，不能拿别人的值代填 |

密钥生成命令的输出也属于秘密：在用户控制的终端写入权限受限文件，不捕获到 Agent 工具输出。公开示例只有占位符。解析用虚构测试值不能部署。

用法（在 skill 根目录）：

```text
python scripts/render.py examples/server-hysteria2.template.json --values PRIVATE_VALUES_FILE --output NEW_CONFIG_FILE
python scripts/scan.py NEW_CONFIG_FILE --runtime
```

`render.py` 不覆盖已有文件；完整占位符可替换为数值或列表，嵌入字符串按字符串处理；只负责渲染与必要输入检查，不代替原生 schema 检查。Linux 参数文件要求无组/其他权限，输出创建为 0600。Windows 模式位不能证明 ACL 私密：使用当前用户私密目录并核对 `icacls` 结果，不在共享工作目录存真实凭据。上级路径也应由可信用户控制；脚本不提供对抗同机管理员的保密保证。

共享发布前：`python scripts/scan.py PUBLIC_DIRECTORY`。公开扫描检查所有扩展名，发现只输出文件/行号/类别；文档地址和少量公开 DNS 地址有窄范围豁免。不存在、二进制、无法解码/读取、符号链接均报错。退出码 0 表示所选模式未发现规则命中，1 表示命中，2 表示扫描失败。`--runtime` 只找残留占位符，绝不能作为脱敏扫描。扫描器不是密钥保险箱；人工复核项目名称、账户、日志、截图和授权信息。

## 客户端 YAML 输出

参数文件仍是私有 JSON；输出名以 `.yaml` 或 `.yml` 结尾时，渲染器生成块状 YAML（字符串逐项转义、数字保留类型），其他后缀继续输出 JSON。模板仍以 JSON 存储，用户无需直接导入模板。

```text
python scripts/render.py examples/client-hy2.template.json --values PRIVATE_VALUES_FILE --output PRIVATE_DIRECTORY/tunnel-client.yaml
python scripts/render.py examples/client-hy2-warp.template.json --values PRIVATE_VALUES_FILE --output PRIVATE_DIRECTORY/tunnel-client-warp.yaml
```

这里的大写路径是说明用占位符：Agent 必须换成用户已确认的私密目录和实际文件路径，包含空格时加引号。只执行所选路线的一条命令，缺少 WARP 资料时交付主线 YAML；不得编造值。

WARP 客户端模板仅 IPv4：`SERVER_HOST` 与 `WARP_ENDPOINT_IP` 使用已确认的数字 IPv4，避免代理与 DNS 引导循环；`TLS_SERVER_NAME` 仍填真实证书匹配域名。WireGuard 私钥、公钥解码后应各为 32 字节；port 必须是有效整数。若自己的 profile 要求 reserved，按 [client-warp.md](client-warp.md) 添加自己的值后再渲染和原生校验。
