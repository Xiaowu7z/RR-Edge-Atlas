# RR Edge Atlas

> 📢 **[Join the official RR-vps community channel](https://t.me/GMgP4NG7lncwZGE1)**

[中文](README.md) · [English](README_EN.md)

**Chinese name: RR 多端域名优选**

RR Edge Atlas is a local multi-platform domain-quality evaluation tool for desktop and Android. It pins candidate IPs, preserves SNI and certificate validation, runs staged transfer tests, and ranks the worst-address floor first to identify stable domain entries for the current device and network.

> Results represent only the current device, egress, network, and test run. Test again after changing the carrier, Wi-Fi, VPN, proxy, or egress.

## Releases

| Platform | Version | Notes | Download |
| --- | --- | --- | --- |
| Windows / macOS / Linux | **1.0** | Native Python probing, local purple UI, Chinese/English switch | [Release v1.0](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/tag/v1.0) |
| Android | **2.7.1** | Native Kotlin; field-tested across three Chinese carriers | [Download APK](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/download/v1.0/CF-Optimizer-2.7.1.apk) |

> The desktop source on `main` is now **1.1**. It accepts one or many custom domains, detects TXT/CSV/TSV/JSON/Base64 domain sources, loads HTTP/HTTPS subscriptions, and can safely create or update a Cloudflare CNAME from a manual target or benchmark result. The latest packaged download remains v1.0 as listed above.

The desktop edition requires Python 3.11 or newer and has no third-party Python dependencies. On Windows, extract the release and double-click `start-windows.bat`. On macOS or Linux, run:

```bash
chmod +x start-unix.sh
./start-unix.sh
```

The interface listens on `127.0.0.1` only and does not upload benchmark records.

Custom mode benchmarks only the domains supplied for that run; it does not inject the built-in pool or reference hostname. Imported content is normalized, deduplicated in order, and capped at 5,000 domains / 1 MiB. Subscription URLs are limited to public HTTP/HTTPS destinations on ports 80 and 443.

The Cloudflare helper performs an upsert: it creates a missing CNAME, patches an existing CNAME, and stops on conflicting record types. Use a zone-scoped `DNS Edit` API Token; add `Zone Read` only when looking up the zone by name instead of supplying a Zone ID. The token is used by the local Python service for the current request and is not persisted in browser storage, history, or logs.

Desktop package SHA-256:

```text
569610261db2c4b3ad17a5d4ea8d4bcb597497d1bf889ace4980cbe4e6518bf3
```

The Android APK SHA-256 is:

```text
d2e26ab5a56e0888ad21c6ae2e900a7446f7e7e548c2084a52babcb772409937
```

## Repository layout

```text
desktop/   Desktop 1.1 source, local UI, launchers, and tests
android/   Android 2.7.1 project source, tests, and build files
```

The Android APK is published as an official `v1.0` Release asset. The legacy RR-vps download path remains available for compatibility.

## Usage boundary

This project is only for personal network-quality evaluation and domain selection on networks you own or are authorized to test. It does not provide port scanning, vulnerability testing, stress testing, or access-control bypass features. Test targets are publicly reachable domains and public test endpoints. Follow applicable laws, network-provider policies, and service terms.

Cloudflare, Android, and other names and marks belong to their respective owners. This is an independent, unofficial project and is not affiliated with, partnered with, sponsored by, or endorsed by those providers. See [NOTICE.md](NOTICE.md).

Related project: [RR-vps](https://github.com/Xiaowu7z/RR-vps).
