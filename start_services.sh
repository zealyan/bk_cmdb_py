#!/bin/bash

# BK-CMDB服务启动脚本
echo "====================================="
echo "BK-CMDB 服务启动"
echo "====================================="
echo ""

# 切换到项目目录
cd /workspace/bk_cmdb_py

echo "[1/3] 检查Python后端服务..."
if ! pgrep -f "python.*app\.py" > /dev/null; then
    echo "启动Python后端服务..."
    nohup python app.py > backend.log 2>&1 &
    echo "后端服务已启动，PID: $!"
else
    echo "后端服务已在运行"
fi

echo ""
echo "[2/3] 检查UI前端服务..."
UI_DIR="/workspace/bk_cmdb_py/ui"
cd "$UI_DIR"

if ! pgrep -f "node.*dev\.js" > /dev/null; then
    echo "启动UI前端服务..."
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use 16
    nohup npm run dev > ui.log 2>&1 &
    echo "UI服务已启动，PID: $!"
else
    echo "UI服务已在运行"
fi

cd /workspace/bk_cmdb_py

echo ""
echo "[3/3] 服务状态检查..."
echo ""
echo "Python后端: http://127.0.0.1:8080"
echo "前端UI:     http://127.0.0.1:9093"
echo ""
echo "测试账号: admin / admin"
echo "           tom / tom123"
echo ""
echo "====================================="
