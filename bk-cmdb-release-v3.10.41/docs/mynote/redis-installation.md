# Redis 安装与配置文档

## 1. 环境准备

- **服务器**：192.168.45.141
- **用户**：root
- **Docker**：已安装
- **Redis 镜像**：swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/redis:5.0.7

## 2. 安装步骤

### 2.1 检查镜像是否存在

```bash
docker images | grep redis
```

### 2.2 启动 Redis 容器

使用 host 网络模式启动 Redis 容器，配置端口 6379 和密码认证：

```bash
docker run -d --name redis --network host swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/redis:5.0.7 redis-server --requirepass redis
```

### 2.3 再次启动/检查容器状态

```bash
docker start redis
docker ps | grep redis
```

**执行结果**：

```
68f48563d7a2   swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/redis:5.0.7         "docker-entrypoint.s…"   9 seconds ago   Up 8 seconds             redis
```

## 3. 验证密码认证配置

### 3.1 测试密码认证

```bash
docker exec redis redis-cli -a redis config get requirepass
```

**执行结果**：

```
requirepass
redis
```

### 3.2 验证结论

- ✅ Redis 容器已成功启动
- ✅ 密码认证已配置成功
- ✅ 密码设置为 "redis"
- ✅ 端口 6379 已开放

## 4. 连接信息

- **服务地址**：192.168.45.141:6379
- **密码**：redis
- **服务状态**：正常运行

## 5. 常见问题

### 5.1 容器启动失败

- 检查端口 6379 是否被占用
- 检查 Docker 服务是否运行
- 查看容器日志：`docker logs redis`

### 5.2 密码认证失败

- 确保启动命令中正确设置了 `--requirepass` 参数
- 验证密码是否正确
- 检查网络连接是否正常

