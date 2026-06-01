# UI 开发环境安装指南

## 一、环境要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Node.js | 16.x | 必须使用 Node.js 16，原项目不支持更高版本 |
| npm | 8.x+ | 随 Node.js 一起安装 |
| MongoDB | 4.4 | 用于数据存储 |
| Python | 3.10 | 用于后端服务 |

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

### 3. 配置 Python 后端服务

#### 3.1 安装 Python 依赖

```bash
cd /workspace
source venv/bin/activate

# 安装必要的依赖
pip install flask flask-cors pymongo bcrypt Flask-Session
```

#### 3.2 启动后端服务（启用 skip-login）

```bash
cd /workspace

# 启用 skip-login 自动登录（开发环境）
export SKIP_LOGIN=true

# 启动后端服务
python app.py
```

后端服务将运行在 `http://localhost:3000`，skip-login 功能会自动以 admin 用户登录。

### 4. 配置 UI 项目

进入 UI 项目目录：

```bash
cd /workspace/bk-cmdb-release-v3.10.41/src/ui
```

#### 4.1 修改配置文件 `builder/config/index.js`

```javascript
dev: {
  // API 配置
  config: Object.assign({}, config, {
    API_URL: JSON.stringify('http://{host}:{port}/proxy/'),
  }),
  // 静态资源路径 - 设为根路径
  assetsPublicPath: '/',
  // API 代理配置 - 指向 Python 后端
  proxyTable: {
    '/proxy': {
      logLevel: 'info',
      changeOrigin: true,
      target: 'http://localhost:3000/',
      pathRewrite: {
        '^/proxy': ''
      }
    }
  },
  // 开发服务器配置
  host: '0.0.0.0',
  port: 8080,
}
```

#### 4.2 创建 Skip-Login 入口文件

