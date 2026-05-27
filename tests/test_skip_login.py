
import sys
sys.path.insert(0, '/workspace/bk_cmdb_py')

from app.config import Config

print("=== Skip Login 配置测试 ===")
print(f"SKIP_LOGIN: {Config.SKIP_LOGIN} (类型: {type(Config.SKIP_LOGIN)})")
print(f"SKIP_LOGIN_USER: {Config.SKIP_LOGIN_USER}")

import os
print(f"\n=== 环境变量 ===")
print(f"SKIP_LOGIN env: {os.environ.get('SKIP_LOGIN')}")
print(f"SKIP_LOGIN_USER env: {os.environ.get('SKIP_LOGIN_USER')}")
