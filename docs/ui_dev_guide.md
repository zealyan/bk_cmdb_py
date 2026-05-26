# UI 开发环境安装指南

## 一、环境要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Node.js | 16.x | 必须使用 Node.js 16，原项目不支持更高版本 |
| npm | 8.x+ | 随 Node.js 一起安装 |
| MongoDB | 4.4 | 用于数据存储 |

## 二、安装步骤

### 1. 安装 Node.js 16

```bash
# 使用 nvm 安装 Node.js 16
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm install 16
nvm use 16

# 验证安装
node --version  # 输出: v16.x.x
npm --version   # 输出: 8.x.x
```

### 2. 安装 MongoDB 4.4

```bash
# 安装依赖
apt-get update
apt-get install -y gnupg curl wget

# 添加 MongoDB GPG 密钥
curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add -

# 配置 MongoDB 清华镜像源
echo "deb [ arch=amd64 ] https://mirrors.tuna.tsinghua.edu.cn/mongodb/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list

# Ubuntu 24.04 需要安装 libssl1.1 兼容库
wget http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_amd64.deb -O /tmp/libssl1.1.deb
dpkg -i /tmp/libssl1.1.deb

# 安装 MongoDB
apt-get update
apt-get install -y mongodb-org

# 创建数据目录并启动 MongoDB
mkdir -p /data/db
mongod --dbpath /data/db --logpath /var/log/mongodb.log --fork --bind_ip 0.0.0.0 --port 27017

# 验证 MongoDB 启动
mongosh --eval "db.adminCommand('ping')"
```

### 3. 配置 UI 项目

进入 UI 项目目录：
```bash
cd /workspace/bk-cmdb-release-v3.10.41/src/ui
```

修改配置文件 `builder/config/index.js`：

```javascript
dev: {
  // API 配置
  config: Object.assign({}, config, {
    API_URL: JSON.stringify('http://{host}:{port}/proxy/'),
  }),
  // 静态资源路径 - 设为根路径
  assetsPublicPath: '/',
  // API 代理配置
  proxyTable: {
    '/proxy': {
      logLevel: 'info',
      changeOrigin: true,
      target: 'http://localhost:8080/',
      pathRewrite: {
        '^/proxy': ''
      }
    }
  },
  // 开发服务器端口
  port: 9093,
}
```

修改配置文件 `builder/webpack/devserver.js`：

```javascript
historyApiFallback: {
  disableDotRule: false,
  rewrites: [
    { from: /^\/.*$/, to: '/index.html' },
  ],
},
```

### 4. 安装依赖

```bash
cd /workspace/bk-cmdb-release-v3.10.41/src/ui

# 安装项目依赖
npm install

# 安装额外依赖（修复 babel runtime 问题）
npm install @babel/runtime --save
```

### 5. 启动开发服务器

```bash
cd /workspace/bk-cmdb-release-v3.10.41/src/ui
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 16

# 启动开发服务器
npm run dev
```

## 三、验证

启动成功后，终端显示：
```
App running at: http://0.0.0.0:9093
```

访问以下地址验证：

```bash
# 检查首页 HTML
curl -s http://127.0.0.1:9093/ | head -20

# 检查 JS 文件可访问
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9093/js/app.*.js

# 检查静态资源
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9093/static/favicon.ico
```

## 四、常用命令

```bash
# 进入 UI 目录
cd /workspace/bk-cmdb-release-v3.10.41/src/ui

# 设置 Node 版本
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 16

# 启动开发服务器
npm run dev

# 生产环境构建
npm run build

# 查看打包分析
npm run build --report
```

## 五、注意事项

1. **必须使用 Node.js 16**，高版本会导致 fibers 编译失败
2. **端口 9093**，如果被占用会尝试其他端口
3. **API 代理**，前端通过 `/proxy/` 前缀访问后端 API
4. **Mock Server**，开发阶段需要配置 mock server 提供模拟数据

## 六、目录结构

```
/workspace/bk_cmdb_py/                    # Python 后端项目根目录
├── doc/                                   # 项目文档
│   ├── mongodb_install.md                 # MongoDB 安装文档
│   ├── plan.md                            # 项目分析计划
│   └── ui_dev_guide.md                    # UI 开发环境指南（本文档）
│
/workspace/bk-cmdb-release-v3.10.41/src/ui/  # 前端 UI 项目
├── builder/                               # 构建配置
│   ├── config/                            # 配置文件
│   └── webpack/                            # Webpack 配置
├── src/                                   # 源代码
├── node_modules/                          # 依赖
├── package.json                           # 项目配置
└── index.html                             # 入口 HTML
```
