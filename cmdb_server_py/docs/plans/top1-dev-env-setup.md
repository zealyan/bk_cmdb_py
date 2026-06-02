# TOP1: 开发环境准备 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 bk-cmdb-py 项目的完整开发环境配置，包括 Python、MongoDB、所有依赖库的安装和验证

**Architecture:** 系统化地完成从操作系统级到项目级的所有依赖安装，确保可完整运行

**Tech Stack:** Python 3.10+, MongoDB 4.4+, Flask, pymongo, mongoengine, Flask-SQLAlchemy, py-pglite

---

## 数据库配置（前置参考）

### MongoDB 配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **Database Name** | `bk_cmdb` | MongoDB 数据库名称 |
| **Connection URI** | `mongodb://localhost:27017/` | 连接地址 |
| **Port** | `27017` | MongoDB 端口 |

### py-pglite 配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **Data Directory** | `./pglite_data` | py-pglite 数据存储目录 |
| **Socket Path** | `./pglite_data/.s.PGSQL.5432` | Unix Socket 文件路径 |
| **Database Name** | `postgres` | 默认数据库名 |
| **Schema** | `public` (默认) | 数据库 Schema |
| **管理方式** | Node.js | 使用 `@electric-sql/pglite` + `@electric-sql/pglite-socket` |
| **连接方式** | Unix Socket | Python 通过 Socket 连接 |
| **Socket 权限** | `777` | 跨进程访问需要 |

---

## 文件结构规划

| 动作 | 文件路径 | 说明 |
|------|---------|------|
| 创建 | `docs/plans/top1-dev-env-setup.md` | 本计划文档（已创建） |
| 参考 | `/workspace/bk_cmdb_py/docs/mongodb_install.md` | MongoDB 安装文档 |
| 参考 | `/workspace/bk_cmdb_py/requirements.txt` | 项目依赖列表 |
| 参考 | `/workspace/bk_cmdb_py/pyproject.toml` | 项目配置文件 |

---

## 任务分解

---

### Task 1: 验证现有环境与准备

**Files:**
- 检查: `/workspace/bk_cmdb_py/requirements.txt`
- 检查: `/workspace/bk_cmdb_py/.python-version`

- [ ] **Step 1: 检查当前 Python 版本**

```bash
cd /workspace/bk_cmdb_py
python --version
python3 --version
```

- [ ] **Step 2: 检查 pip 与虚拟环境**

```bash
pip --version
pip3 --version
which python
which python3
```

- [ ] **Step 3: 检查系统是否安装 MongoDB**

```bash
mongod --version || echo "MongoDB not installed"
ps aux | grep mongod || echo "MongoDB not running"
```

- [ ] **Step 4: 查看现有项目配置**

```bash
cat /workspace/bk_cmdb_py/requirements.txt
cat /workspace/bk_cmdb_py/pyproject.toml 2>/dev/null || echo "No pyproject.toml found"
```

---

### Task 2: 安装与配置 Python 3.10+ 环境

**Files:**
- 参考: `.python-version` (如果存在)
- 参考: `requirements.txt`

- [ ] **Step 1: 检查可用的 Python 版本**

```bash
cd /workspace/bk_cmdb_py
# 检查系统已安装的 Python
ls -la /usr/bin/python*
ls -la /usr/local/bin/python*

# 如果使用 pyenv，检查可用版本
which pyenv || echo "pyenv not available"
pyenv versions 2>/dev/null || echo "pyenv not installed"
```

- [ ] **Step 2: 确定使用的 Python 版本 (3.10+) 并创建虚拟环境**

```bash
cd /workspace/bk_cmdb_py

# 使用系统 Python 创建虚拟环境
python3 -m venv venv
# 或使用具体的 python 版本
# /usr/bin/python3.10 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 验证
python --version
which python
```

- [ ] **Step 3: 升级 pip 到最新版本**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

pip install --upgrade pip
pip --version
```

- [ ] **Step 4: 提交环境准备**

```bash
cd /workspace/bk_cmdb_py
# 确保 .gitignore 包含 venv
grep -q "venv" .gitignore || echo "venv/" >> .gitignore
git add .gitignore
git status
```

---

### Task 3: 安装项目 Python 依赖库

**Files:**
- 核心文件: `requirements.txt`

- [ ] **Step 1: 使用 requirements.txt 安装所有依赖**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

pip install -r requirements.txt
```

