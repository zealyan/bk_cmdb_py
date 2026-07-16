#!/usr/bin/env bash
#
# setup_cmdb_supervisor.sh
# ----------------------------------------------------------------------------
# 将「CMDB 完整系统」（最小依赖：仅 MongoDB 4.4.29）的三个服务注册到
# PID 1 的 supervisord，实现沙箱休眠/恢复后自动拉起，并一键产出预览 URL。
#
# 适用模式：完整系统（最小依赖，不拉起任何 Go 服务、ZooKeeper、Redis）。
# 覆盖服务：
#   - MongoDB 4.4.29 副本集 rs0（:27017）
#   - 后端 app.py（Flask，:3000）
#   - UI 服务 ui_server.py（:8085，反向代理 /api/v3 到 :3000）
#
# 幂等性：重复执行安全。reload 会重读配置；已运行进程保持不变或平滑重启。
#
# 用法：
#   sudo bash setup_cmdb_supervisor.sh
#   bash  setup_cmdb_supervisor.sh        # 需 root（沙箱默认 root）
# ----------------------------------------------------------------------------
set -uo pipefail

# ---------- 0. 路径与依赖 ----------
SUP_BIN=/.PlnPyKFp4CRfFtgC1/bin/supervisord
SUP_CONF=/.PlnPyKFp4CRfFtgC1/supervisord-conf/supervisord.conf
SUP_CONF_DIR=/usr/local/share/supervisor
BIN_DIR=/usr/local/bin

BACKEND_DIR=/workspace/bk_cmdb_py/cmdb_server_py
PROD_UI=/workspace/bk_cmdb_py/prod_bin/ui
MONGO_DATA=/data/db
MONGO_LOGDIR=/var/log/mongodb
MONGO_BIN=/usr/bin/mongod

APP_PORT=3000
UI_PORT=8085
MONGODB_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb"

log(){ echo "[$(date '+%F %T')] $*"; }

# ---------- 1. 前置检查 ----------
[ -x "$MONGO_BIN" ] || { log "ERROR: 未找到 mongod ($MONGO_BIN)"; exit 1; }
command -v "$SUP_BIN" >/dev/null 2>&1 || { log "ERROR: 未找到 supervisord ($SUP_BIN)"; exit 1; }
[ -d "$BACKEND_DIR" ] || { log "ERROR: 未找到后端目录 ($BACKEND_DIR)"; exit 1; }
[ -d "$PROD_UI" ] || { log "ERROR: 未找到前端静态目录 ($PROD_UI)"; exit 1; }

mkdir -p "$SUP_CONF_DIR" "$BIN_DIR" "$MONGO_DATA" "$MONGO_LOGDIR"

# 清理 stale mongod.lock（仅当确实无 mongod 运行）
if ! pgrep -x mongod >/dev/null 2>&1; then
  rm -f "$MONGO_DATA/mongod.lock"
  log "已清理可能遗留的 mongod.lock"
fi

# ---------- 2. 写启动包装脚本（前台运行，交由 supervisord 管理）----------
cat > "$BIN_DIR/cmdb_start_mongo.sh" <<'EOF'
#!/bin/bash
# CMDB 完整系统 - MongoDB 前台启动（副本集 rs0），由 supervisord 托管
set -e
mkdir -p /data/db /var/log/mongodb
# 极端情况下若遗留 lock 且无运行实例则清理
if ! pgrep -x mongod >/dev/null 2>&1; then rm -f /data/db/mongod.lock; fi
exec /usr/bin/mongod --dbpath /data/db --replSet rs0 --bind_ip 0.0.0.0 --port 27017
EOF

cat > "$BIN_DIR/cmdb_start_app.sh" <<'EOF'
#!/bin/bash
# CMDB 完整系统 - 后端 app.py 前台启动，由 supervisord 托管
set -e
PY="$(ls /root/.pyenv/versions/*/bin/python3.11 2>/dev/null | head -1)"
PY="${PY:-python3.11}"
DIR=/workspace/bk_cmdb_py/cmdb_server_py
cd "$DIR"
# 等待 MongoDB 就绪（最多 60s），避免启动时序竞态
for i in $(seq 1 60); do
  if "$PY" -c "import pymongo; pymongo.MongoClient('mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb', serverSelectionTimeoutMS=1000).admin.command('ping')" 2>/dev/null; then
    echo "[app] MongoDB 就绪"; break
  fi
  sleep 1
done
export MONGODB_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb"
export MONGODB_DB="cmdb"
export SKIP_LOGIN=false
export SESSION_TYPE=filesystem   # 规避 config.py 中 'filesystem' 拼写缺陷（缺 s）
exec "$PY" app.py
EOF

