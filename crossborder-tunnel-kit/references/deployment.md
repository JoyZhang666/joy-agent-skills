# 部署准备与最小路径

先确认：VPS 所有权与变更范围、OS/架构、SSH 和云控制台恢复入口、UDP 可达性、客户端类型、是否仅应用代理、域名和有效 TLS 证书。不了解具体平台时，不给出“通用一键安装”承诺。

1. 本地核查材料；`python scripts/baseline.py` 只输出平台、工具存在性、代理环境变量是否配置。服务器路由、监听、现有服务、磁盘和防火墙另行只读检查，在用户授权的服务器上进行。原始输出留在私密证据目录。
2. 明确单一主线：`examples/server-hysteria2.template.json` 配 `examples/client-hy2.template.json`。初版不含远程规则订阅、自动切换、WARP 或 TUN。除回环例外外，送入客户端代理的流量走所选线路；不宣称已实现国内直连。若要求国内直连，另行审阅固定来源/版本/校验值的国内域名与网段规则，先匹配必要内网/管理地址，再国内直连，最后代理，并验证规则命中；不默认拉取第三方订阅。
3. 依据 [inputs.md](inputs.md) 在受保护文件准备参数。使用 `render.py` 输出新文件。统一使用 JSON，端口等完整占位符保留整数类型，字符串由 JSON 序列化转义。Hysteria 官方支持 JSON；JSON 也是 YAML 子集，Mihomo 可读取。不要沿用原 ZIP 的字符串替换和错误 YAML。
4. 锁定 [sources.md](sources.md) 版本与官方发行包。部署的 Linux 包必须另取对应架构 SHA-256；不能用 Windows 解析检查包的哈希。`verify.py FILE --sha256 EXPECTED` 仅比较一份可信预期值，校验值和包同站获取不等于多方认证。禁止 `curl | sh`。
5. 配置原生解析检查，见 [verification.md](verification.md)。服务器端证书链须受客户端信任且 SAN 匹配 TLS_SERVER_NAME；证书、私钥预先放置并制定更新方式。此包不自动申请证书或修改 DNS。自签方案须单独配置受信 CA 或核验客户端支持的固定证书指纹，不直接关闭验证。
6. 真正部署前展示明确变更清单：文件、服务、监听端口、现有防火墙/云安全组规则、恢复方式。已获该范围授权则执行。先留第二条 SSH 会话和可用云控制台，再按 [rollback.md](rollback.md) 为本批改动建立恢复计划。
7. 单端口服务使用 `examples/systemd-units/`。需预先建立专用 `tunnel` 系统用户/组（无登录 shell），由 root 管理程序与 unit；配置目录 root:tunnel 0750，运行配置和证书私钥 root:tunnel 0640，服务只读。这些是部署动作，本次材料打磨不执行。Python 恢复工具及批次目录 root 拥有且组/其他用户不可写。
8. `systemd-analyze verify` 检查 unit；`systemctl daemon-reload` 后启动本批服务，检查进程、监听和最少日志。服务限制能力为低端口绑定，禁止隐式管理 TUN 或系统路由。首次部署完成运行验收后才决定是否开机自启。
9. 客户端默认监听回环地址且禁止 LAN 访问，无控制器 API；在一个明确指定的应用中使用它并验收。移动端的 VPN 权限和 Windows 的系统代理/TUN 模式另行说明影响，不自动切换。

Hysteria 服务必须显式包含 `server` 子命令；本包 unit 使用正确形式。不要把程序启动成功当作跨网可达性证据。