- [ ] **Step 2: 验证依赖安装**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

pip list
```

验证关键包：
```
Flask==2.3.3
Flask-Cors==4.0.0
Flask-SQLAlchemy==3.1.1
pymongo==4.5.0
SQLAlchemy==2.0.23
mongoengine==0.28.2
py-pglite==0.5.3
python-dotenv==1.0.0
```

- [ ] **Step 3: 简单验证 Flask 应用导入**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

python -c "
import sys
print('Python:', sys.version)
import flask
print('Flask:', flask.__version__)
import pymongo
print('pymongo:', pymongo.version)
import mongoengine
print('mongoengine:', mongoengine.__version__)
import sqlalchemy
print('SQLAlchemy:', sqlalchemy.__version__)
import py_pglite
print('py-pglite: OK')
print('All dependencies imported successfully!')
"
```

---

### Task 4: 安装并启动 MongoDB

**Files:**
- 参考: `docs/mongodb_install.md`
- 配置: `app/config.py`

- [ ] **Step 1: 检查 MongoDB 安装与运行状态**

```bash
which mongod
mongod --version

# 检查运行状态
ps aux | grep -v grep | grep mongod
curl --connect-timeout 2 http://localhost:27017/ 2>&1 || echo "MongoDB not running"
```

- [ ] **Step 2: 如果 MongoDB 未安装，按 mongodb_install.md 安装**

```bash
cd /workspace/bk_cmdb_py
cat docs/mongodb_install.md
```

**快速安装（Ubuntu/Debian）：**
```bash
# 安装 MongoDB 4.4 (官方推荐)
wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list

sudo apt-get update
sudo apt-get install -y mongodb-org
```

**启动 MongoDB：**
```bash
sudo systemctl start mongod
sudo systemctl enable mongod
sudo systemctl status mongod
```

- [ ] **Step 3: 验证 MongoDB 连接**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

python -c "
from pymongo import MongoClient
from app.config import Config

client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=5000)
client.admin.command('ping')
print('MongoDB connected successfully!')

db = client[Config.MONGODB_DB]
print('Database:', Config.MONGODB_DB)
"
```

- [ ] **Step 4: 检查初始数据初始化**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

python -c "
from app.models.db import db, INIT_DATA, list_collections, get_collection_count

if db is not None:
    print('MongoDB collections:', list_collections())
    for coll in list_collections():
        print(f'  {coll}: {get_collection_count(coll)} documents')
else:
    print('MongoDB not available')
"
```

---

### Task 5: 安装配置前端环境 (Node.js 16 + UI)

**参考文档:**
- `docs/ui_dev_guide.md`

**Files:**
- 检查: `/workspace/bk_cmdb_py/ui/` (前端项目目录)
- 参考: `/workspace/bk_cmdb_py/ui/package.json`

- [ ] **Step 1: 检查 Node.js 和 npm 版本**

```bash
# 检查已安装的 Node.js 版本
node --version 2>/dev/null || echo "Node.js not installed"
npm --version 2>/dev/null || echo "npm not installed"

# 检查是否使用 nvm
which nvm || echo "nvm not installed"
nvm --version 2>/dev/null || echo "nvm not available"
```

- [ ] **Step 2: 安装 Node.js 16 (必须使用此版本)**

```bash
# 安装 nvm (如果未安装)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"

# 安装并使用 Node.js 16
nvm install 16
nvm use 16

# 验证安装
node --version  # 应输出: v16.x.x
npm --version   # 应输出: 8.x.x
```

- [ ] **Step 3: 检查前端项目目录**

```bash
cd /workspace/bk_cmdb_py

# 检查 UI 目录是否存在
ls -la ui/

# 检查 package.json
cat ui/package.json | head -20
```

- [ ] **Step 4: 配置前端项目**

