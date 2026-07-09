#!/usr/bin/env bash
#
# start.sh — 基于 prod_bin 部署并启动 bk-cmdb（v3.10.50 最小服务集）
#
# 前置：先运行 ./setup_deps.sh 安装 MongoDB/Redis/ZooKeeper
# 用法：
#   ./start.sh           # 部署 + 启动全部服务 + migrate + 健康检查
#   ./start.sh stop      # 停止全部 CMDB 服务（保留依赖）
#   ./start.sh status    # 查看服务状态
#
# 结构约定：
#   prod_bin/
#     server/<svc>/<svc>        # 6 个 Go 二进制
#     ui/                       # 前端静态资源
#     resources/errors|language # 错误码/语言包（cn/en/default/comon.json）
#     deploy/conf/*.yaml        # 配置文件
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR"
PROD_BIN="$(dirname "$SCRIPT_DIR")"
CONF_DIR="$DEPLOY_DIR/conf"
SERVER_DIR="$PROD_BIN/server"
UI_DIR="$PROD_BIN/ui"
RES_DIR="$PROD_BIN/resources"
DATA_ROOT=/data/cmdb

SERVICES=(cmdb_adminserver cmdb_coreservice cmdb_toposerver cmdb_hostserver cmdb_procserver cmdb_apiserver cmdb_webserver)

# 服务 -> 监听端口 / 启动参数
declare -A PORT=(
  [cmdb_adminserver]=60004 [cmdb_coreservice]=50009 [cmdb_toposerver]=60002
  [cmdb_hostserver]=60001 [cmdb_procserver]=60003 [cmdb_apiserver]=8081 [cmdb_webserver]=8083
)

log(){ echo "[$(date '+%H:%M:%S')] $*"; }

# ----------------------------- stop -----------------------------
stop_all(){
  log "停止 CMDB 服务 ..."
  for s in "${SERVICES[@]}"; do
    if pkill -f "$s" 2>/dev/null; then log "  stopped $s"; else log "  (未运行) $s"; fi
  done
  sleep 2
  log "完成。"
}

# ----------------------------- status -----------------------------
status_all(){
  for s in "${SERVICES[@]}"; do
    pids="$(pgrep -f "$s" | tr '\n' ',' | sed 's/,$//')"
    if [ -n "$pids" ]; then
      printf "  [RUN]  %-18s pid=%s port=%s\n" "$s" "$pids" "${PORT[$s]}"
    else
      printf "  [STOP] %-18s port=%s\n" "$s" "${PORT[$s]}"
    fi
  done
}

