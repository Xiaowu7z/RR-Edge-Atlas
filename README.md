# RR Edge Atlas

> 📢 **[进入 RR-vps 官方交流频道](https://t.me/GMgP4NG7lncwZGE1)**

[中文](README.md) · [English](README_EN.md)

**中文名：RR 多端域名优选**

RR Edge Atlas 是一个在用户本机运行的多端域名质量评估工具，提供电脑端与 Android 端。它通过固定候选 IP、保持 SNI 与证书校验、分阶段传输测试和最差地址优先排序，帮助用户在当前设备、当前网络下筛选表现更稳定的域名入口。

> 测试结果只代表当前设备、当前网络出口与本轮状态。更换运营商、Wi-Fi、VPN、代理或网络出口后应重新测试。

## 正式版本

| 平台 | 版本 | 说明 | 下载 |
| --- | --- | --- | --- |
| Windows / macOS / Linux | **1.1** | 自定义域名、文件/订阅导入、Cloudflare CNAME | [Release v1.1](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/tag/v1.1) |
| Android | **2.8.0** | 原生 Kotlin，同步自定义域名与 Cloudflare CNAME | [直接下载 APK](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/download/v1.1/CF-Optimizer-2.8.0.apk) |

Android 版适合中国移动、中国电信、中国联通三网优选。电脑端沿用 Android 2.8.0 的固定 IP、分层筛选与地址底线排序原理，方便没有 Android 环境的用户。

电脑端 1.1 与 Android 2.8.0 均支持：单个/批量自定义域名、TXT/CSV/TSV/JSON/Base64 内容识别、HTTP/HTTPS 域名订阅，以及把手选或测速结果安全新增/更新到用户自己的 Cloudflare CNAME。

> Android 2.8.0 启用新的正式签名。已安装 2.7.1 的设备需要先卸载旧版再安装；从 2.8.0 开始，后续正式版可以直接覆盖升级。卸载会清除应用本地历史记录。

## 电脑端快速开始

电脑端要求 Python 3.11 或更高版本，不需要安装第三方 Python 库。

Windows：

1. 从 [Release v1.1](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/tag/v1.1) 下载 `RR-Edge-Atlas-Desktop-1.1.zip`。
2. 解压后双击 `start-windows.bat`。
3. 保持命令窗口运行，在自动打开的本地页面开始测试。

电脑端压缩包 SHA-256：

```text
c8fb4ecfc30fc30f330f9d73c11129659cf042e957b73cc83eaaf4f7793bdfec
```

macOS / Linux：

```bash
chmod +x start-unix.sh
./start-unix.sh
```

也可以直接运行：

```bash
python rr_optimizer.py
```

界面只监听 `127.0.0.1`，测试记录不会上传。

## Android 快速开始

下载并安装 [CF-Optimizer-2.8.0.apk](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/download/v1.1/CF-Optimizer-2.8.0.apk)。APK SHA-256：

```text
3758d8938ba573221caa83a2bd6f148eb43e88ca7f28cd8e74525242172764e7
```

完整说明见 [android/README.md](android/README.md)。

Android 可在首页切换到自定义域名，使用系统文件选择器或订阅导入；测速结果卡片可直接预填 Cloudflare CNAME 目标。系统文件选择器不需要存储权限，Cloudflare Token 不会写入文件、偏好设置、历史或日志。

## 核心方法

- 对域名池建立一次 DNS 快照，固定候选地址并去重。
- 固定候选 IP，同时保持测试端点的 SNI、Host 与证书校验。
- 依次执行 Pre、Micro、Full 分层测试，减少无效流量。
- Full 失败按 `0 Mbps` 进入统计，优先比较最差地址底线。
- 综合成功率、最低速度、平均速度、波动和 TTFB 排序。
- 提供 IPv4、IPv6、双栈、均衡模式和亚洲入口狩猎。
- 自定义域名模式只测试用户本次载入的域名，不混入内置池或参考域名。
- Cloudflare CNAME 写入使用本机后端和最小权限 API Token，不在浏览器中持久化凭据。

## 仓库结构

```text
desktop/   电脑端 1.1 源码、网页界面、启动脚本与测试
android/   Android 2.8.0 完整工程源码、测试与构建文件
```

电脑端压缩包与 Android APK 作为 `v1.1` Release 正式资产发布；RR-vps 原仓库中的旧下载路径继续保留归档。

## 使用边界

本项目仅用于个人在自有或获授权网络中的网络质量评估与域名选择，不提供端口扫描、漏洞探测、压力测试或绕过访问控制能力。测试对象仅为公开可访问的域名和公开测试端点。请遵守所在地法律、网络提供商政策和相关服务条款。

Cloudflare、Android 等名称与商标归各自权利人所有。本项目是非官方独立工具，与相关服务商不存在隶属、合作、赞助或背书关系。详见 [NOTICE.md](NOTICE.md)。

## 致谢与关联项目

- [RR-vps](https://github.com/Xiaowu7z/RR-vps)：VPS 管理脚本与 RR Nexus 面板。
- RR Nexus 浏览器优选只负责候选初筛；原生电脑端与 Android 端适合最终测试。
