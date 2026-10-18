"""给 portal mockup 截图：桌面 1440 宽、手机 390 宽，整页，冻结动画。

    python3 docs/mockups/shot.py docs/mockups/portal-a.html
    → docs/mockups/portal-a-desktop.png、docs/mockups/portal-a-mobile.png
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

FREEZE = "*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}"
MAX_DEVICE_PX = 16384   # Chrome 单张截图纹理上限


def main() -> None:
    page_path = Path(sys.argv[1]).resolve()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")   # 用本机 Chrome，免得下载 Playwright 自带浏览器
        for name, width, scale in (("desktop", 1440, 1), ("mobile", 390, 2)):
            while True:
                ctx = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=scale)
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("requestfailed", lambda r: errors.append(f"请求失败 {r.url}"))
                page.goto(page_path.as_uri(), wait_until="networkidle", timeout=30000)
                page.add_style_tag(content=FREEZE)
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(300)
                h = page.evaluate("document.documentElement.scrollHeight")
                # Chrome 整页截图超过 16384 设备像素后会把页面开头重复画进去（不报错），这时降到 1 倍重截
                if h * scale <= MAX_DEVICE_PX or scale == 1:
                    break
                ctx.close()
                scale = 1
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            out = page_path.with_name(f"{page_path.stem}-{name}.png")
            page.screenshot(path=str(out), full_page=True)
            note = f"，{scale} 倍图" + ("（超过截图上限，下半页可能重复）" if h * scale > MAX_DEVICE_PX else "")
            print(f"{out.name}: {width}x{h}{note}，横向溢出 {overflow}px" + (f"，错误 {errors}" if errors else ""))
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
