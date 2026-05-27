#!/bin/bash

export SKIP_LOGIN=true
export SKIP_LOGIN_USER=admin

cd /workspace

echo "================================"
echo "BK-CMDB Python Backend"
echo "Skip Login Mode: ENABLED"
echo "Auto Login User: $SKIP_LOGIN_USER"
echo "================================"
echo ""

python app.py
