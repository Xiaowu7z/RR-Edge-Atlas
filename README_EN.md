# RR Edge Atlas

> 📱 **[Android update repository / Obtainium](https://github.com/Xiaowu7z/RR-Edge-Atlas-Android)** · 📢 **[RR-vps community](https://t.me/GMgP4NG7lncwZGE1)**

[中文](README.md) · [English](README_EN.md)

**Chinese name: RR 多端域名优选**

RR Edge Atlas is a local multi-platform domain-quality evaluation tool for desktop and Android. It pins candidate IPs, preserves SNI and certificate validation, runs staged transfer tests, and ranks the worst-address floor first to identify stable domain entries for the current device and network.

> Results represent only the current device, egress, network, and test run. Test again after changing the carrier, Wi-Fi, VPN, proxy, or egress.

## Releases

| Platform | Version | Notes | Download |
| --- | --- | --- | --- |
| Windows / macOS / Linux | **1.1** | Custom domains, file/subscription import, Cloudflare CNAME | [Release v1.1](https://github.com/Xiaowu7z/RR-Edge-Atlas/releases/tag/v1.1) |
| Android | **2.8.0** | Native Kotlin with the same custom-domain and CNAME features | [Dedicated downloads and updates](https://github.com/Xiaowu7z/RR-Edge-Atlas-Android) |

Desktop 1.1 and Android 2.8.0 support one or many custom domains, TXT/CSV/TSV/JSON/Base64 content detection, HTTP/HTTPS subscriptions, and safe Cloudflare CNAME create/update from a manual target or benchmark result.

> Android 2.8.0 starts using a new release signing certificate. Devices with 2.7.1 installed must uninstall it first; later official releases can upgrade directly from 2.8.0. Uninstalling clears local app history.

The desktop edition requires Python 3.11 or newer and has no third-party Python dependencies. On Windows, extract the release and double-click `start-windows.bat`. On macOS or Linux, run:

```bash
chmod +x start-unix.sh
./start-unix.sh
```

The interface listens on `127.0.0.1` only and does not upload benchmark records.

Custom mode on both platforms benchmarks only the domains supplied for that run; it does not inject the built-in pool or reference hostname. Imported content is normalized, deduplicated in order, and capped at 5,000 domains / 1 MiB. Subscription URLs are limited to public HTTP/HTTPS destinations on ports 80 and 443. Android file import uses the system document picker and requires no broad storage permission.

The Cloudflare helper performs an upsert: it creates a missing CNAME, patches an existing CNAME, and stops on conflicting record types. Use a zone-scoped `DNS Edit` API Token; add `Zone Read` only when looking up the zone by name instead of supplying a Zone ID. On Android the token is cleared from the input before the request and is never written to files, preferences, history, or logs.

Desktop package SHA-256:

```text
c8fb4ecfc30fc30f330f9d73c11129659cf042e957b73cc83eaaf4f7793bdfec
```

The Android APK SHA-256 is:

```text
3758d8938ba573221caa83a2bd6f148eb43e88ca7f28cd8e74525242172764e7
```

## Android updates with Obtainium

1. Install Obtainium from its [official latest GitHub release](https://github.com/ImranR98/Obtainium/releases/latest). Most modern phones use `app-arm64-v8a-release.apk`; choose the universal `app-release.apk` if unsure. [F-Droid](https://f-droid.org/packages/dev.imranr.obtainium.fdroid/) is also supported.
2. Tap [Add RR Edge Atlas Android to Obtainium](https://apps.obtainium.imranr.dev/redirect?r=obtainium://app/%7B%22id%22%3A%22com.cfoptimizer%22%2C%22url%22%3A%22https%3A%2F%2Fgithub.com%2FXiaowu7z%2FRR-Edge-Atlas-Android%22%2C%22author%22%3A%22Xiaowu7z%22%2C%22name%22%3A%22RR%20Edge%20Atlas%20Android%22%7D) and confirm the app in Obtainium.
3. Android may ask you to allow Obtainium to install unknown apps on the first install or update. Grant the permission, return to Obtainium, and tap Install or Update.
4. Later, refresh Obtainium or run an update check to download and install new Android releases.

If the one-tap link does not open, use Add App in Obtainium and paste `https://github.com/Xiaowu7z/RR-Edge-Atlas-Android`. Existing Obtainium entries that track this mixed repository must be removed or edited; they do not migrate automatically.

## Repository layout

```text
desktop/   Desktop 1.1 source, local UI, launchers, and tests
android/   Android 2.8.0 project source, tests, and build files
```

The desktop archive remains available from this repository's `v1.1` Release. Its Android APK is retained only as a historical archive; use [RR-Edge-Atlas-Android](https://github.com/Xiaowu7z/RR-Edge-Atlas-Android) for current Android downloads and automatic updates.

## Usage boundary

This project is only for personal network-quality evaluation and domain selection on networks you own or are authorized to test. It does not provide port scanning, vulnerability testing, stress testing, or access-control bypass features. Test targets are publicly reachable domains and public test endpoints. Follow applicable laws, network-provider policies, and service terms.

Cloudflare, Android, and other names and marks belong to their respective owners. This is an independent, unofficial project and is not affiliated with, partnered with, sponsored by, or endorsed by those providers. See [NOTICE.md](NOTICE.md).

Related projects: [RR Edge Atlas Android](https://github.com/Xiaowu7z/RR-Edge-Atlas-Android) and [RR-vps](https://github.com/Xiaowu7z/RR-vps).
