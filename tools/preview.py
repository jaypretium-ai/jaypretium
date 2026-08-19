"""Start the Streamlit app, screenshot every tab, then shut it down — one process."""
import os, subprocess, time, urllib.request, sys
from playwright.sync_api import sync_playwright

PORT = 8899
URL = f"http://localhost:{PORT}"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
OUT = "/home/user/jaypretium/outputs/shots"
os.makedirs(OUT, exist_ok=True)

TABS = [
    ("Overview / Q1–Q10", "01_overview.png", "Q1."),
    ("Factor ranking", "02_ranking.png", "Factor ranking (Long-Short"),
    ("Seasonality", "03_seasonality.png", "Season (Feb/May/Aug/Nov)"),
    ("1M vs 3M", "04_1m_vs_3m.png", "1M vs 3M revision"),
    ("Costs", "05_costs.png", "Cost / borrow sensitivity"),
    ("Event-time & FM", "06_eventtime_fm.png", "Fama-MacBeth"),
    ("Long candidates", "07_long_candidates.png", "Latest top-20"),
]

proc = subprocess.Popen(
    ["streamlit", "run", "app.py", "--server.headless", "true",
     "--server.port", str(PORT), "--browser.gatherUsageStats", "false"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/home/user/jaypretium",
)
try:
    ready = False
    for _ in range(40):
        try:
            urllib.request.urlopen(f"{URL}/healthz", timeout=2)
            ready = True
            break
        except Exception:
            time.sleep(1)
    if not ready:
        print("app did not start"); sys.exit(1)
    print("app up")

    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = br.new_page(viewport={"width": 1500, "height": 1000})
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_selector("text=Korea Earnings-Revision Factor", timeout=90000)
        pg.wait_for_selector("text=Q1.", timeout=120000)
        pg.wait_for_timeout(1500)
        for name, fname, marker in TABS:
            try:
                if name != TABS[0][0]:
                    pg.get_by_role("tab", name=name).click()
                    pg.wait_for_timeout(400)
                    try:
                        pg.wait_for_selector(f"text={marker}", timeout=15000)
                    except Exception:
                        pass
                    pg.wait_for_timeout(700)
                pg.screenshot(path=os.path.join(OUT, fname), full_page=True)
                print("shot:", fname)
            except Exception as e:
                print("FAIL", name, repr(e)[:150])
        br.close()
    print("DONE")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
