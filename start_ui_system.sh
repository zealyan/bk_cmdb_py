#!/usr/bin/env bash
#
# start_ui_system.sh — 启动「完整的 CMDB 系统」（BFF 无关、最小依赖）
#
#   依赖：MongoDB（已有 cmdb 实例 + initdb 原生数据）
#   服务：cmdb_server_py (app.py :3000) + UI 服务 (ui_server.py :8085)
#   说明：本脚本与 run_stack.sh（Go 全栈 + BFF）相互独立，不拉起任何 Go 服务 / ZooKeeper / Redis。
#
# 登录：内置管理员 admin / admin（与 bk-cmdb common.yaml webServer.session.userInfo 对齐）
#
set -uo pipefail

BFF_DIR=/workspace/bk_cmdb_py/cmdb_server_py
PROD_UI=/workspace/bk_cmdb_py/prod_bin/ui
PY_BIN=$(ls /root/.pyenv/versions/*/bin/python3.11 2>/dev/null | head -1)
PY_BIN="${PY_BIN:-python3.11}"

APP_PORT=3000
UI_PORT=8085
BACKEND_URL="http://127.0.0.1:${APP_PORT}"

echo "[$(date '+%F %T')] 使用 Python: $PY_BIN"

# 1) 确认 MongoDB 就绪（cmdb 实例）
echo "[$(date '+%F %T')] 检查 MongoDB(27017)..."
if "$PY_BIN" - <<'PY' 2>/dev/null
import sys
try:
    from pymongo import MongoClient
    MongoClient("mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb",
                serverSelectionTimeoutMS=3000).admin.command("ping")
except Exception as e:
    print("MongoDB 不可用:", e); sys.exit(1)
PY
then
  echo "[$(date '+%F %T')] MongoDB 就绪"
else
  echo "[$(date '+%F %T')] 警告: MongoDB 未就绪，app.py 可能无法连接" >&2
fi

# 2) 启动 app.py（关闭 SKIP_LOGIN，走真实登录；admin/admin 内置管理员兜底）
echo "[$(date '+%F %T')] 启动 app.py (:${APP_PORT})..."
fuser -k ${APP_PORT}/tcp 2>/dev/null || true
sleep 1
( cd "$BFF_DIR" && \
  MONGODB_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb" \
  MONGODB_DB="cmdb" SKIP_LOGIN=false \
  setsid nohup "$PY_BIN" app.py > /tmp/cmdb_py_app.log 2>&1 & )
sleep 6
curl -fsS -o /dev/null "http://127.0.0.1:${APP_PORT}/health" --max-time 5 \
  && echo "[$(date '+%F %T')] [app.py] 已就绪 :${APP_PORT}" \
  || { echo "[$(date '+%F %T')] [app.py] 启动失败，见 /tmp/cmdb_py_app.log"; tail -20 /tmp/cmdb_py_app.log; }

# 3) 启动 UI 服务
echo "[$(date '+%F %T')] 启动 UI 服务 (:${UI_PORT})..."
fuser -k ${UI_PORT}/tcp 2>/dev/null || true
sleep 1
( cd "$BFF_DIR" && \
  UI_PORT="${UI_PORT}" BACKEND_URL="${BACKEND_URL}" PROD_UI_DIR="${PROD_UI}" \
  setsid nohup "$PY_BIN" ui_server.py > /tmp/cmdb_py_ui.log 2>&1 & )
sleep 4
curl -fsS -o /dev/null "http://127.0.0.1:${UI_PORT}/healthz" --max-time 5 \
  && echo "[$(date '+%F %T')] [UI] 已就绪 :${UI_PORT}" \
  || { echo "[$(date '+%F %T')] [UI] 启动失败，见 /tmp/cmdb_py_ui.log"; tail -20 /tmp/cmdb_py_ui.log; }

echo
echo "[$(date '+%F %T')] 系统已启动："
echo "    UI 入口 : http://127.0.0.1:${UI_PORT}/"
echo "    后端 API: http://127.0.0.1:${APP_PORT}/  (经 UI 代理 /api/v3)"
echo "    账号    : admin / admin"
