# 私密订阅与接入端入口维护

适用于已实际跑通的域名/CDN线路。订阅包含节点认证信息，随机URL与SSH发布密钥分别管理；不输出到日志、命令行或公开包。

## 数据流与安装契约

接入端 `edge_monitor.py --settings <私密JSON>` → 受限SSH命令 `subscription.py` → 原子替换订阅文件 → 客户端HTTPS更新。
完整链路检测由接入端固定物理接口的隔离Mihomo完成；境外源站自测不能代替接入端可达性。

- `cdn.py` 可选 `subscription_path` 必须为 `/s/<64位随机十六进制>/client.yaml`。新路由只允许GET/HEAD，固定重写为 `/var/lib/crossborder-subscription/current.yaml`，禁止目录浏览，返回no-store和6小时更新提示。实际客户端更新周期仍需配置。
- `subscription.py` 从 `/etc/crossborder-subscription/policy.json` 读安装者拥有的 `values`（固定认证/SNI/WS参数）和 `allowed_addresses`。接收标准输入JSON，限制8192字节：`status` 或带 `expected_sha256`、两个地址的 `publish`。不接受新UUID、路径、任意配置内容或调用者提供的文件路径。
- 用独立无sudo发布账号，SSH `restrict,command="/usr/bin/timeout 60 /usr/bin/python3 -B /opt/crossborder/subscription/subscription.py"`；authorized_keys及其父目录由root拥有。发布账号仅能写订阅数据目录。Caddy通过独立补充组只读访问，不让发布账号加入持有源站证书的服务组。
- 每次发布先核对旧SHA；v0.4.0监测端还发送 `expected_new_sha256`，服务端在写入前比较新配置是否与已探测内容完全一致，避免两端参数漂移时发布另一份配置。通过后保留previous.yaml并原子替换current.yaml；不重启服务。订阅HTTP没有写接口。首次添加路由走管理器原生校验、受控重启和回退。
- 订阅URL持有者能够获得完整节点凭据；不承诺对CDN提供商隐藏URL。日志不得启用含该路径的访问记录；链接泄露时轮换路径，节点凭据泄露时另行轮换UUID。

## 监测参数

安装者先完成以下准备，脚本不会自动创建这些资源：

1. 将 `subscription.py`、同版本 `cdn.py`、`render.py` 放入root管理、发布账号不可写的 `/opt/crossborder/subscription/`。策略 `/etc/crossborder-subscription/policy.json` 使用root拥有、发布账号只读的权限；对象含 `values`（与已部署节点匹配的私密CDN参数对象）及 `allowed_addresses`（已实测CDN候选IPv4数组）。
2. 建立独立无sudo发布账号与Caddy只读组。数据目录 `/var/lib/crossborder-subscription` 由发布账号拥有、只读组可遍历读取，建议目录2750、文件0640；Caddy加入只读组，发布账号不能写脚本、策略或authorized_keys。不要将Caddy证书组授予发布账号。
3. 在私密环境通过发布器标准输入发送 `{"op":"status"}`。初始化时用返回的空内容SHA、两个已验收地址及新YAML的SHA发送publish请求，创建 `current.yaml`；不能让监测端在空订阅上开始选址。请求结构为 `op`、`expected_sha256`、`expected_new_sha256`、`addresses`，内容通过标准输入传递，不放命令行。
4. 添加64位随机十六进制订阅路径并走管理器apply，完成有效链接、错误token、POST拒绝、HTTPS正文哈希与客户端导入测试。URL私密交付，两端各执行一次更新。
5. 接入端保存下面的私密settings，配置固定SSH别名和可信known_hosts；先手动验收，再创建48小时计划任务，并核对真实调度触发。监测端需同版本 `edge_monitor.py`、`subscription.py`、`cdn.py`、`probe.py`、`render.py`，不是只复制一个脚本。

