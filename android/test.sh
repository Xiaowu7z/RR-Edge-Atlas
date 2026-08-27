#!/usr/bin/env bash
set -euo pipefail

PROJ="$(cd "$(dirname "$0")" && pwd)"
TOOL="$PROJ/toolchain"
RRAV_TOOL="${RRAV_TOOL:-/srv/hermes-agent/projects/RRAV/toolchain}"
JAVA_HOME="${JAVA_HOME:-$RRAV_TOOL/jdk-17.0.20+8}"
JAVA_BIN="${JAVA_BIN:-$JAVA_HOME/bin/java}"
KOTLINC="${KOTLINC_BIN:-$TOOL/kotlinc/bin/kotlinc}"
OKHTTP_JAR="${OKHTTP_JAR:-$TOOL/lib/okhttp.jar}"
OKIO_JAR="${OKIO_JAR:-$TOOL/lib/okio.jar}"
KOTLIN_STDLIB_JAR="${KOTLIN_STDLIB_JAR:-$TOOL/lib/kotlin-stdlib.jar}"
BUILD="$PROJ/build-tests"

if [ ! -x "$KOTLINC" ]; then
  echo "缺少 Kotlin 编译器：$KOTLINC" >&2
  exit 2
fi
if [ ! -x "$JAVA_BIN" ]; then
  echo "缺少 JDK 17：$JAVA_BIN" >&2
  exit 2
fi

rm -rf "$BUILD"
mkdir -p "$BUILD/classes"
CP="$OKHTTP_JAR:$OKIO_JAR:$KOTLIN_STDLIB_JAR"

"$KOTLINC" -jvm-target 1.8 -classpath "$CP" -d "$BUILD/classes" \
  "$PROJ/app/src/com/cfoptimizer/DomainSources.kt" \
  "$PROJ/app/src/com/cfoptimizer/DomainSubscription.kt" \
  "$PROJ/app/src/com/cfoptimizer/CloudflareDns.kt" \
  "$PROJ/test/DomainSourcesTest.kt" \
  "$PROJ/test/CloudflareDnsTest.kt"

"$JAVA_BIN" -cp "$BUILD/classes:$CP" DomainSourcesTestKt
"$JAVA_BIN" -cp "$BUILD/classes:$CP" CloudflareDnsTestKt
