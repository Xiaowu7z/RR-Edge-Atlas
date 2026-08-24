#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
  exec python3 rr_optimizer.py ui
fi

echo "[RR] 未找到 Python 3，请先安装 Python 3.11 或更高版本。" >&2
exit 1