创建 `index.skip-login.html` 文件（参考 `index.dev.html`）：

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,minimum-scale=1.0,user-scalable=no,viewport-fit=cover">
    <title>蓝鲸配置平台</title>
    <script type="text/javascript">
        // 动态获取当前协议和端口
        var protocol = window.location.protocol
        var host = window.location.hostname
        var port = window.location.port || (protocol === 'https:' ? '443' : '80')
        var baseUrl = protocol + '//' + host + (port ? ':' + port : '')

        window.Site = {
            url: baseUrl + "/proxy/",
            version: "v3",
            login: "skip-login",
            agent: "",
            authscheme: "internal",
            buildVersion: "dev",
            fullTextSearch: "off",
            helpDocUrl: null,
            disableOperationStatistic: false
        }
        window.User = {
            admin: 1,
            name: "admin"
        }
        window.Supplier = {
            account: '0'
        }
        window.ESB = {
          userManage: ""
        }
        window.API_HOST = baseUrl + "/proxy/"
        window.API_PREFIX = API_HOST + 'api/' + Site.version
    </script>
    <!-- 加载完成后自动登录 -->
    <script type="text/javascript">
        (async function() {
            try {
                const response = await fetch(window.API_HOST + 'user/auth', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                const result = await response.json()
                if (result.result) {
                    document.cookie = 'bk_token=' + result.data.bk_token + ';path=/'
                    console.log('[Skip-Login] 登录成功')
                }
            } catch (error) {
                console.error('[Skip-Login] 登录失败:', error)
            }
        })()
    </script>
</head>
<body>
    <div id="app"></div>
</body>
</html>
```

#### 4.3 配置 Webpack 插件

修改 `builder/webpack/plugins.js`，添加 skip-login HTML 模板：

```javascript
// 在 plugins 函数中添加
const skipLoginHtmlPlugin = new HtmlWebpackPlugin({
  filename: 'index-skip-login.html',
  template: path.resolve(__dirname, '../../index.skip-login.html'),
  inject: false
})

plugins.push(skipLoginHtmlPlugin)
```

#### 4.4 配置开发服务器入口

修改 `builder/webpack/devserver.js`，根据环境变量选择入口：

```javascript
// 在 module.exports 函数中
const skipLogin = process.env.SKIP_LOGIN === 'true'

// 修改 historyApiFallback 配置
historyApiFallback: {
  disableDotRule: false,
  rewrites: [
    ...(skipLogin ? [{ from: /^\/.*$/, to: '/index-skip-login.html' }] : []),
    { from: /^\/.*$/, to: '/index.html' },
  ],
},
```

### 5. 安装依赖

```bash
cd /workspace/bk-cmdb-release-v3.10.41/src/ui

# 安装项目依赖
npm install

# 安装额外依赖（修复 babel runtime 问题）
npm install @babel/runtime --save

# 安装 vConsole 移动端调试工具
npm install vconsole --save
```

### 6. 集成 vConsole 移动端调试工具

#### 6.1 创建 vConsole 初始化文件

创建 `src/setup/vconsole.js`：

```javascript
/*
 * vConsole 移动端调试工具初始化
 * 仅在开发环境启用，提供移动端调试能力
 */

if (process.env.NODE_ENV === 'development') {
  import('vconsole').then((module) => {
    const VConsole = module.default
    window.vConsole = new VConsole({
      defaultPlugins: ['system', 'network', 'element', 'storage'],
      maxLogNumber: 1000,
      onReady: () => {
        console.log('[vConsole] vConsole 已启动，可在右下角查看')
      }
    })
  }).catch((err) => {
    console.warn('[vConsole] 加载失败:', err)
  })
}
```

#### 6.2 在 main.js 中导入

在 `src/main.js` 中添加导入语句：

```javascript
import './setup/vconsole'
```

### 7. 启动开发服务器

```bash
cd /workspace/bk-cmdb-release-v3.10.41/src/ui
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 16

# 启用 skip-login 模式启动开发服务器
export SKIP_LOGIN=true
npm run dev
```

## 三、验证

### 1. 启动后端服务

```bash
# 启动后端
cd /workspace
export SKIP_LOGIN=true
python app.py &

# 验证后端 API
curl http://localhost:3000/site/config
# 预期输出: {"data":{"authscheme":"internal","login":"skip-login"},"result":true}
```

### 2. 启动前端服务

```bash
# 启动前端
cd /workspace/bk-cmdb-release-v3.10.41/src/ui
export SKIP_LOGIN=true
npm run dev

# 终端显示
App running at: http://0.0.0.0:8080
```

### 3. 访问应用

打开浏览器访问：

```bash
# 访问前端应用（自动登录）
http://localhost:8080

# 验证 API 代理
curl -s http://localhost:8080/proxy/api/v3/biz/with_reduced
```

### 4. vConsole 使用

- 在浏览器或移动端访问应用
- 页面右下角会显示 vConsole 按钮
- 点击可查看：
  - **Console**：控制台日志
  - **Network**：网络请求
  - **Element**：页面元素
  - **Storage**：本地存储

## 四、常用命令

```bash
# 进入 UI 目录
cd /workspace/bk-cmdb-release-v3.10.41/src/ui

# 设置 Node 版本
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 16

# 启动开发服务器（skip-login 模式）
export SKIP_LOGIN=true
npm run dev

# 生产环境构建
npm run build

# 查看打包分析
npm run build --report
```

## 五、代码改动清单

### 5.1 后端改动（Python）

| 文件 | 改动说明 |
|------|---------|
| `app/config.py` | 添加 SKIP_LOGIN 配置 |
| `app/routes/user_routes.py` | 实现 skip-login 逻辑，添加 `/site/config` 接口 |
| `app/models/db.py` | 实现 `init_mock_data()` 初始化测试数据 |

### 5.2 前端改动（UI）

| 文件 | 改动说明 |
|------|---------|
| `builder/config/index.js` | 配置 API 代理到 Python 后端（端口 3000） |
| `builder/webpack/plugins.js` | 添加 index-skip-login.html 模板生成 |
| `builder/webpack/devserver.js` | 根据 SKIP_LOGIN 环境变量切换入口 |
| `index.skip-login.html` | **新增** skip-login 专用入口页面 |
| `src/main.js` | 添加 vconsole 初始化导入 |
| `src/setup/vconsole.js` | **新增** vConsole 调试工具配置 |
| `src/api/index.js` | 动态使用 `window.API_PREFIX` 作为 baseURL |
| `src/store/modules/api/object-biz.js` | 添加 `transformData: false` 配置 |

## 六、Skip-Login 功能说明

### 6.1 功能原理

Skip-login 是一种开发环境下的免密码登录机制：

1. **前端**：访问 `index-skip-login.html`，设置 `Site.login = "skip-login"`
2. **自动登录**：页面加载时自动调用 `/user/auth` 接口
3. **后端响应**：检测到 skip-login 模式，直接返回 admin 用户的 token
4. **Cookie 设置**：前端将 token 写入 Cookie，完成登录

### 6.2 使用场景

- ✅ **开发环境**：快速测试，无需输入密码
- ✅ **自动化测试**：无人值守测试
- ❌ **生产环境**：必须关闭，确保安全

### 6.3 安全提示

⚠️ **重要提醒**：
- 禁止在生产环境启用 skip-login
- 仅在本地开发环境使用
- 确保 `SKIP_LOGIN=true` 环境变量仅在开发时设置

## 七、注意事项

1. **必须使用 Node.js 16**，高版本会导致 fibers 编译失败
2. **端口 8080**，如果被占用会尝试其他端口
3. **API 代理**，前端通过 `/proxy/` 前缀访问 Python 后端（端口 3000）
4. **MongoDB 必须启动**，后端依赖 MongoDB 存储数据
5. **Skip-login 仅开发环境使用**，生产环境必须禁用

## 八、目录结构

```
/workspace/                                    # 工作空间根目录
├── bk_cmdb_py/                               # Python 后端项目
│   ├── app/                                 # Flask 应用
│   │   ├── config.py                       # 配置文件
│   │   ├── routes/                         # 路由
│   │   │   └── user_routes.py              # 用户认证路由
│   │   └── models/                         # 数据模型
│   │       └── db.py                       # 数据库操作
│   ├── venv/                               # Python 虚拟环境
│   └── app.py                               # 应用入口
│
├── bk-cmdb-release-v3.10.41/src/ui/         # 前端 UI 项目
│   ├── builder/                             # 构建配置
│   │   ├── config/                         # 配置文件
│   │   │   └── index.js                    # API 代理配置
│   │   └── webpack/                        # Webpack 配置
│   │       ├── plugins.js                   # HTML 模板插件
│   │       └── devserver.js                # 开发服务器配置
│   ├── src/                                 # 源代码
│   │   ├── setup/                          # 初始化脚本
│   │   │   ├── vconsole.js                 # vConsole 配置
│   │   │   └── ...
│   │   ├── api/                            # API 层
│   │   │   └── index.js                    # API 实例配置
│   │   ├── store/                          # Vuex Store
│   │   │   └── modules/api/
│   │   │       └── object-biz.js          # 业务 API
│   │   └── main.js                         # 应用入口
│   ├── index.skip-login.html               # Skip-login 入口页面
│   ├── package.json                        # 项目配置
│   └── ...
│
└── docs/                                   # 文档目录
    ├── mongodb_install.md                  # MongoDB 安装文档
    ├── ui_dev_guide.md                     # UI 开发环境指南（本文档）
    └── skip_login_analysis.md              # Skip-login 原理分析
```

## 九、故障排查

### 问题 1：MongoDB 连接失败

```bash
# 检查 MongoDB 状态
mongosh --eval "db.adminCommand('ping')"

# 如果失败，重新启动
mongod --dbpath /data/db --logpath /var/log/mongodb.log --fork --bind_ip 0.0.0.0 --port 27017
```

### 问题 2：API 请求失败

```bash
# 检查后端是否运行
curl http://localhost:3000/site/config

# 检查前端代理配置
# 确保 builder/config/index.js 中 proxyTable.target 指向 http://localhost:3000
```

### 问题 3：Skip-login 不生效

```bash
# 确保设置环境变量
export SKIP_LOGIN=true

# 检查后端日志
# 应该显示 "[Skip Login] 已启用自动登录功能"
```

### 问题 4：端口被占用

```bash
# 查看端口占用
lsof -ti :8080

# 杀掉进程
kill -9 <PID>

# 或使用其他端口重新启动
```
