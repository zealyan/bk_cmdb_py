#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

# 测试在没有 Flask web server 情况下运行登录逻辑
from flask import request
from werkzeug.test import Client
from werkzeug.wrappers import Response

client = Client(app, Response)

print("--- 测试 1: user/auth ---")
response = client.post(
    '/user/auth',
    json={"bk_username": "admin", "bk_password": "admin"}
)
print(f"状态码: {response.status_code}")
print(f"响应: {response.data.decode()}")

print("\n--- 测试 2: api/v3/user/auth ---")
response = client.post(
    '/api/v3/user/auth',
    json={"bk_username": "admin", "bk_password": "admin"}
)
print(f"状态码: {response.status_code}")
print(f"响应: {response.data.decode()}")
