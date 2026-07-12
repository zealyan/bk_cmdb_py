#!/usr/bin/env bash
#
# init_cmdb_seed.sh —— 从「已构建的 Go 二进制」重跑 bk-cmdb init/seed 流程
#
# 目的（对应需求四问）：
#   1) 如何清空数据   -> 本脚本的 clear 步骤（先自动 mongodump 备份，再 drop 非系统集合）
#   2) 启动哪个服务   -> 仅需 cmdb_adminserver（60004），它内置 migrate 能力
#   3) 运行哪个脚本   -> 本脚本调用 adminserver 的 migrate 接口完成 init seed
#                        POST http://127.0.0.1:60004/migrate/v3/migrate/community/0
#   4) 补充业务/主机  -> 见同仓 cmdb_server_py/seed_extra.py（本脚本 --with-extra 可串联）
#
# 重要前提：
#   * MongoDB(27017, replSet rs0) / Redis(6379) / ZooKeeper(2181) 已就绪
#     （可先 ./start_deps.sh 拉起依赖；本脚本不负责拉依赖）
#   * 预编译二进制在 prod_bin/server/<svc>/<svc>
#   * Python 后端直接读 Mongo 的 cmdb 库，init seed 后 Go 服务可停（见 --no-stop-admin）
#
# 用法：
#   ./init_cmdb_seed.sh                 # 仅备份 + 打印将执行步骤（不破坏数据）
#   ./init_cmdb_seed.sh run --clear     # 备份→清空→部署→启动 adminserver→migrate→校验→停 admin
#   ./init_cmdb_seed.sh run --clear --with-extra   # 上述 + 串联 seed_extra.py（1 业务 + 12 主机）
#   ./init_cmdb_seed.sh run --clear --no-stop-admin # migrate 后保留 adminserver 运行
#   ./init_cmdb_seed.sh backup          # 仅备份 cmdb
#   ./init_cmdb_seed.sh clear           # 仅清空（会先自动备份）
#   ./init_cmdb_seed.sh migrate         # 假设 adminserver 已起，仅执行 migrate
#   ./init_cmdb_seed.sh status          # 查看依赖/服务/数据概况
#
set -uo pipefail

# ----------------------------- 路径与常量 -----------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR"
PROD_BIN="$(dirname "$DEPLOY_DIR")"
SERVER_DIR="$PROD_BIN/server"
RES_DIR="$PROD_BIN/resources"
DATA_ROOT=/data/cmdb
ADMIN_DIR="$DATA_ROOT/cmdb_adminserver"
ADMIN_BIN="$ADMIN_DIR/cmdb_adminserver"
MIGRATE_PORT=60004
MIGRATE_URL="http://127.0.0.1:$MIGRATE_PORT/migrate/v3/migrate/community/0"

MONGO_BIN="${MONGO_BIN:-/usr/bin/mongo}"
MONGO_DUMP="${MONGO_DUMP:-/usr/bin/mongodump}"
BACKUP_ROOT="${BACKUP_ROOT:-$PROD_BIN/backups}"

# 与 Go(mongodb.yaml) / Python(config.py) 完全一致的连接串
MONGO_URI="${MONGO_URI:-mongodb://cc:cc@127.0.0.1:27017/cmdb?replicaSet=rs0&authSource=cmdb}"

log(){ echo "[$(date '+%H:%M:%S')] $*"; }
die(){ echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; exit 1; }

# ----------------------------- 依赖检查 -----------------------------
check_deps(){
  local ok=1
  for b in mongod redis-server java; do
    if ! pgrep -f "$b" >/dev/null 2>&1; then
      log "  [警告] 依赖进程未运行: $b（请先 ./start_deps.sh）"
      ok=0
    fi
  done
  ss -ltn 2>/dev/null | grep -q ':27017' || { log "  [警告] MongoDB 未监听 27017"; ok=0; }
  ss -ltn 2>/dev/null | grep -q ':2181'  || { log "  [警告] ZooKeeper 未监听 2181（adminserver migrate 需要）"; ok=0; }
  [ -x "$MONGO_DUMP" ] || { log "  [警告] mongodump 不存在: $MONGO_DUMP"; ok=0; }
  [ -x "$MONGO_BIN" ]  || { log "  [警告] mongo 客户端不存在: $MONGO_BIN"; ok=0; }
  if [ "$ok" = "1" ]; then
    log "  依赖检查通过"
    return 0
  else
    return 1
  fi
}

# ----------------------------- 备份（Q1 前置）-----------------------------
do_backup(){
  mkdir -p "$BACKUP_ROOT"
  local ts; ts="$(date '+%Y%m%d_%H%M%S')"
  local out="$BACKUP_ROOT/cmdb_$ts"
  log "==== 备份 cmdb 数据库 -> $out ===="
  "$MONGO_DUMP" --uri="$MONGO_URI" --db cmdb --out "$out" >/dev/null 2>&1 \
    || die "mongodump 失败，已中止（不会清空数据）"
  log "  备份完成: $(du -sh "$out" 2>/dev/null | cut -f1)  $(find "$out" -name '*.bson' | wc -l) 个集合"
  echo "$out"
}

