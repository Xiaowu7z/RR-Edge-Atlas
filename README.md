# RR Edge Atlas

> 📢 **[进入 RR-vps 官方交流频道](https://t.me/GMgP4NG7lncwZGE1)**

[中文](README.md) · [English](README_EN.md)

**中文名：RR 多端域名优选**

RR Edge Atlas 是一个在用户本机运行的多端域名质量评估工具，提供电脑端与 Android 端。它通过固定候选 IP、保持 SNI 与证书校验、分阶段传输测试和最差地址优先排序，帮助用户在当前设备、当前网络下筛选表现更稳定的域名入口。

> 测试结果只代表当前设备、当前网络出口与本轮状态。更换运营商、Wi-Fi、VPN、代理或网络出口后应重新测试。

## 正式版本

| 平台 | 版本 | 说明 | 下载 |
| --- | --- | --- | --- |
| Windows / macOS / Linux | **1.0** | Python 原生探测，本地紫黑 UI，中英文切换 | [Release v1.0](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/tag/v1.0) |
| Android | **2.7.1** | 原生 Kotlin，已完成三网实际测试 | [直接下载 APK](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/download/v1.0/CF-Optimizer-2.7.1.apk) |

Android 版适合中国移动、中国电信、中国联通三网优选，测试结果可直接用于实际配置。电脑端沿用 Android 2.7.1 的固定 IP、分层筛选与地址底线排序原理，方便没有 Android 环境的用户。

## 电脑端快速开始

电脑端要求 Python 3.11 或更高版本，不需要安装第三方 Python 库。

Windows：

1. 从 [Release v1.0](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/tag/v1.0) 下载 `RR-Edge-Atlas-Desktop-1.0.zip`。
2. 解压后双击 `start-windows.bat`。
3. 保持命令窗口运行，在自动打开的本地页面开始测试。

电脑端压缩包 SHA-256：

```text
569610261db2c4b3ad17a5d4ea8d4bcb597497d1bf889ace4980cbe4e6518bf3
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

下载并安装 [CF-Optimizer-2.7.1.apk](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/download/v1.0/CF-Optimizer-2.7.1.apk)。APK SHA-256：

```text
d2e26ab5a56e0888ad21c6ae2e900a7446f7e7e548c2084a52babcb772409937
```

完整说明见 [android/README.md](android/README.md)。

## 核心方法

- 对域名池建立一次 DNS 快照，固定候选地址并去重。
- 固定候选 IP，同时保持测试端点的 SNI、Host 与证书校验。
- 依次执行 Pre、Micro、Full 分层测试，减少无效流量。
- Full 失败按 `0 Mbps` 进入统计，优先比较最差地址底线。
- 综合成功率、最低速度、平均速度、波动和 TTFB 排序。
- 提供 IPv4、IPv6、双栈、均衡模式和亚洲入口狩猎。

## 仓库结构

```text
desktop/   电脑端 1.0 完整源码、网页界面、启动脚本与测试
android/   Android 2.7.1 完整源码、测试、构建文件与 APK
```

## 使用边界

本项目仅用于个人在自有或获授权网络中的网络质量评估与域名选择，不提供端口扫描、漏洞探测、压力测试或绕过访问控制能力。测试对象仅为公开可访问的域名和公开测试端点。请遵守所在地法律、网络提供商政策和相关服务条款。

Cloudflare、Android 等名称与商标归各自权利人所有。本项目是非官方独立工具，与相关服务商不存在隶属、合作、赞助或背书关系。详见 [NOTICE.md](NOTICE.md)。

## 致谢与关联项目

- [RR-vps](https://github.com/Xiaowu7z/RR-vps)：VPS 管理脚本与 RR Nexus 面板。
- RR Nexus 浏览器优选只负责候选初筛；原生电脑端与 Android 端适合最终测试。

