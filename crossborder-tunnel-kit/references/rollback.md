# 按批次恢复

工具只恢复本包的三个配置并停止明确标记为本批新增的服务；不处理系统路由、防火墙、DNS 配置或其他软件。若计划含这些变更，先另行制定并验证对应恢复方案，不能把这个 timer 当完整保命手段。

在获授权的 Linux 主机建立 `/var/lib/crossborder-tunnel-kit/batches/BATCH/`（root 0700），保留原配置字节和哈希。恢复工具固定目标在 `/etc/crossborder-tunnel-kit/`，备份与 manifest 同目录。工具文件、manifest 和所有上级目录 root 拥有且组/其他用户不可写。将工具放受保护的稳定路径，不从临时可写目录或服务用户目录调用。备份文件 root 0600；恢复后配置变为 root:tunnel 0640。

manifest 结构示例（摘要必须换为本批真实备份 SHA-256）：

```json
{
  "batch": "change-001",
  "restore": {"hysteria.json": "{{BACKUP_SHA256}}"},
  "stop_new_services": ["sing-box-warp.service"],
  "dns_name": "example.com",
  "dns_expected_ipv4": ["{{BASELINE_DNS_A}}"]
}
```

`restore` 只接受 hysteria.json / xray.json / sing-box.json。`stop_new_services` 只列**变更前不存在且由本批创建**的服务；已有服务不能放进去，否则会被 disable。首次部署可用空 restore 和新服务列表；配置文件保留为私密残留，由人工核对后清理。工具不删除证书、备份或二进制。

DNS 名称选用户允许访问、具有稳定已知 A 记录的测试域名，在变更前使用本机解析器测得 expected 列表。示例域名不保证其地址长期稳定；多地址只要求至少一个匹配预期。`dig` 非零、NXDOMAIN、没有 A 记录或无预期交集都失败。IPv6 和实际业务健康另行验收。

```text
python3 safety.py rollback --manifest ABSOLUTE_MANIFEST
python3 safety.py arm --manifest ABSOLUTE_MANIFEST --unit tunnel-rollback-change-001 --minutes 15 --apply
python3 safety.py disarm --unit tunnel-rollback-change-001 --apply
```

首条默认 review，只核查计划和所有备份哈希，不修改任何状态。arm/disarm 也仅加 `--apply` 才执行，且限定 Linux root。unit 名与 manifest 路径为独立参数；每批使用新名字，冲突不覆盖。

实际修改前先 arm 并回读 timer active。变更完成且所有验收通过后才 disarm。它明确停止 `.timer`，读取 `.service` 状态、执行时间戳与排队 Job；若恢复已排队或开始，拒绝宣称取消成功，也不会中断恢复。目标 systemd 的 Job 输出必须在演练中确认为 0 表示无任务，不识别的输出按失败处理。失败日志脱敏且返回非零，去受保护本地状态检查原因。

回滚开始前验证全部备份，逐项原子恢复并读回哈希、重启服务、确认 active，最后核验真实 DNS 答案。失败可能留下部分已恢复状态，不宣称事务原子性；按本批 manifest 人工继续。必须先在可丢弃 Linux 测试机演练 timer 触发和失败路径，之后才能把它作为生产恢复辅助。
