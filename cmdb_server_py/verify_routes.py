#!/usr/bin/env python3
"""验证后端各核心路由在 MongoDB 恢复后是否正常返回数据。"""
import requests

BASE = "http://127.0.0.1:3000"  # app.py
UI = "http://127.0.0.1:8085"     # ui_server

s = requests.Session()
results = []


def check(name, method, url, **kw):
    try:
        r = s.request(method, url, timeout=15, **kw)
        try:
            body = r.json()
        except Exception:
            body = {"_raw": r.text[:200]}
        data = body.get("data")
        bk_code = body.get("bk_error_code")
        ok = r.status_code == 200 and bk_code == 0 and data is not None
        n = len(data) if isinstance(data, (list, dict)) else data
        info = f"HTTP {r.status_code} bk_code={bk_code} data={n}"
        results.append((name, ok, info))
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {info}")
    except Exception as e:
        results.append((name, False, f"EXC {e}"))
        print(f"[FAIL] {name}: EXC {e}")


# 健康检查
check("health", "GET", f"{BASE}/health")
# 登录
try:
    r = s.post(f"{BASE}/api/v3/user/auth",
               json={"bk_username": "admin", "bk_password": "admin"}, timeout=15)
    j = r.json()
    tok = (j.get("data") or {}).get("bk_token")
    print(f"\n[login] HTTP {r.status_code} bk_code={j.get('bk_error_code')} token={'YES' if tok else 'NO'}\n")
except Exception as e:
    print(f"[login] EXC {e}\n")

# 模型 / 资源 / 主机 / 业务（真实路径）
check("classificationobject", "POST", f"{BASE}/api/v3/find/classificationobject", json={})
check("object_list", "POST", f"{BASE}/api/v3/find/object", json={})
check("host_search", "POST", f"{BASE}/api/v3/hosts/search",
      json={"condition": [], "page": {"start": 0, "limit": 5, "sort": "bk_host_id"}})
check("biz_search_web", "POST", f"{BASE}/api/v3/biz/search/web",
      json={"condition": {}, "page": {"start": 0, "limit": 10, "sort": "bk_biz_id"}})

# 经 UI 反代（浏览器真实路径）
check("ui_classification", "POST", f"{UI}/api/v3/find/classificationobject", json={})
check("ui_host_search", "POST", f"{UI}/api/v3/hosts/search",
      json={"condition": [], "page": {"start": 0, "limit": 5, "sort": "bk_host_id"}})

ok_n = sum(1 for _, ok, _ in results if ok)
print(f"\n=== 汇总: 通过 {ok_n}/{len(results)} ===")
