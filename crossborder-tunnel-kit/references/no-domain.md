# 默认路线：无需自有域名的 Hysteria2

适用于新部署。默认不询问或要求购买域名；先核对获授权的 Linux VPS、SSH 主机身份、UDP 可达性和 Mihomo 客户端。使用数字 IPv4 连接，IP 对客户端可见；这条路线没有 CDN 隐藏源站或 CDN 入口维护能力。保留已有可用部署，不将域名/CDN 线路自动迁移成直连。

## 身份材料与配置

1. 通过已验证主机密钥的 SSH 管理通道，在服务器专用私密目录生成证书、私钥与高熵口令。TLS 名称固定为 `tunnel.invalid`，仅为内部证书身份，不需要注册或 DNS 解析。不要将其他网站域名当成自己的证书。
2. 用已安装、来源可信的 OpenSSL 生成 P-256 自签名证书；例如在**新建的私密目录**运行下列命令。预先确认同名文件不存在；`openssl req` 本身会覆盖文件。`umask 077` 是 Linux shell 设置。有效期示例365天，登记到期日及轮换计划。

```sh
umask 077
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 365 -subj /CN=tunnel.invalid -addext subjectAltName=DNS:tunnel.invalid -keyout server.key -out server.crt
```

3. 以**完整证书 DER**的 SHA-256 为 `TLS_CERT_SHA256`，格式为64位十六进制（去掉 OpenSSL 输出的冒号）。从上述受信任管理通道获取，不从未认证网络连接自动学习证书。指纹不是公钥指纹，也不是 `client-fingerprint: chrome`。
4. 私密参数对象包含 `SERVER_HOST`、整数 `HY2_UDP_PORT`、`HY2_PASSWORD`、`TLS_CERT_SHA256`、服务器绝对路径 `TLS_CERT_PATH` 与 `TLS_KEY_PATH`。不需要 `TLS_SERVER_NAME` 或 `domain`；空白自有域名不阻塞此路线。
5. 使用现有服务器模板及新增客户端模板：

```text
python scripts/render.py examples/server-hysteria2.template.json --values PRIVATE_VALUES_FILE --output NEW_PRIVATE_SERVER_JSON
python scripts/render.py examples/client-hy2-pinned.template.json --values PRIVATE_VALUES_FILE --output PRIVATE_DIRECTORY/tunnel-client.yaml
```

大写路径由 Agent 替换成实际私密路径。按 [部署说明](deployment.md)核查二进制来源、账号、权限、端口和服务，再应用获授权的变更。服务器证书文件应只有服务所需的读取权限；私钥留在服务器，客户端只需口令与指纹。

Mihomo 的 `fingerprint` 固定校验服务器证书；配置保持 `skip-cert-verify: false`。叶子证书指纹校验替代公共 CA 信任链检查，不另检查名称和期限，故维护者仍须记录证书期限。`sniGuard: strict` 在服务器侧检查 `tunnel.invalid`。错指纹必须失败，缺失/格式错误指纹在渲染时拒绝。禁止为排错删除指纹或开启跳过验证。

## 验收、轮换与恢复

- 先原生解析，再通过隔离显式代理验证真实请求、出口及应用；TUN/系统代理按用户选择另行启用。正确指纹成功、错误指纹失败；测试不应切断已有连接。
- 证书轮换会改变完整证书指纹。先备份旧证书与私密配置，生成新证书及新 YAML；在维护窗口同步服务器和客户端，验证后交付。更新失败恢复旧证书和旧 YAML。不要只换证书却继续分发旧指纹。
- 默认交付本地 YAML。可选域名直连继续使用旧 `client-hy2.template.json` 和公共 CA 证书；可选 CDN 路线见 [cdn-warp.md](cdn-warp.md)。私密 HTTPS 订阅及入口更新目前属于 CDN 路线，不能靠跳过证书验证套用在 IP 订阅上。

依据：[Mihomo TLS 证书指纹](https://wiki.metacubex.one/config/proxies/tls/#fingerprint)、[Hysteria2 客户端字段](https://wiki.metacubex.one/config/proxies/hysteria2/)。固定版本的真实握手检查见 `tests/integration_hy2.py`；它使用临时自签名证书、回环监听和虚构认证，不访问生产节点。