**配置 API 代理 (修改 ui/builder/config/index.js)：**

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
      target: 'http://localhost:8080/',  // Python 后端端口
      pathRewrite: {
        '^/proxy': ''
      }
    }
  },
  // 开发服务器端口
  port: 9093,
}
```

**配置 historyApiFallback (修改 ui/builder/webpack/devserver.js)：**

```javascript
historyApiFallback: {
  disableDotRule: false,
  rewrites: [
    { from: /^\/.*$/, to: '/index.html' },
  ],
},
```

- [ ] **Step 5: 安装前端依赖**

```bash
cd /workspace/bk_cmdb_py/ui

# 设置 Node.js 16
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 16

# 安装项目依赖
npm install

# 安装额外依赖（修复 babel runtime 问题）
npm install @babel/runtime --save
```

- [ ] **Step 6: 验证前端依赖安装**

```bash
cd /workspace/bk_cmdb_py/ui

# 检查关键目录
ls -la node_modules/ | head -10

# 检查 package.json 中的依赖
npm list --depth=0
```

预期输出应包含：
```
vue@2.x.x
webpack@4.x.x
@babel/core
...
```

- [ ] **Step 7: 测试启动前端开发服务器**

```bash
cd /workspace/bk_cmdb_py/ui

# 设置 Node.js 16
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 16

# 后台启动开发服务器
npm run dev &
sleep 5

# 验证服务器启动
curl -s http://127.0.0.1:9093/ | head -20
```

- [ ] **Step 8: 验证前端页面访问**

```bash
# 检查首页 HTML
curl -s http://127.0.0.1:9093/ | head -20

# 检查 JS 文件可访问
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9093/js/app.*.js

# 检查静态资源
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9093/static/favicon.ico
```

预期输出：
- 首页返回 200
- JS 文件返回 200
- 静态资源返回 200

- [ ] **Step 9: 常用前端命令**

```bash
cd /workspace/bk_cmdb_py/ui

# 设置 Node 版本 (每次新终端都需要)
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

---

### Task 6: 验证完整开发环境启动

**Files:**
- 启动文件: `app.py`
- 数据库模型: `app/models/db.py`, `app/models/pglite.py`

- [ ] **Step 1: 测试现有启动脚本（如果有）**

```bash
cd /workspace/bk_cmdb_py
ls -la | grep -E "(start|app)"
cat start_services.sh 2>/dev/null || echo "No start script found"
```

- [ ] **Step 2: 直接运行 Flask 应用（背景启动测试）**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

# 测试导入
python -c "
import app
print('App imported successfully')
"

# 如果有启动脚本，运行它
# bash start_services.sh &

# 或者直接用 Flask 启动
# FLASK_APP=app.py flask run --host=0.0.0.0 --port=5000 &
# sleep 3
# curl http://localhost:5000/
```

- [ ] **Step 3: 验证 py-pglite 连接与初始化**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

python -c "
from app.models.pglite import get_pglite_connection, list_tables, get_table_count
conn = get_pglite_connection()
print('py-pglite tables:', list_tables())
for tbl in list_tables():
    print(f'  {tbl}: {get_table_count(tbl)} rows')
"
```

---

### Task 7: 生成环境验证脚本与文档

**Files:**
- 创建: `scripts/verify-env.sh` (可选)
- 更新: `README.md` (如果存在)

- [ ] **Step 1: 创建环境检查脚本**

