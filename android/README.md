# CF 域名优选（Android）

Cloudflare IP / 域名入口优选 Android 工具。原生 Kotlin，仅申请联网与网络状态权限，无广告。

## 当前版本

**2.8.0**（[下载 `CF-Optimizer-2.8.0.apk`](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/download/v1.1/CF-Optimizer-2.8.0.apk)，SHA-256：`3758d8938ba573221caa83a2bd6f148eb43e88ca7f28cd8e74525242172764e7`）

> 2.8.0 启用新的正式签名。已安装 2.7.1 的设备需要先卸载旧版再安装；卸载会清除应用本地历史记录。从 2.8.0 开始的后续正式版可以直接覆盖升级。证书指纹见 [RELEASE_SIGNING.md](RELEASE_SIGNING.md)。

- 包名：`com.cfoptimizer`，versionCode 22，minSdk 29，targetSdk 34
- IPv4 / IPv6 / 双栈独立测速
- 均衡模式 + **亚洲入口狩猎**模式
- 亚洲入口优先级：HKG > NRT > SIN > ICN > TPE；Full 阶段再次 trace 检查 POP 漂移
- 1000 个候选域名种子，DNS 去重 Cloudflare IP，按 IP / POP / Prefix 发现入口
- 可输入单个/多个自定义域名，或导入 TXT、CSV、TSV、JSON、Base64 文件和 HTTP/HTTPS 订阅
- 自定义模式只建立用户列表的 DNS 快照，不混入内置池或 Nexus Mods 基准
- 测速结果可一键预填为 Cloudflare CNAME 目标，也可在首页手动填写目标
- Nexus Mods 固定基准、Final Address Floor、失败计 0、成功率/波动/TTFB/最佳与最差 IP
- 50 条历史记录；保留 2.7.1 的主页滚动与历史入口修复

历史 APK 继续保留在 [RR-vps 原仓库归档](https://github.com/Xiaowu7z/RR-vps/tree/main/assets/cf-optimizer)。

## 自定义域名

在首页把“候选域名来源”切到“自定义域名”后，可以：

- 输入单个域名，或用换行、空格、逗号、分号分隔多个域名。
- 通过 Android 系统文件选择器导入文件，不申请存储权限。
- 填写域名订阅链接并下载本次列表。

文件格式按**内容**识别，不依赖扩展名。域名会统一转小写、去尾点、将国际化域名转为 Punycode，并按原顺序去重；IP、通配符与无效字段会被忽略。单次最多 5000 个域名，源内容最多 1 MiB，支持 UTF-8 和 GB18030。

订阅仅允许 HTTP/HTTPS、公网目标和 80/443 端口；每次跳转都会重新检查地址，并将连接固定到本次校验过的公网 IP。HTTP 内容可能被链路篡改，优先使用 HTTPS。

## Cloudflare CNAME

可从首页手动打开 Cloudflare 表单，或在任意测速结果点击“将此优选域名设为 CNAME 目标”。填写区域域名或 Zone ID、自己的记录名、目标域名和 API Token 后：

1. 精确查询同名 DNS 记录。
2. 不存在时创建 CNAME；已有一个 CNAME 时更新；内容与代理状态相同则不写入。
3. 同名 A、AAAA 或其他记录存在、或出现多个同名 CNAME 时立即停止，不覆盖也不删除。

默认使用 `DNS only` 和自动 TTL。Token 建议只授权目标区域的 `Zone / DNS / Edit`；按区域域名查询 Zone 时再授予 `Zone / Zone / Read`。Token 不写入文件、偏好设置、历史或日志，并在请求发起前从输入框清除。

开启橙云会改变实际路由；目标位于另一 Cloudflare 账号时还可能触发 `1014 CNAME Cross-User Banned`。

## 目录

- `app/` — Android 工程源码
- `test/` — 测试源码
- `test.sh` — 域名源与 Cloudflare CNAME 纯 JVM 回归测试
- `domains.txt` — 1000 域名候选池
- `build.gradle.kts` / `settings.gradle.kts` — Gradle 构建入口
- `build.sh` — CLI 构建脚本

## 构建

标准 Gradle 环境可使用 JDK 17 + Android SDK 34 + Gradle 8.10.2 构建。

CLI 工具链准备完成后可执行测试并构建本地 debug 包：

```bash
./test.sh
./build.sh
```

正式签名必须从仓库外注入，参数与证书核验方式见 [RELEASE_SIGNING.md](RELEASE_SIGNING.md)。

应用仅申请联网与网络状态权限。文件导入使用系统文档选择器，不申请读取全部存储空间的权限。
