# Android 正式签名

从 Android `2.8.0` 起，RR Edge Atlas 使用新的专用正式签名。私钥与密码不会保存到 Git 仓库、APK 或公开 Release。

## 正式证书

- 证书主体：`CN=RR Edge Atlas Android Release, O=RR Edge Atlas, C=CN`
- SHA-256：`E7:EF:2F:60:DC:8C:0E:74:44:80:2E:BA:A8:53:5C:0C:49:61:F3:6C:8B:A6:51:C0:96:4F:43:D3:62:A4:A4:08`
- 首个版本：Android `2.8.0` / Release `v1.1`

旧版 `2.7.1` 的签名证书 SHA-256 为 `55:9B:45:AF:09:30:84:AB:B7:85:07:03:BA:C7:F8:51:BB:8C:20:AB:95:CC:9F:F4:10:10:FD:7E:A1:0B:5F:07`。两把签名不同，因此已安装 `2.7.1` 的设备必须先卸载旧版，再安装 `2.8.0`。从 `2.8.0` 开始的后续正式版可以直接覆盖升级。

## 正式构建

`build.sh` 默认生成本地 debug 包。正式构建必须从仓库外注入签名材料：

```bash
SIGNING_KEYSTORE=/private/path/RR-Edge-Atlas-Android-release.p12 \
SIGNING_KEY_ALIAS=rr-edge-atlas \
SIGNING_STORE_PASSWORD_FILE=/private/path/password.txt \
./build.sh
```

如私钥密码与仓库密码不同，可另外设置 `SIGNING_KEY_PASSWORD_FILE`。正式发布前必须执行 `apksigner verify --verbose --print-certs`，并核对上面的 SHA-256 指纹。
