import sys, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8085"
CHROME = "/usr/bin/chromium"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True,
                                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("console", lambda m: None)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        print("[1] 打开首页，预期跳登录")
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)
        print("    URL =", page.url)

        # 登录：bk-cmdb 登录表单
        try:
            page.wait_for_selector("input", timeout=8000)
            # 尝试常见选择器
            user = page.query_selector('input[name="username"]') or page.query_selector('input[placeholder*="用户名"]') or page.query_selector('input[type="text"]')
            pwd  = page.query_selector('input[name="password"]') or page.query_selector('input[placeholder*="密码"]') or page.query_selector('input[type="password"]')
            if user and pwd:
                user.fill("admin")
                pwd.fill("admin")
                btn = page.query_selector('button[type="submit"]') or page.query_selector('.bk-button')
                if btn:
                    btn.click()
                print("    已填写 admin/admin 并提交")
            else:
                print("    [WARN] 未找到登录输入框")
        except Exception as e:
            print("    [登录异常]", e)

        # 等待回到首页
        page.wait_for_timeout(2500)
        print("    URL after login =", page.url)

        print("[2] 进入业务拓扑 #/business/1/index")
        page.goto(BASE + "/#/business/1/index", wait_until="domcontentloaded", timeout=20000)
        # 等待业务名“资源池”出现（拓扑节点渲染）
        try:
            page.wait_for_function("document.body.innerText.indexOf('资源池') >= 0", timeout=15000)
            print("    业务拓扑已渲染（出现 '资源池'）")
        except Exception as e:
            print("    [WARN] 未检测到 '资源池':", e)
        # 再等计数 API 加载完成
        page.wait_for_timeout(5000)

        # 提取拓扑区域文本
        text = page.evaluate("document.querySelector('main') ? document.querySelector('main').innerText : document.body.innerText")
        print("\n===== 业务拓扑区域文本（节选）=====")
        # 只打印含关键节点名/计数的行
        for line in text.splitlines():
            s = line.strip()
            if s and (any(k in s for k in ["资源池","空闲机","业务","集群","模块","主机","5","0"]) and len(s) < 60):
                print("   |", s)

        # 截图
        shot = "/workspace/bk_cmdb_py/topology_verify.png"
        page.screenshot(path=shot, full_page=False)
        print("\n[3] 截图已保存:", shot)

        if errors:
            print("\n[页面JS错误]", errors[:5])
        browser.close()

if __name__ == "__main__":
    main()
