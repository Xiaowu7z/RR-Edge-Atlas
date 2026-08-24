# RR Edge Atlas 电脑端域名优选

电脑端正式版 `1.0`。优选原理与 Android 2.7.1 保持一致。

## 适用平台

- Windows 10 / 11
- macOS
- Linux
- Python 3.11 或更高版本

不需要安装第三方 Python 库。界面只在本机 `127.0.0.1` 启动，测试结果不会上传。

## 最简单的启动方式

Windows 双击：

```text
start-windows.bat
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

程序会自动打开本地网页界面。保持命令窗口运行；关闭命令窗口即退出本地服务。

## 命令行模式

完整双栈均衡优选：

```bash
python rr_optimizer.py run --mode balanced --family dual --operator 中国移动
```

仅 IPv4、前 200 个候选域名快速预览：

```bash
python rr_optimizer.py run --mode balanced --family ipv4 --limit 200 --output result.json --csv result.csv
```

区域优选：

```bash
python rr_optimizer.py run --mode asia --family dual --output asia-result.json
```

参数说明：

- `--mode balanced|asia`：均衡优选或区域优选。
- `--family ipv4|ipv6|dual`：IPv4、IPv6 或双栈。
- `--operator`：本轮运营商标签，只写入结果，不干预排名。
- `--limit N`：只取域名池前 N 个候选；`0` 为完整 1000 域名。
- `--domains FILE`：改用自定义域名池，每行一个域名。
- `--output FILE`：JSON 结果路径。
- `--csv FILE`：同时输出 CSV。

## 核心规则

1. 建立一次 DNS 快照，只保留内置 CDN 候选范围中的 IPv4 / IPv6 地址并去重。
2. 每次比较直接连接指定候选地址，TLS SNI、Host 与证书校验保持为内置公开测试端点。
3. 强制 HTTP/1.1 冷连接，不复用连接，不自动重试。
4. Pre、Micro 对共享 IP 只测试一次；Full 覆盖晋级域名快照中的每个地址。
5. 下载达到目标字节的 80% 才算成功。
6. Full 失败按 `0 Mbps` 进入最低速度、平均速度、波动率和成功率。
7. 最终排名顺序：Final Address Floor → Full 成功率 → 最低完整速度 → 平均完整速度 → 地址成功率 → 波动率 → TTFB。
8. `www.nexusmods.com` 固定进入 Micro / Full，作为稳定参考域名。
9. 区域优选按 `HKG > NRT > SIN > ICN > TPE` 整理优选，并在最终阶段复核区域变化。

## 使用提醒

- 请在最终使用域名的同一台电脑、同一条网络上测试，测试期间不要切换 Wi-Fi、有线网络、VPN 或代理。
- 完整 1000 域名、双栈、区域优选会消耗较多时间和流量。第一次可以用 50 或 200 个候选确认环境正常，再跑完整测试。
- “运营商”选项只方便区分历史记录。Wi-Fi 宽带无法可靠自动识别时，请手动选择移动、电信或联通。
- 结果只代表当前网络出口和本轮状态；更换网络后应重新测试。

## 使用边界

本工具只用于个人网络质量评估和域名选择，不提供端口扫描、漏洞探测、压力测试或绕过访问控制能力。请仅在合法、获授权的网络环境中使用，并遵守所在地法律和相关服务条款。文档中出现的名称与商标归各自权利人所有，本工具并非相关服务商的官方产品，也不代表其认可或背书。

## 开发验证

```bash
python -m unittest discover -s tests -v
```

测试不执行大流量公网任务，使用可控的模拟数据验证排名、失败计 0、全地址覆盖、参考域名强制晋级和区域规则。
