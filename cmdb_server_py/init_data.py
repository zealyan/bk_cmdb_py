#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.db import init_mock_data
from app.auth.policies import init_admin_super_permission, init_default_policies

print("正在初始化 MongoDB 数据...")
init_mock_data()

print("正在初始化权限策略...")
init_admin_super_permission()
init_default_policies()

print("数据初始化完成！")
