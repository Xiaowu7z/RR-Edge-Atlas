#!/usr/bin/env bash
set -euo pipefail

PROJ="$(cd "$(dirname "$0")" && pwd)"
TOOL="$PROJ/toolchain"
RRAV_TOOL="${RRAV_TOOL:-/srv/hermes-agent/projects/RRAV/toolchain}"
JDK="$RRAV_TOOL/jdk-17.0.20+8"
KOTLINC="$TOOL/kotlinc/bin/kotlinc"
LIB="$TOOL/lib"
BUILD="$PROJ/build-tests"

if [ ! -x "$KOTLINC" ]; then
  echo "缺少 Kotlin 编译器：$KOTLINC" >&2
  exit 2
fi
if [ ! -x "$JDK/bin/java" ]; then
  echo "缺少 JDK 17：$JDK" >&2
  exit 2
fi

rm -rf "$BUILD"
mkdir -p "$BUILD/classes"
CP="$LIB/okhttp.jar:$LIB/okio.jar:$LIB/kotlin-stdlib.jar"

"$KOTLINC" -jvm-target 1.8 -classpath "$CP" -d "$BUILD/classes" \
  "$PROJ/app/src/com/cfoptimizer/DomainSources.kt" \
  "$PROJ/app/src/com/cfoptimizer/DomainSubscription.kt" \
  "$PROJ/app/src/com/cfoptimizer/CloudflareDns.kt" \
  "$PROJ/test/DomainSourcesTest.kt" \
  "$PROJ/test/CloudflareDnsTest.kt"

"$JDK/bin/java" -cp "$BUILD/classes:$CP" DomainSourcesTestKt
"$JDK/bin/java" -cp "$BUILD/classes:$CP" CloudflareDnsTestKt
