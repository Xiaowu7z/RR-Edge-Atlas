#!/usr/bin/env bash
# RR优选 Android 2.8.0 — CLI 构建（无 Android Studio）
# 工具链：RRAV JDK17 + build-tools r34 + kotlinc 1.9.25 + OkHttp jars
set -euo pipefail

PROJ="$(cd "$(dirname "$0")" && pwd)"
APP="$PROJ/app"
TOOL="$PROJ/toolchain"
RRAV_TOOL="${RRAV_TOOL:-/srv/hermes-agent/projects/RRAV/toolchain}"
JAVA_HOME="${JAVA_HOME:-$RRAV_TOOL/jdk-17.0.20+8}"
JAVA_BIN="${JAVA_BIN:-$JAVA_HOME/bin/java}"
BT="${ANDROID_BUILD_TOOLS_DIR:-$RRAV_TOOL/build-tools/android-14}"
ANDROID_JAR="${ANDROID_PLATFORM_JAR:-$RRAV_TOOL/platform/android-34/android.jar}"
KOTLINC="${KOTLINC_BIN:-$TOOL/kotlinc/bin/kotlinc}"
OKHTTP_JAR="${OKHTTP_JAR:-$TOOL/lib/okhttp.jar}"
OKIO_JAR="${OKIO_JAR:-$TOOL/lib/okio.jar}"
KOTLIN_STDLIB_JAR="${KOTLIN_STDLIB_JAR:-$TOOL/lib/kotlin-stdlib.jar}"
COROUTINES_JAR="${COROUTINES_JAR:-$TOOL/lib/coroutines.jar}"
COROUTINES_ANDROID_JAR="${COROUTINES_ANDROID_JAR:-$TOOL/lib/coroutines-android.jar}"
VERSION_NAME="2.8.0"

export PATH="$(dirname "$JAVA_BIN"):$PATH"

BUILD="$PROJ/build"
rm -rf "$BUILD"
mkdir -p "$BUILD/compiled" "$BUILD/classes" "$BUILD/dex" "$BUILD/apk"

echo "[1/6] aapt2 compile resources"
"$BT/aapt2" compile --dir "$APP/res" -o "$BUILD/compiled/res.zip"

echo "[2/6] aapt2 link (含 assets)"
"$BT/aapt2" link -o "$BUILD/apk/app.unsigned.apk" \
  -I "$ANDROID_JAR" \
  -A "$APP/assets" \
  --manifest "$APP/AndroidManifest.xml" \
  "$BUILD/compiled/res.zip"

echo "[3/6] kotlinc compile"
CP="$ANDROID_JAR:$OKHTTP_JAR:$OKIO_JAR:$KOTLIN_STDLIB_JAR:$COROUTINES_JAR:$COROUTINES_ANDROID_JAR"
"$KOTLINC" -jvm-target 1.8 -classpath "$CP" -d "$BUILD/classes" \
  "$APP/src/com/cfoptimizer/engine/DnsOverride.kt" \
  "$APP/src/com/cfoptimizer/engine/TimingListener.kt" \
  "$APP/src/com/cfoptimizer/engine/ProbeEngine.kt" \
  "$APP/src/com/cfoptimizer/engine/CfRanges.kt" \
  "$APP/src/com/cfoptimizer/engine/DnsResolver.kt" \
  "$APP/src/com/cfoptimizer/engine/Ranker.kt" \
  "$APP/src/com/cfoptimizer/engine/Pipeline.kt" \
  "$APP/src/com/cfoptimizer/DomainSources.kt" \
  "$APP/src/com/cfoptimizer/DomainSubscription.kt" \
  "$APP/src/com/cfoptimizer/CloudflareDns.kt" \
  "$APP/src/com/cfoptimizer/NetEnv.kt" \
  "$APP/src/com/cfoptimizer/HistoryStore.kt" \
  "$APP/src/com/cfoptimizer/MainActivity.kt"

echo "[4/6] d8 (classes + 依赖 jar → classes.dex)"
mkdir -p "$BUILD/dex"
mapfile -d '' CLASS_FILES < <(find "$BUILD/classes" -name '*.class' -print0)
"$BT/d8" --release --lib "$ANDROID_JAR" --min-api 29 --output "$BUILD/dex" \
  "${CLASS_FILES[@]}" \
  "$OKHTTP_JAR" "$OKIO_JAR" "$KOTLIN_STDLIB_JAR" \
  "$COROUTINES_JAR" "$COROUTINES_ANDROID_JAR"

echo "[5/6] 打包 dex 进 APK"
(cd "$BUILD/dex" && zip -q -u "$BUILD/apk/app.unsigned.apk" classes.dex)

echo "[6/6] zipalign + 签名"
"$BT/zipalign" -f 4 "$BUILD/apk/app.unsigned.apk" "$BUILD/apk/app.aligned.apk"
if [ -n "${SIGNING_KEYSTORE:-}" ]; then
  : "${SIGNING_KEY_ALIAS:?正式构建必须设置 SIGNING_KEY_ALIAS}"
  : "${SIGNING_STORE_PASSWORD_FILE:?正式构建必须设置 SIGNING_STORE_PASSWORD_FILE}"
  APK_OUTPUT="${APK_OUTPUT:-$PROJ/CF-Optimizer-$VERSION_NAME.apk}"
  SIGNING_PASSWORD_ARGS=(--ks-pass "file:$SIGNING_STORE_PASSWORD_FILE")
  if [ -n "${SIGNING_KEY_PASSWORD_FILE:-}" ]; then
    SIGNING_PASSWORD_ARGS+=(--key-pass "file:$SIGNING_KEY_PASSWORD_FILE")
  fi
  "$BT/apksigner" sign --ks "$SIGNING_KEYSTORE" --ks-key-alias "$SIGNING_KEY_ALIAS" \
    "${SIGNING_PASSWORD_ARGS[@]}" \
    --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
    --v4-signing-enabled false \
    --out "$APK_OUTPUT" "$BUILD/apk/app.aligned.apk"
else
  DEBUG_KEYSTORE="$PROJ/cfopt-debug.keystore"
  if [ ! -f "$DEBUG_KEYSTORE" ]; then
    "$JAVA_HOME/bin/keytool" -genkeypair -keystore "$DEBUG_KEYSTORE" \
      -alias cfopt -keyalg RSA -keysize 2048 -validity 10000 \
      -storepass cfoptdebug -keypass cfoptdebug \
      -dname "CN=CFOpt Debug,O=CFOpt,C=CN" 2>/dev/null
  fi
  APK_OUTPUT="${APK_OUTPUT:-$PROJ/CF-Optimizer-$VERSION_NAME-debug.apk}"
  "$BT/apksigner" sign --ks "$DEBUG_KEYSTORE" --ks-key-alias cfopt \
    --ks-pass pass:cfoptdebug --key-pass pass:cfoptdebug \
    --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
    --v4-signing-enabled false \
    --out "$APK_OUTPUT" "$BUILD/apk/app.aligned.apk"
fi

echo "=== 构建完成 ==="
"$BT/apksigner" verify --verbose --print-certs "$APK_OUTPUT"
ls -la "$APK_OUTPUT"
