#!/usr/bin/env bash
#
# setup_deps.sh — 安装并启动 bk-cmdb 运行依赖
#   - MongoDB 4.4.29（副本集 rs0，用户 cc/cc）
#   - Redis 7（密码 cmdb_redis）
#   - ZooKeeper 3.8.6（127.0.0.1:2181）
#
# 幂等：已安装/已运行的组件会跳过。仅执行一次安装即可。
# 参考：docs/env_setup_sop.plan.md §2~§4
#
set -euo pipefail

LOG=/tmp/cmdb_setup_deps.log
exec > >(tee -a "$LOG") 2>&1

echo "================================================================"
echo " bk-cmdb 依赖安装脚本  $(date '+%F %T')"
echo "================================================================"

# ----------------------------- 通用函数 -----------------------------
need_cmd() { command -v "$1" >/dev/null 2>&1; }

# ----------------------------- JAVA (ZK 需要) -----------------------------
echo ">>> [1/3] 检查 Java（ZooKeeper 依赖）"
if need_cmd java; then
  export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
  echo "    Java 已存在: $JAVA_HOME"
else
  echo "!!! 未找到 java，ZooKeeper 无法启动。请先安装 JDK。" >&2
  exit 1
fi

# ----------------------------- MongoDB 4.4 -----------------------------
echo ">>> [2/3] 安装 MongoDB 4.4.29"
if need_cmd mongod; then
  echo "    mongod 已安装，跳过安装"
else
  # Ubuntu 24.04 需 libssl1.1（mongodb 4.4 依赖）
  if ! ldconfig -p | grep -q libssl.so.1.1; then
    echo "    安装 libssl1.1 ..."
    LIBSSL_DEB=/tmp/libssl1.1.deb
    for url in \
      "http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb" \
      "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb" \
      "https://mirrors.cloud.tencent.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb" ; do
      if curl -fsSL "$url" -o "$LIBSSL_DEB"; then echo "      下载成功: $url"; break; fi
    done
    dpkg -i "$LIBSSL_DEB" && rm -f "$LIBSSL_DEB"
  fi

  echo "    配置 MongoDB apt 源（腾讯云 focal 镜像）..."
  curl -fsSL https://pgp.mongodb.com/server-4.4.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-4.4.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/mongodb-4.4.gpg] https://mirrors.cloud.tencent.com/mongodb/apt/ubuntu focal/mongodb-org/4.4 multiverse" > /etc/apt/sources.list.d/mongodb-4.4.list
  apt-get update -o Acquire::Retries=3
  apt-get install -y mongodb-org=4.4.29 mongodb-org-server=4.4.29 mongodb-org-shell=4.4.29 mongodb-org-mongos=4.4.29 mongodb-org-tools=4.4.29
fi

# 启动 MongoDB（副本集模式）
if pgrep -x mongod >/dev/null 2>&1; then
  echo "    mongod 已在运行，跳过启动"
else
  mkdir -p /data/db /var/log/mongodb
  echo "    以副本集 rs0 启动 mongod ..."
  mongod --dbpath /data/db --replSet rs0 --fork --logpath /var/log/mongodb/mongod.log
  sleep 5
  # 初始化副本集
  mongo --quiet --eval 'rs.initiate({_id: "rs0", members: [{_id: 0, host: "127.0.0.1:27017"}]})' || true
  sleep 3
  # 创建数据库用户 cc/cc
  mongo --quiet --eval '
    db = db.getSiblingDB("cmdb");
    if (db.getUser("cc") == null) {
      db.createUser({user: "cc", pwd: "cc", roles: [{role: "readWrite", db: "cmdb"}]});
      print("user cc created");
    } else { print("user cc already exists"); }
  '
fi

# ----------------------------- Redis -----------------------------
echo ">>> [3/3] 安装并启动 Redis"
if need_cmd redis-server; then
  echo "    redis-server 已安装，跳过安装"
else
  apt-get install -y redis-server
fi

if redis-cli -a cmdb_redis ping 2>/dev/null | grep -q PONG; then
  echo "    Redis 已在运行且密码正确，跳过启动"
else
  echo "    启动 redis-server（密码 cmdb_redis）..."
  redis-server --daemonize yes --bind 0.0.0.0 --port 6379
  sleep 2
  redis-cli CONFIG SET requirepass "cmdb_redis"
fi

# ----------------------------- ZooKeeper -----------------------------
echo ">>> [附加] 安装并启动 ZooKeeper 3.8.6"
ZK_HOME=/usr/local/zookeeper
if [ -x "$ZK_HOME/bin/zkServer.sh" ]; then
  echo "    ZooKeeper 已安装，跳过安装"
else
  ZK_TGZ=/tmp/zookeeper.tar.gz
  for url in \
    "https://mirrors.tuna.tsinghua.edu.cn/apache/zookeeper/zookeeper-3.8.6/apache-zookeeper-3.8.6-bin.tar.gz" \
    "https://mirrors.cloud.tencent.com/apache/zookeeper/zookeeper-3.8.6/apache-zookeeper-3.8.6-bin.tar.gz" \
    "https://archive.apache.org/dist/zookeeper/zookeeper-3.8.6/apache-zookeeper-3.8.6-bin.tar.gz" ; do
    if curl -fsSL "$url" -o "$ZK_TGZ"; then echo "      下载成功: $url"; break; fi
  done
  tar -xzf "$ZK_TGZ" -C /usr/local/
  ln -sfn /usr/local/apache-zookeeper-3.8.6-bin "$ZK_HOME"
  rm -f "$ZK_TGZ"
  cp "$ZK_HOME/conf/zoo_sample.cfg" "$ZK_HOME/conf/zoo.cfg"
  sed -i 's|dataDir=/tmp/zookeeper|dataDir=/data/zookeeper|' "$ZK_HOME/conf/zoo.cfg"
  mkdir -p /data/zookeeper
fi

if "$ZK_HOME/bin/zkServer.sh" status >/dev/null 2>&1; then
  echo "    ZooKeeper 已在运行，跳过启动"
else
  echo "    启动 ZooKeeper ..."
  "$ZK_HOME/bin/zkServer.sh" start
  sleep 5
fi

# ----------------------------- 结果校验 -----------------------------
echo "================================================================"
echo " 依赖就绪性检查"
echo "================================================================"
check() { if eval "$2" >/dev/null 2>&1; then echo "  [OK]   $1"; else echo "  [FAIL] $1"; fi; }
check "MongoDB 27017"        "redis-cli -a cmdb_redis ping >/dev/null 2>&1; (ss -ltn 2>/dev/null | grep -q ':27017')"
check "Redis 6379 (auth)"    "redis-cli -a cmdb_redis ping 2>/dev/null | grep -q PONG"
check "ZooKeeper 2181"       "(ss -ltn 2>/dev/null | grep -q ':2181')"
echo "================================================================"
echo "完成。下一步执行 ./start.sh 部署并启动 CMDB 服务。"
