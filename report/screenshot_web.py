# -*- coding: utf-8 -*-
"""Chụp ảnh thật giao diện web demo bằng Playwright (headless Chromium)."""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

FIGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(FIGS, exist_ok=True)
URL = "http://localhost:8000"
Q = "Điều kiện để cá nhân được cấp giấy phép hành nghề khám bệnh, chữa bệnh?"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1024, "height": 1500}, device_scale_factor=2)
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_selector(".chip", timeout=30000)   # React đã render màn hình chào
        pg.wait_for_timeout(1200)
        # 1) Trang chủ (màn hình chào + câu hỏi mẫu)
        pg.screenshot(path=os.path.join(FIGS, "web_home.png"))
        print("Đã chụp web_home.png")
        # 2) Gửi một câu hỏi thật
        pg.fill("textarea", Q)
        pg.click("button.send")
        print("Đã gửi câu hỏi, chờ câu trả lời (tối đa 240s)...")
        pg.wait_for_selector(".srctoggle", timeout=240000)  # có nguồn = đã trả lời
        pg.wait_for_timeout(800)
        pg.click(".srctoggle")  # mở danh sách nguồn
        pg.wait_for_timeout(800)
        pg.screenshot(path=os.path.join(FIGS, "web_result.png"), full_page=True)
        print("Đã chụp web_result.png")
        b.close()
    print("XONG")


if __name__ == "__main__":
    main()
