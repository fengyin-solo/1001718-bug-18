#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# 优先用项目 venv；venv 缺失或损坏（例如在别的平台创建后拷贝过来）时
# 回退到系统 python3，依赖装在用户目录也能直接起。
PYTHON=".venv/bin/python"
if [ ! -x "$PYTHON" ] || ! "$PYTHON" -c "import sys" >/dev/null 2>&1; then
  PYTHON="python3"
fi

if [ "$PYTHON" = ".venv/bin/python" ]; then
  .venv/bin/pip install -q -r requirements.txt
else
  "$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null || "$PYTHON" -m pip install --user -r requirements.txt
fi

exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