# ----------------------------- deploy -----------------------------
deploy(){
  log "==== 1. 检查依赖 ===="
  if ! (ss -ltn 2>/dev/null | grep -q ':27017') ; then
    log "  [警告] MongoDB 未监听 27017，请先运行 ./setup_deps.sh"
  fi
  if ! redis-cli -a cmdb_redis ping 2>/dev/null | grep -q PONG; then
    log "  [警告] Redis 未就绪（密码 cmdb_redis），请先运行 ./setup_deps.sh"
  fi
  if ! (ss -ltn 2>/dev/null | grep -q ':2181') ; then
    log "  [警告] ZooKeeper 未监听 2181，请先运行 ./setup_deps.sh"
  fi

  log "==== 2. 建立目录结构 ===="
  mkdir -p "$DATA_ROOT"/{cmdb_adminserver/configures,cmdb_adminserver/conf/errors,cmdb_adminserver/conf/language,cmdb_coreservice/logs,cmdb_toposerver/logs,cmdb_hostserver/logs,cmdb_apiserver/logs,cmdb_webserver/logs,web}
  for s in "${SERVICES[@]}"; do mkdir -p "$DATA_ROOT/$s/logs"; done

  log "==== 3. 拷贝二进制 ===="
  for s in "${SERVICES[@]}"; do
    cp -f "$SERVER_DIR/$s/$s" "$DATA_ROOT/$s/$s"
    chmod +x "$DATA_ROOT/$s/$s"
    log "  $s -> $DATA_ROOT/$s/$s"
  done

  log "==== 4. 拷贝配置 ===="
  cp -f "$CONF_DIR"/*.yaml "$DATA_ROOT/cmdb_adminserver/configures/"
  log "  配置已写入 $DATA_ROOT/cmdb_adminserver/configures/"

  log "==== 5. 拷贝错误码/语言资源 ===="
  cp -rf "$RES_DIR/errors/."   "$DATA_ROOT/cmdb_adminserver/conf/errors/"
  cp -rf "$RES_DIR/language/." "$DATA_ROOT/cmdb_adminserver/conf/language/"
  log "  errors: $(find "$DATA_ROOT/cmdb_adminserver/conf/errors" -name comon.json | wc -l) 个 comon.json"
  log "  language: $(find "$DATA_ROOT/cmdb_adminserver/conf/language" -name comon.json | wc -l) 个 comon.json"

  log "==== 6. 拷贝前端静态资源 ===="
  cp -rf "$UI_DIR/." "$DATA_ROOT/web/"
  log "  前端已写入 $DATA_ROOT/web/"
}

# ----------------------------- start services -----------------------------
start_services(){
  log "==== 7. 启动服务（顺序：admin -> core -> topo -> host -> api -> web）===="

  # adminserver（--config 指向本地 migrate.yaml）
  cd "$DATA_ROOT/cmdb_adminserver"
  nohup ./"cmdb_adminserver" --addrport=127.0.0.1:60004 \
    --logtostderr=false --log-dir=./logs --v=3 \
    --config=configures/migrate.yaml --enable-auth=false \
    > ./logs/std.log 2>&1 &
  log "  启动 cmdb_adminserver (60004) pid=$!"

  sleep 6   # 等 adminserver 把配置写入 ZK

  start_regdiscv(){
    local svc="$1" port="$2" extra="${3:-}"
    cd "$DATA_ROOT/$svc"
    nohup "./$svc" --addrport="127.0.0.1:$port" \
      --logtostderr=false --log-dir=./logs --v=3 \
      --regdiscv=127.0.0.1:2181 $extra \
      > ./logs/std.log 2>&1 &
    log "  启动 $svc ($port) pid=$!"
    sleep 4
  }

  start_regdiscv cmdb_coreservice 50009
  start_regdiscv cmdb_toposerver  60002 "--enable-auth=false"
  start_regdiscv cmdb_hostserver  60001 "--enable-auth=false"
  # procserver 承载 /process/ 模块（服务分类/服务模板/进程），缺它则新增服务分类 500
  start_regdiscv cmdb_procserver  60003 "--enable-auth=false"
  start_regdiscv cmdb_apiserver   8081  "--enable-auth=false"
  # webserver 绑定 0.0.0.0，--register-ip 避免 0.0.0.0 注册报错
  cd "$DATA_ROOT/cmdb_webserver"
  nohup ./"cmdb_webserver" --addrport=0.0.0.0:8083 \
    --logtostderr=false --log-dir=./logs --v=3 \
    --regdiscv=127.0.0.1:2181 --register-ip=127.0.0.1 \
    > ./logs/std.log 2>&1 &
  log "  启动 cmdb_webserver (8083) pid=$!"
}

# ----------------------------- migrate -----------------------------
run_migrate(){
  log "==== 8. 执行数据库初始化 (migrate) ===="
  for i in $(seq 1 30); do
    code=$(curl -s -o /tmp/migrate_resp.json -w '%{http_code}' -X POST \
      -H 'Content-Type:application/json' -H 'BK_USER:migrate' -H 'HTTP_BLUEKING_SUPPLIER_ID:0' \
      http://127.0.0.1:60004/migrate/v3/migrate/community/0 2>/dev/null)
    if [ "$code" = "200" ]; then
      log "  migrate 返回 HTTP 200: $(head -c 200 /tmp/migrate_resp.json)"
      return 0
    fi
    log "  重试 $i/30 (http=$code) ..."
    sleep 4
  done
  log "  [警告] migrate 未在限定次数内成功，请检查 adminserver 日志：$DATA_ROOT/cmdb_adminserver/logs/"
  return 1
}

# ----------------------------- health -----------------------------
health_check(){
  log "==== 9. 健康检查 ===="
  for s in cmdb_coreservice cmdb_toposerver cmdb_hostserver cmdb_procserver cmdb_apiserver; do
    p=${PORT[$s]}
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/healthz" | grep -q 200; then
      log "  [OK]   $s healthz ($p)"
    else
      log "  [FAIL] $s healthz ($p)"
    fi
  done
  log "  web: http://127.0.0.1:8083/  (账号 admin/admin)"
}

# ----------------------------- main -----------------------------
case "${1:-start}" in
  stop)    stop_all ;;
  status)  status_all ;;
  start|"")
    stop_all
    deploy
    start_services
    sleep 5
    run_migrate
    health_check
    log "部署完成。状态概览："
    status_all
    ;;
  *) echo "用法: $0 [start|stop|status]"; exit 1 ;;
esac
