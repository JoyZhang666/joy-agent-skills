# 开发测试与证据范围

Python 3.10+ 标准库。完整回归命令：`python -B -m unittest discover -s tests -v`。
使用临时虚构数据与服务回调，不连接生产服务器、不实际调用 systemctl。Windows 明确跳过6项仅适用于 Linux 的服务指针事务测试和3项 flock 测试，Linux CI 必须运行全部47项；Windows 保留配置、计划、订阅发布和巡检等38项回归。命令本身不是沙箱，只在已审阅代码的开发环境或一次性 CI runner 运行。

## 真实证书握手

Linux amd64 需要 OpenSSL、iproute2 与 util-linux。下载命令明确联网，从固定官方发行包取得测试核心并校验 `tests/native-assets.json` 中 SHA-256，不安装到系统。输出目录必须不存在。

```sh
python3 -B tests/fetch_native.py --output /tmp/crossborder-test-cores
sudo unshare --net --fork bash -c 'ip link set lo up; exec python3 -B tests/integration_hy2.py --artifacts /tmp/crossborder-test-cores'
```

在一次性 Linux CI runner 执行；网络命名空间只有回环接口。临时 Hysteria2、Mihomo与HTTP目标都只监听回环，使用临时自签名证书和虚构认证，TUN/控制器关闭。进程有超时并在退出时回收，不读取实际客户端配置。

检查生成YAML原生解析、正确指纹成功、错误指纹拒绝、移除指纹后不受信证书拒绝、证书替换后旧指纹拒绝、同步新指纹后恢复。负向项检查证书拒绝日志，不能只把超时算安全验证。测试强制将回环HTTP目标送入隧道，避免DIRECT规则假通过。

仓库CI只对Skill及对应工作流路径生效：Windows/Linux × Python3.10/3.12回归，加Linux真实握手。权限contents:read、checkout不保留凭据、Actions固定提交，没有生产密钥或自动部署。

## 实际使用验收

2026-11-07用户确认参考CDN部署正常，Windows/Android、YouTube和订阅导入/更新通过。工程验证包含CDN正反向请求、服务事务、WARP失败关闭、订阅原子发布/恢复、DNS-01续期演练与真实调度触发；版本和历史层级见 [versions.json](versions.json)。

这些证据不等于每个网络、客户端或整机路由都通过。系统DNS/IPv6、计时播放和客户端自动刷新周期等未独立实测的项目继续注明，不阻塞已确认的日常应用验收，也不编造测量。