```json
{
  "values_file": "{{PRIVATE_CDN_VALUES_FILE}}",
  "mihomo": "{{VERIFIED_MIHOMO_PATH}}",
  "mihomo_sha256": "{{MIHOMO_BINARY_SHA256}}",
  "curl": "{{CURL_PATH}}",
  "interface": "{{PHYSICAL_INTERFACE}}",
  "ssh": "{{SSH_PATH}}",
  "ssh_config": "{{PRIVATE_SSH_CONFIG}}",
  "candidates": ["{{REVIEWED_CDN_IPV4_A}}", "{{REVIEWED_CDN_IPV4_B}}"],
  "reviewed_cdn_networks": ["{{CURRENT_OFFICIAL_CDN_CIDR}}"]
}
```

以上为字段说明，不能照抄占位符运行；候选地址不是源站IP。运行 `python -B scripts/edge_monitor.py --settings PRIVATE_SETTINGS_FILE`，Windows定时任务用已验证的pythonw路径。调度器账号必须能访问该私密目录、固定网络接口及SSH密钥。

从候选版本升级时，先更新服务端发布器，再更新监测端；新发布器兼容不带新哈希的旧人工发布请求，自动监测始终带新哈希。旧服务端收到新字段会拒绝，保留当前订阅；不要仅升级一端后宣称自动维护已可用。两端 `cdn.py`、`render.py` 及固定身份/引导DNS等参数必须一致。公开包更新不自动升级已有生产安装。

私密settings含：`values_file`、`mihomo`、`mihomo_sha256`、`curl`、`interface`、`ssh`、`ssh_config`、`candidates`、`reviewed_cdn_networks`。
`ssh_config` 的固定Host别名为 `crossborder-subscription`，必须启用StrictHostKeyChecking、BatchMode与独立IdentityFile。

候选限定2–8个人工审核的提供商IPv4地址；同时配置当前官方地址段，地址段校验不代表端点一定承载该域名。程序不扫描公网、不下载第三方优选IP名单。需补充候选时同步服务端白名单和接入端设置，并实测TLS和完整隧道。

每轮对每个地址做真实TLS/WS/认证/WARP出口检查。当前入口连续两轮失败、替代入口连续两轮成功且至少两个合格地址时，复测新组合后才发布；保留当前正常入口和顺序，不根据单次速度抖动。采样至少间隔5分钟，超过2小时的连续计数清零。无替代入口、核心哈希改变、接口不可用或SSH失败时，不发布未经验证的组合。

状态和last-result保存在settings同目录；使用OS文件锁避免重叠。常规每48小时检查一次：若现用入口异常且尚未发布，则在同一进程内等待5分钟复核一次，之后结束，不无限重试；只有未使用的候选失败时不复核。等待期间last-result记录待复核及预计时间。保留两小时证据有效期，不用两天前的检测凑连续次数。

Windows计划任务调用pythonw避免弹窗，设置48小时重复、错过后补跑、禁止重叠，取消额外登录触发；当前四候选配置任务时限20分钟。交互式账号需要用户已登录，关机/注销会停止检测或复核；恢复后依调度器补跑，不承诺关机期间准时运行。服务器旧订阅继续可用。必须核对一次真实计划触发，不用手动运行冒充。客户端订阅周期仍建议6小时，与入口巡检周期独立。

## 验收与恢复

核对有效URL200、SHA及原生解析，错误token/目录/POST拒绝、no-store、SSH shell和白名单外地址拒绝。真实发布已知可用的重排组合，HTTPS读回，再用最新SHA恢复原组合。全坏时保留上一版；客户端下载失败时保留本地旧配置，需在目标客户端确认。

定时监测成功不等于手机、其他运营商或境外网络通过。订阅下载与隧道共用CDN/源站，属于共同故障点；全部失效时可能无法自动取回更新，保留本地工作配置并按另行批准的独立备线恢复。完整订阅更新也可能让客户端重载现有连接，不承诺无缝视频切换。

源码测试：`python -B -m unittest discover -s tests -v`。公开示例仅用虚构身份；安装路径、实际URL、密钥、状态及部署脚本留在私有运维层，不能打入Skill包。