# ----------------------------- 清空（Q1）-----------------------------
do_clear(){
  log "==== 清空 cmdb 数据（保留 system.* 与账号）===="
  "$MONGO_BIN" --quiet "$MONGO_URI" --eval '
  var dropped = 0;
  db.getCollectionNames().forEach(function(c){
    if (c.indexOf("system.") === 0) return;   // 绝不删除 system.users / system.version
    db.getCollection(c).drop();
    dropped++;
  });
  print("已清空非系统集合数量: " + dropped);
  void 0;
  ' 2>&1 | grep -v 'DeprecationWarning\|future\|WARNING' \
    || die "清空失败"
  log "  清空完成。"
}

# ----------------------------- 部署 adminserver -----------------------------
deploy_admin(){
  log "==== 部署 cmdb_adminserver -> $ADMIN_DIR ===="
  mkdir -p "$ADMIN_DIR"/{configures,conf/errors,conf/language,logs,web}
  [ -f "$SERVER_DIR/cmdb_adminserver/cmdb_adminserver" ] \
    || die "缺失预编译二进制: $SERVER_DIR/cmdb_adminserver/cmdb_adminserver"
  cp -f "$SERVER_DIR/cmdb_adminserver/cmdb_adminserver" "$ADMIN_BIN"
  chmod +x "$ADMIN_BIN"
  cp -f "$DEPLOY_DIR/conf"/*.yaml "$ADMIN_DIR/configures/"
  # 错误码 / 语言资源（仅 adminserver 启动需要，migrate 数据本身不依赖）
  if [ -d "$RES_DIR/errors" ];   then cp -rf "$RES_DIR/errors/."   "$ADMIN_DIR/conf/errors/";   fi
  if [ -d "$RES_DIR/language" ]; then cp -rf "$RES_DIR/language/." "$ADMIN_DIR/conf/language/"; fi
  log "  部署完成。"
}

# ----------------------------- 启动 adminserver（Q2）-----------------------------
start_admin(){
  # 若已运行则先停，避免端口冲突
  if pgrep -f "cmdb_adminserver" >/dev/null 2>&1; then
    log "  检测到已运行的 adminserver，先停止..."
    pkill -f "cmdb_adminserver"; sleep 3
  fi
  log "==== 启动 cmdb_adminserver（migrate 端口 $MIGRATE_PORT）===="
  cd "$ADMIN_DIR"
  nohup ./"cmdb_adminserver" --addrport=127.0.0.1:$MIGRATE_PORT \
    --logtostderr=false --log-dir=./logs --v=3 \
    --config=configures/migrate.yaml --enable-auth=false \
    > ./logs/std.log 2>&1 &
  log "  pid=$!"
  # 等端口监听（最多 ~30s）
  local i
  for i in $(seq 1 30); do
    if ss -ltn 2>/dev/null | grep -q ":$MIGRATE_PORT "; then
      log "  adminserver 已监听 $MIGRATE_PORT"; return 0
    fi
    sleep 1
  done
  log "  [警告] 端口 $MIGRATE_PORT 未在预期时间内监听，查看日志: $ADMIN_DIR/logs/std.log"
  return 1
}

# ----------------------------- 执行 migrate（Q3）-----------------------------
do_migrate(){
  log "==== 执行 init seed（POST $MIGRATE_URL）===="
  local i code
  for i in $(seq 1 40); do
    code=$(curl -s -o /tmp/migrate_resp.json -w '%{http_code}' -X POST \
      -H 'Content-Type:application/json' -H 'BK_USER:migrate' -H 'HTTP_BLUEKING_SUPPLIER_ID:0' \
      "$MIGRATE_URL" 2>/dev/null)
    if [ "$code" = "200" ]; then
      log "  migrate 返回 HTTP 200"
      log "  响应: $(head -c 300 /tmp/migrate_resp.json)"
      return 0
    fi
    log "  重试 $i/40 (http=$code) ..."
    sleep 4
  done
  log "  [失败] migrate 未在限定次数内成功，请检查: $ADMIN_DIR/logs/"
  return 1
}

# ----------------------------- 校验 -----------------------------
verify(){
  log "==== 校验 init seed 结果 ===="
  "$MONGO_BIN" --quiet "$MONGO_URI" --eval '
  var att = db.cc_ObjAttDes.countDocuments({});
  var biz = db.cc_ApplicationBase.countDocuments({});
  var set = db.cc_SetBase.countDocuments({});
  var mod = db.cc_ModuleBase.countDocuments({});
  var host = db.cc_HostBase.countDocuments({});
  print("cc_ObjAttDes(模型属性, 期望≈145): " + att);
  print("cc_ApplicationBase(业务, 含资源池): " + biz);
  print("cc_SetBase(集群): " + set);
  print("cc_ModuleBase(模块): " + mod);
  print("cc_HostBase(主机, init seed 不创建实例=0): " + host);
  var rp = db.cc_ApplicationBase.findOne({default:1}, {bk_biz_name:1,_id:0});
  print("资源池(内置业务): " + (rp?rp.bk_biz_name:"缺失!"));
  void 0;
  ' 2>&1 | grep -v 'DeprecationWarning\|future\|WARNING'
}

# ----------------------------- 停止 adminserver -----------------------------
stop_admin(){
  if pgrep -f "cmdb_adminserver" >/dev/null 2>&1; then
    log "==== 停止 adminserver（Python 后端直接读 Mongo，无需常驻 Go 服务）===="
    pkill -f "cmdb_adminserver"; sleep 2; log "  已停止。"
  fi
}

# ----------------------------- status -----------------------------
do_status(){
  log "==== 依赖 ====="
  ( ss -ltn 2>/dev/null | grep -q ':27017' && echo "  [OK] Mongo 27017" || echo "  [X] Mongo 27017" )
  ( ss -ltn 2>/dev/null | grep -q ':2181'  && echo "  [OK] ZooKeeper 2181" || echo "  [X] ZooKeeper 2181" )
  ( redis-cli -a cmdb_redis ping 2>/dev/null | grep -q PONG && echo "  [OK] Redis 6379" || echo "  [X] Redis 6379" )
  log "==== 服务 ====="
  ( ss -ltn 2>/dev/null | grep -q ":$MIGRATE_PORT " && echo "  [RUN] cmdb_adminserver $MIGRATE_PORT" || echo "  [STOP] cmdb_adminserver $MIGRATE_PORT" )
  log "==== 数据概况（cmdb）===="
  "$MONGO_BIN" --quiet "$MONGO_URI" --eval '
  ["cc_ObjAttDes","cc_ApplicationBase","cc_SetBase","cc_ModuleBase","cc_HostBase","cc_ModuleHostConfig","cc_ObjectBase_0_pub_bk_switch"].forEach(function(c){
    try { print("  " + c.padEnd(34) + db.getCollection(c).countDocuments({})); } catch(e){ print("  " + c + " ERR"); }
  });
  void 0;
  ' 2>&1 | grep -v 'DeprecationWarning\|future\|WARNING'
}

# ----------------------------- run（主流程）-----------------------------
run_flow(){
  local CLEAR=0 WITH_EXTRA=0 NO_STOP_ADMIN=0
  for a in "$@"; do
    case "$a" in
      --clear) CLEAR=1;;
      --with-extra) WITH_EXTRA=1;;
      --no-stop-admin) NO_STOP_ADMIN=1;;
      *) echo "未知参数: $a" >&2;;
    esac
  done

  check_deps || die "依赖未就绪，请先 ./start_deps.sh"

  # 1) 永远先备份（即便不清空，也保证可回滚）
  do_backup

  if [ "$CLEAR" = "1" ]; then
    do_clear
    deploy_admin
    start_admin || die "adminserver 启动失败"
    do_migrate || die "migrate 失败"
    verify
    if [ "$NO_STOP_ADMIN" = "0" ]; then
      stop_admin
    else
      log "  保留 adminserver 运行（--no-stop-admin）。"
    fi
    if [ "$WITH_EXTRA" = "1" ]; then
      log "==== 串联 seed_extra.py（1 业务 + 12 主机）===="
      # cmdb_server_py 是 prod_bin 的兄弟目录（Python 后端），不在 prod_bin 下
      SEED_EXTRA="$PROD_BIN/../cmdb_server_py/seed_extra.py"
      [ -f "$SEED_EXTRA" ] || SEED_EXTRA="$(dirname "$PROD_BIN")/cmdb_server_py/seed_extra.py"
      python3 "$SEED_EXTRA" \
        || log "  [警告] seed_extra.py 执行失败，请单独排查"
    fi
    log "==== 完成。Python 后端可直接读取 cmdb 库。===="
  else
    log "（未指定 --clear，仅完成备份与状态展示，未清空/未 migrate）"
    log "如需重跑 init seed，请执行: $0 run --clear"
    do_status
  fi
}

# ----------------------------- 入口 -----------------------------
case "${1:-run}" in
  run)     shift; run_flow "$@" ;;
  backup)  do_backup ;;
  clear)   check_deps; do_backup >/dev/null; do_clear ;;
  migrate) start_admin; do_migrate; verify; stop_admin ;;
  status)  do_status ;;
  -h|--help|help) sed -n '2,30p' "$0" ;;
  *) echo "用法: $0 [run|backup|clear|migrate|status] [--clear] [--with-extra] [--no-stop-admin]"; exit 1 ;;
esac