cat > "$BIN_DIR/cmdb_start_ui.sh" <<'EOF'
#!/bin/bash
# CMDB 完整系统 - UI 服务 ui_server.py 前台启动，由 supervisord 托管
set -e
PY="$(ls /root/.pyenv/versions/*/bin/python3.11 2>/dev/null | head -1)"
PY="${PY:-python3.11}"
DIR=/workspace/bk_cmdb_py/cmdb_server_py
cd "$DIR"
# 等待后端 app.py(:3000) 就绪（最多 60s）
for i in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://127.0.0.1:3000/health" --max-time 2 2>/dev/null; then
    echo "[ui] 后端 app.py 就绪"; break
  fi
  sleep 1
done
export UI_PORT=8085
export BACKEND_URL="http://127.0.0.1:3000"
export PROD_UI_DIR="/workspace/bk_cmdb_py/prod_bin/ui"
exec "$PY" ui_server.py
EOF

chmod +x "$BIN_DIR"/cmdb_start_*.sh
log "已写入启动包装脚本：$BIN_DIR/cmdb_start_{mongo,app,ui}.sh"

# ---------- 3. 写 supervisord 程序配置 ----------
cat > "$SUP_CONF_DIR/cmdb-mongodb.conf" <<EOF
[program:cmdb-mongodb]
command=$BIN_DIR/cmdb_start_mongo.sh
autostart=true
autorestart=true
startsecs=5
startretries=5
stopwaitsecs=20
stopasgroup=true
killasgroup=true
stdout_logfile=/tmp/cmdb-mongodb.log
stderr_logfile=/tmp/cmdb-mongodb.log
redirect_stderr=true
EOF

cat > "$SUP_CONF_DIR/cmdb-app.conf" <<EOF
[program:cmdb-app]
command=$BIN_DIR/cmdb_start_app.sh
directory=$BACKEND_DIR
autostart=true
autorestart=true
startsecs=5
startretries=5
stopwaitsecs=10
stopasgroup=true
killasgroup=true
stdout_logfile=/tmp/cmdb-app.log
stderr_logfile=/tmp/cmdb-app.log
redirect_stderr=true
environment=PATH="/root/.pyenv/versions/3.11.1/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
EOF

cat > "$SUP_CONF_DIR/cmdb-ui.conf" <<EOF
[program:cmdb-ui]
command=$BIN_DIR/cmdb_start_ui.sh
directory=$BACKEND_DIR
autostart=true
autorestart=true
startsecs=5
startretries=5
stopwaitsecs=10
stopasgroup=true
killasgroup=true
stdout_logfile=/tmp/cmdb-ui.log
stderr_logfile=/tmp/cmdb-ui.log
redirect_stderr=true
environment=PATH="/root/.pyenv/versions/3.11.1/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
EOF

log "已写入 supervisord 配置：$SUP_CONF_DIR/cmdb-{mongodb,app,ui}.conf"

# ---------- 4. 加载配置并启动 ----------
log "reload supervisord 以加载新程序（等价于 reread+update，不会全量重启现有进程）..."
"$SUP_BIN" ctl -c "$SUP_CONF" reload

# ---------- 5. 等待 RUNNING ----------
for prog in cmdb-mongodb cmdb-app cmdb-ui; do
  st=""
  for _ in $(seq 1 40); do
    st=$("$SUP_BIN" ctl -c "$SUP_CONF" status "$prog" 2>/dev/null | awk '{print $2}')
    [ "$st" = "RUNNING" ] && break
    sleep 1
  done
  log "$prog => ${st:-UNKNOWN}"
done

# ---------- 6. 校验 ----------
sleep 3
log "端口检查:"
( ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null ) | grep -E ':27017|:3000|:8085' || log "WARN: 端口未全部监听"
log "健康检查:"
curl -fsS -o /dev/null -w "  app /health  -> HTTP %{http_code}\n" "http://127.0.0.1:$APP_PORT/health" --max-time 5 || log "  app 未就绪"
curl -fsS -o /dev/null -w "  ui  /healthz -> HTTP %{http_code}\n" "http://127.0.0.1:$UI_PORT/healthz" --max-time 5 || log "  ui 未就绪"

# ---------- 7. 产出预览 URL（可选）----------
NOTIFY=/root/.codebuddy/skills/preview/notify
if [ -f "$NOTIFY" ]; then
  log "获取预览 URL:"
  "$NOTIFY" "$UI_PORT" || log "notify 失败，请手动执行: $NOTIFY $UI_PORT"
else
  log "未找到 notify 脚本，请手动预览端口 $UI_PORT"
fi

log "完成。"
