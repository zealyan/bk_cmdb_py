from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # 尝试访问首页
    page.goto('http://127.0.0.1:9092/', timeout=10000)
    page.wait_for_load_state('networkidle')
    
    # 获取页面标题和内容
    title = page.title()
    content = page.content()
    
    print(f"Page title: {title}")
    print(f"Page content length: {len(content)}")
    
    # 截图
    page.screenshot(path='/tmp/ui_test.png', full_page=True)
    print("Screenshot saved to /tmp/ui_test.png")
    
    # 打印前500个字符
    print("\nPage HTML preview:")
    print(content[:500] if content else "No content")
    
    browser.close()
