"""Screenshot each tab of the static HTML twin."""
import os
from playwright.sync_api import sync_playwright

OUT = "/home/user/jaypretium/outputs/shots"
os.makedirs(OUT, exist_ok=True)
FILE = "file:///home/user/jaypretium/outputs/app_preview.html"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
TABS = ["01_overview", "02_ranking", "03_seasonality", "04_1m_vs_3m",
        "05_costs", "06_eventtime_fm", "07_subperiods"]

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
    pg = br.new_page(viewport={"width": 1400, "height": 950}, device_scale_factor=2)
    pg.goto(FILE, wait_until="networkidle")
    for i, name in enumerate(TABS):
        pg.evaluate(f"show({i})")
        pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(OUT, name + ".png"), full_page=True)
        print("shot", name)
    br.close()
print("DONE")
