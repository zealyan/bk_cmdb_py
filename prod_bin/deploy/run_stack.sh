#!/usr/bin/env bash
#
# run_stack.sh — 在 supervisord 下常驻拉起并自愈 bk-cmdb 全栈
#   - 启动依赖（MongoDB / Redis / ZooKeeper）
#   - 部署并启动 7 个 CMDB 服务 + migrate
#   - 保活/自愈：每 60s 探活 webserver(8083) 与 adminserver(60004)，不可达则自动重拉
#
# 关键健壮性设计：
#   1) 启动与自愈前均用 fuser 按端口释放可能残留的 CMDB 进程，避免
#      "bind: address already in use"（supervisord 重启时旧子进程变孤儿占用端口）。
#   2) 捕获 TERM/INT，使 supervisord stop 能干净退出（空闲 sleep 循环不会忽略信号）。
#   3) 仅在 supervisord 子环境下运行，命令行不含服务名，pkill 不会误伤自身。
#
set -uo pipefail

DEPLOY=/workspace/bk_cmdb_py/prod_bin/deploy
CMDB_PORTS=(60004 50009 60002 60001 60003 8081 8084)

# supervisord stop 能干净退出
trap 'echo "[$(date '+%F %T')] 收到停止信号，退出。"; exit 0' TERM INT

# 确保 java 可用（ZooKeeper 依赖）。supervisord 环境可能未加载 sdkman。
if ! command -v java >/dev/null 2>&1; then
  export JAVA_HOME=/root/.sdkman/candidates/java/current
  export PATH="$JAVA_HOME/bin:$PATH"
fi

# 按端口释放残留 CMDB 进程（端口级，避免按名 pkill 误伤）
free_cmdb_ports(){
  for p in "${CMDB_PORTS[@]}"; do
    fuser -k "${p}/tcp" 2>/dev/null || true
  done
  sleep 2
}

echo "[$(date '+%F %T')] 清理可能残留的 CMDB 进程/端口..."
free_cmdb_ports

echo "[$(date '+%F %T')] 启动 CMDB 依赖（MongoDB/Redis/ZooKeeper）..."
bash "$DEPLOY/start_deps.sh"

echo "[$(date '+%F %T')] 部署并启动 CMDB 7 个服务 + migrate..."
bash "$DEPLOY/start.sh"

# 启动 Python 后端 (app.py :3000) 与 BFF 集成网关 (:8083)
# —— prod_bin UI 经 8083 接入 Python 后端；Go webserver 已迁至 8084
# 注意：supervisord 环境 PATH 不含 pyenv，必须用 python 绝对路径；setsid 脱离进程组以免被自愈重启误杀
start_python_stack(){
  local BFF_DIR=/workspace/bk_cmdb_py/cmdb_server_py
  local PY_BIN
  PY_BIN=$(ls /root/.pyenv/versions/*/bin/python3.11 2>/dev/null | head -1)
  PY_BIN="${PY_BIN:-python3.11}"
  echo "[$(date '+%F %T')] Python 解释器: $PY_BIN"

  echo "[$(date '+%F %T')] 启动 Python 后端 app.py (3000)..."
  if ! pgrep -f "python3.11 app.py" >/dev/null 2>&1; then
    ( cd "$BFF_DIR" && \
      MONGODB_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb" \
      MONGODB_DB="cmdb" SKIP_LOGIN=true \
      setsid nohup "$PY_BIN" app.py > /tmp/cmdb_py_app.log 2>&1 & )
    sleep 6
  fi
  curl -fsS -o /dev/null "http://127.0.0.1:3000/health" --max-time 5 \
    && echo "[$(date '+%F %T')] [app.py] 已就绪 :3000" \
    || echo "[$(date '+%F %T')] [app.py] 未就绪，见 /tmp/cmdb_py_app.log"

  echo "[$(date '+%F %T')] 启动 Python BFF 集成网关 (8083)..."
  pkill -f "integrated_bff.py" 2>/dev/null || true
  sleep 1
  ( cd "$BFF_DIR" && \
    GO_WEB_PORT=8084 BFF_PORT=8083 \
    CMDB_MONGO_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb" \
    HZ_VIEW_BIZ_ID=1 \
    setsid nohup "$PY_BIN" integrated_bff.py > /tmp/bff.log 2>&1 & )
  sleep 3
  curl -fsS -o /dev/null "http://127.0.0.1:8083/healthz" --max-time 5 \
    && echo "[$(date '+%F %T')] [BFF] 已就绪 :8083" \
    || echo "[$(date '+%F %T')] [BFF] 启动失败，见 /tmp/bff.log"
}
start_python_stack

echo "[$(date '+%F %T')] CMDB 全栈已启动，进入保活/自愈循环（每 60s 探活 webserver:8084 与 adminserver:60004）..."
while true; do
  web_ok=$(curl -fsS -o /dev/null "http://127.0.0.1:8084/"        --max-time 5 && echo yes || echo no)
  adm_ok=$(curl -fsS -o /dev/null "http://127.0.0.1:60004/healthz" --max-time 5 && echo yes || echo no)
  if [ "$web_ok" != "yes" ] || [ "$adm_ok" != "yes" ]; then
    echo "[$(date '+%F %T')] [自愈] webserver=$web_ok adminserver=$adm_ok，重新拉起 CMDB 服务..."
    free_cmdb_ports
    bash "$DEPLOY/start.sh"
    start_python_stack
  fi
  sleep 60
done
