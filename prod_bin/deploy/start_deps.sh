#!/usr/bin/env bash
#
# start_deps.sh — 仅启动 bk-cmdb 运行依赖（幂等，不做安装/初始化）
#   - MongoDB 4.4（副本集 rs0，数据目录 /data/db）
#   - Redis 7（密码 cmdb_redis）
#   - ZooKeeper 3.8.6（127.0.0.1:2181）
#
# 适用场景：沙箱休眠恢复后，依赖进程丢失但数据/二进制仍在，用本脚本快速重启依赖，
#           随后执行 ./start.sh 拉起 CMDB 服务。
# 前置：已通过 ./setup_deps.sh 完成一次性安装。
#
set -uo pipefail

JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
export JAVA_HOME

ZK_HOME=/usr/local/zookeeper
log(){ echo "[$(date '+%H:%M:%S')] $*"; }

# ----------------------------- MongoDB -----------------------------
log ">>> MongoDB"
if (exec 3<>/dev/tcp/127.0.0.1/27017) 2>/dev/null; then
  log "    已在监听，跳过"
  exec 3>&-
else
  mkdir -p /data/db /var/log/mongodb
  log "    以副本集 rs0 启动 mongod ..."
  if ! mongod --dbpath /data/db --replSet rs0 --fork --logpath /var/log/mongodb/mongod.log; then
    log "    [重试] 检测到可能的不干净关闭，执行 --repair 后重启 ..."
    mongod --dbpath /data/db --repair --logpath /var/log/mongodb/mongod-repair.log
    mongod --dbpath /data/db --replSet rs0 --fork --logpath /var/log/mongodb/mongod.log
  fi
  sleep 5
  # 仅在未初始化副本集时执行（已初始化会报错，忽略即可）
  mongo --quiet --eval 'try { rs.initiate({_id:"rs0", members:[{_id:0, host:"127.0.0.1:27017"}]}); } catch(e){}' 2>/dev/null || true
  sleep 3
fi

# ----------------------------- Redis -----------------------------
log ">>> Redis"
if redis-cli -a cmdb_redis ping 2>/dev/null | grep -q PONG; then
  log "    已在运行且密码正确，跳过"
else
  log "    启动 redis-server ..."
  redis-server --daemonize yes --bind 0.0.0.0 --port 6379
  sleep 2
  redis-cli CONFIG SET requirepass "cmdb_redis"
fi

# ----------------------------- ZooKeeper -----------------------------
log ">>> ZooKeeper"
if "$ZK_HOME/bin/zkServer.sh" status >/dev/null 2>&1; then
  log "    已在运行，跳过"
else
  log "    启动 ZooKeeper ..."
  "$ZK_HOME/bin/zkServer.sh" start
  sleep 5
fi

# ----------------------------- 校验 -----------------------------
echo "================================================================"
check(){ if eval "$2" >/dev/null 2>&1; then echo "  [OK]   $1"; else echo "  [FAIL] $1"; fi; }
check "MongoDB 27017"   "(exec 3<>/dev/tcp/127.0.0.1/27017) 2>/dev/null"
check "Redis 6379 (auth)" "redis-cli -a cmdb_redis ping 2>/dev/null | grep -q PONG"
check "ZooKeeper 2181"  "(exec 3<>/dev/tcp/127.0.0.1/2181) 2>/dev/null"
echo "================================================================"
log "依赖就绪。下一步执行 ./start.sh 启动 CMDB 服务。"