```bash
mkdir -p /workspace/bk_cmdb_py/scripts

cat > /workspace/bk_cmdb_py/scripts/verify-env.sh << 'EOF'
#!/bin/bash
set -e

echo "=== BK-CMDB Python Backend - Environment Verification ==="
echo

# 1. Python
echo "[1] Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo "Python version: $PYTHON_VERSION"
    
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
        echo "✓ Python version OK"
    else
        echo "⚠ Python 3.10+ recommended"
    fi
else
    echo "✗ Python3 not found"
fi
echo

# 2. Virtualenv
echo "[2] Checking virtual environment..."
if [ -d "venv" ]; then
    echo "✓ Virtualenv directory found"
else
    echo "✗ Virtualenv not found"
fi

if [ -n "$VIRTUAL_ENV" ]; then
    echo "✓ Virtualenv activated: $VIRTUAL_ENV"
else
    echo "⚠ Virtualenv not activated"
fi
echo

# 3. Dependencies
echo "[3] Checking pip dependencies..."
if [ -f "requirements.txt" ]; then
    echo "Requirements file found"
else
    echo "✗ requirements.txt not found"
fi

if [ -n "$VIRTUAL_ENV" ]; then
    echo "Installed packages (selected):"
    pip list | grep -E "(Flask|pymongo|mongoengine|SQLAlchemy|py-pglite|Flask-)" || true
fi
echo

# 4. MongoDB
echo "[4] Checking MongoDB..."
if command -v mongod &> /dev/null; then
    MONGODB_VERSION=$(mongod --version | head -1 | awk '{print $3}' | cut -d, -f1)
    echo "MongoDB version: $MONGODB_VERSION"
else
    echo "✗ MongoDB not installed"
fi

if pgrep -x "mongod" > /dev/null; then
    echo "✓ MongoDB is running"
    
    if python3 -c "
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
    print('✓ Connection test successful')
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; then
        echo "✓ Connection test passed"
    else
        echo "✗ Connection test failed"
    fi
else
    echo "✗ MongoDB is not running"
fi
echo

echo "=== Verification complete ==="
EOF

chmod +x /workspace/bk_cmdb_py/scripts/verify-env.sh
```

- [ ] **Step 2: 创建前端环境检查脚本**

```bash
cat >> /workspace/bk_cmdb_py/scripts/verify-env.sh << 'EOF'

echo
echo "=== BK-CMDB Frontend - Environment Verification ==="
echo

# 5. Node.js
echo "[5] Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Node.js version: $NODE_VERSION"
    
    # 检查是否为 Node 16
    if [[ $NODE_VERSION == v16* ]]; then
        echo "✓ Node.js 16 correct version"
    else
        echo "⚠ Node.js 16 required (recommended)"
    fi
else
    echo "✗ Node.js not installed"
fi

# 6. Frontend
echo "[6] Checking Frontend..."
if [ -d "ui" ]; then
    echo "✓ UI directory found"
else
    echo "✗ UI directory not found"
fi

if [ -f "ui/package.json" ]; then
    echo "✓ package.json found"
else
    echo "✗ package.json not found"
fi

if [ -d "ui/node_modules" ]; then
    echo "✓ node_modules installed"
else
    echo "⚠ node_modules not installed (run: cd ui && npm install)"
fi

# 7. Frontend Dev Server
echo "[7] Checking Frontend Dev Server..."
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9093/ 2>/dev/null | grep -q "200"; then
    echo "✓ Frontend dev server is running at http://127.0.0.1:9093"
else
    echo "⚠ Frontend dev server not running (run: cd ui && npm run dev)"
fi

echo
echo "=== Frontend Verification complete ==="
EOF
```

- [ ] **Step 3: 运行验证脚本**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

./scripts/verify-env.sh
```

- [ ] **Step 4: 最终验证 - 运行完整初始化**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

python -c "
from app.models.db import init_mock_data, list_collections, get_collection_count
from app.models.pglite import init_pglite_schema, init_pglite_data, list_tables, get_table_count

print('=== Initializing MongoDB ===')
init_mock_data()
print('Collections:', list_collections())
for coll in list_collections():
    print(f'  {coll}: {get_collection_count(coll)}')

print('\n=== Initializing py-pglite ===')
init_pglite_schema()
init_pglite_data()
print('Tables:', list_tables())
for tbl in list_tables():
    print(f'  {tbl}: {get_table_count(tbl)}')

print('\n=== Environment fully initialized! ===')
"
```

---

## 完成检查清单

在完成 TOP1 后，确认：

- [ ] Python 3.10+ 已安装并运行在虚拟环境中
- [ ] `requirements.txt` 中所有依赖已正确安装
- [ ] MongoDB 4.4+ 已安装并运行在 `localhost:27017`
- [ ] Flask 应用可以正常启动
- [ ] MongoDB 连接正常且有初始化数据
- [ ] py-pglite 连接正常且有初始化表结构
- [ ] Node.js 16 已安装
- [ ] 前端依赖已安装
- [ ] 前端开发服务器可以启动在 `localhost:9093`

---

## 下一步

完成 TOP1 后，继续执行 [TOP2: 数据库结构初始化](./top2-db-init.md)
