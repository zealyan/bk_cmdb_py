# MongoDB 4.4 安装文档

## 环境信息
- 操作系统：Ubuntu 24.04.3 LTS (Noble Numbat)
- 内核：Linux 6.18.5 x86_64
- 安装版本：MongoDB 4.4.29

## 安装步骤

### 1. 安装依赖工具
```bash
apt-get update
apt-get install -y gnupg curl
```

### 2. 添加 MongoDB GPG 密钥
```bash
curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add -
```

### 3. 配置 MongoDB 清华镜像源
```bash
echo "deb [ arch=amd64 ] https://mirrors.tuna.tsinghua.edu.cn/mongodb/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list
```

### 4. 安装 libssl1.1（Ubuntu 24.04 兼容）
```bash
wget http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_amd64.deb -O /tmp/libssl1.1.deb
dpkg -i /tmp/libssl1.1.deb
```

### 5. 安装 MongoDB
```bash
apt-get update
apt-get install -y mongodb-org
```

### 6. 创建数据目录
```bash
mkdir -p /data/db
chown -R mongodb:mongodb /data/db
```

### 7. 启动 MongoDB 单实例服务
```bash
mongod --dbpath /data/db --logpath /var/log/mongodb.log --fork --bind_ip 0.0.0.0 --port 27017
```

### 8. 验证服务
```bash
mongo --eval "db.version(); db.adminCommand('ping');"
```

### 9. 服务管理命令
```bash
# 连接 MongoDB
mongo

# 停止服务
mongod --dbpath /data/db --shutdown

# 查看日志
tail -f /var/log/mongodb.log
```

## 验证结果
```
MongoDB Version: 4.4.29
Server Status: OK
{ "ok" : 1 }
```

## 安装配置
| 配置项 | 值 |
|--------|-----|
| 数据目录 | /data/db |
| 日志文件 | /var/log/mongodb.log |
| 监听地址 | 0.0.0.0:27017 |
| 包管理源 | mirrors.tuna.tsinghua.edu.cn (清华镜像) |
