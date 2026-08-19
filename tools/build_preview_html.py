"""Build a static HTML twin of the Streamlit app from the demo outputs."""
import base64, os, re
import pandas as pd

OUT = "/home/user/jaypretium/outputs"
CSV = os.path.join(OUT, "csv")


def img64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def table(csv, rnd=3, idx=0):
    df = pd.read_csv(os.path.join(CSV, csv), index_col=idx)
    return df.round(rnd).to_html(classes="tbl", border=0, na_rep="")


def md_to_html(md):
    html = []
    for line in md.splitlines():
        if line.startswith("## "):
            html.append(f"<h3>{line[3:]}</h3>")
        elif line.startswith("> "):
            html.append(f"<div class='warn'>{line[2:]}</div>")
        elif line.startswith("- "):
            html.append(f"<li>{line[2:]}</li>")
        elif line.strip():
            html.append(f"<p>{line}</p>")
    txt = "\n".join(html)
    txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
    return txt


answers = md_to_html(open(os.path.join(OUT, "synthetic_ANSWERS_Q1-Q10.md")).read())

tabs = {
    "Overview / Q1–Q10": f"<div class='ans'>{answers}</div>",
    "Factor ranking": f"<h3>Factor ranking (Long-Short, net)</h3>{table('synthetic_ranking.csv')}"
                      f"<img src='{img64(OUT+'/synthetic_sharpe_ranking.png')}'>"
                      f"<img src='{img64(OUT+'/synthetic_ls_equity.png')}'>",
    "Seasonality": f"<h3>Calendar-month seasonality — OP_1M</h3>"
                   f"<img src='{img64(OUT+'/synthetic_seasonality_OP_1M.png')}'>"
                   f"<h4>Season (Feb/May/Aug/Nov) vs other months</h4>{table('synthetic_season_vs_other.csv')}",
    "1M vs 3M": f"<h3>1M vs 3M revision (season months)</h3>{table('synthetic_horizon_compare_season.csv', idx=None)}",
    "Costs": f"<h3>Cost / borrow sensitivity</h3>{table('synthetic_cost_sensitivity.csv', idx=None)}",
    "Event-time & FM": f"<h3>Event-time (post-earnings drift by revision group)</h3>{table('synthetic_event_time.csv', idx=None)}"
                       f"<h3>Fama-MacBeth (next-month return on revision + controls)</h3>{table('synthetic_fama_macbeth.csv')}"
                       f"<h3>Sector-neutral check</h3>{table('synthetic_sector_neutral.csv')}",
    "Sub-periods": f"<h3>Sub-period robustness (LS Sharpe)</h3>{table('synthetic_subperiods.csv')}",
}

_btn = []
for i, name in enumerate(tabs):
    cls = "tab active" if i == 0 else "tab"
    _btn.append(f"<button class='{cls}' onclick='show({i})'>{name}</button>")
btns = "".join(_btn)

_pane = []
for i, (name, html) in enumerate(tabs.items()):
    disp = "block" if i == 0 else "none"
    _pane.append(f"<div class='pane' id='p{i}' style='display:{disp}'>{html}</div>")
panes = "".join(_pane)

HTML = f"""<!doctype html><html><head><meta charset='utf-8'><title>Korea Earnings-Revision Backtest</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#1a1a1a}}
.layout{{display:flex;min-height:100vh}}
.side{{width:300px;background:#f0f2f6;padding:20px;flex:0 0 300px;border-right:1px solid #e0e0e0}}
.side h2{{font-size:18px;margin:0 0 16px}}
.ctl{{margin:14px 0}} .ctl label{{display:block;font-size:13px;font-weight:600;margin-bottom:4px}}
.ctl .val{{font-size:12px;color:#555}}
.pill{{display:inline-block;background:#fff;border:1px solid #ccc;border-radius:6px;padding:5px 10px;font-size:13px;margin:2px 3px 2px 0}}
.pill.sel{{background:#ff4b4b;color:#fff;border-color:#ff4b4b}}
.slider{{height:6px;background:#ddd;border-radius:3px;position:relative;margin:8px 0}}
.slider .fill{{position:absolute;height:6px;background:#ff4b4b;border-radius:3px}}
.slider .knob{{position:absolute;top:-4px;width:14px;height:14px;border-radius:50%;background:#ff4b4b}}
.main{{flex:1;padding:24px 34px;overflow:auto}}
h1{{font-size:26px;margin:0 0 6px}} h3{{margin:18px 0 8px;font-size:17px}} h4{{margin:14px 0 6px;font-size:14px;color:#444}}
.warn{{background:#fff3cd;border-left:4px solid #ffc107;padding:10px 14px;border-radius:4px;margin:10px 0;font-size:13px}}
.tabs{{border-bottom:2px solid #eee;margin:16px 0}} .tab{{background:none;border:none;padding:10px 14px;font-size:14px;cursor:pointer;color:#555;border-bottom:2px solid transparent;margin-bottom:-2px}}
.tab.active{{color:#ff4b4b;border-bottom:2px solid #ff4b4b;font-weight:600}}
table.tbl{{border-collapse:collapse;font-size:12px;margin:8px 0;width:100%}}
table.tbl th,table.tbl td{{border:1px solid #eee;padding:5px 8px;text-align:right}} table.tbl th{{background:#fafafa}}
table.tbl td:first-child,table.tbl th:first-child{{text-align:left;font-weight:600}}
img{{max-width:820px;width:100%;margin:10px 0;border:1px solid #eee;border-radius:6px}}
.ans p,.ans li{{font-size:13px;line-height:1.5;margin:5px 0}} .ans li{{margin-left:18px}}
.badge{{display:inline-block;background:#e8f0fe;color:#1a56db;font-size:11px;padding:3px 8px;border-radius:10px;margin-left:8px}}
</style></head><body>
<div class='layout'>
  <div class='side'>
    <h2>⚙️ Settings</h2>
    <div class='ctl'><label>Data source</label>
      <span class='pill sel'>Demo (synthetic)</span><span class='pill'>Upload real CSVs</span></div>
    <div class='ctl'><label># synthetic tickers <span class='val'>160</span></label>
      <div class='slider'><div class='fill' style='width:38%'></div><div class='knob' style='left:36%'></div></div></div>
    <div class='ctl'><label>Universe</label>
      <span class='pill sel'>ALL</span><span class='pill'>TOP500</span><span class='pill'>KOSPI200</span></div>
    <div class='ctl'><label>Weighting</label>
      <span class='pill sel'>equal</span><span class='pill'>mktcap</span></div>
    <div class='ctl'><label>Drop illiquid bottom % <span class='val'>20%</span></label>
      <div class='slider'><div class='fill' style='width:50%'></div><div class='knob' style='left:48%'></div></div></div>
    <div class='ctl'><label>Long cost (bp, one-way) <span class='val'>20</span></label>
      <div class='slider'><div class='fill' style='width:40%'></div><div class='knob' style='left:38%'></div></div></div>
    <div class='ctl'><label>Borrow (annual) <span class='val'>5%</span></label>
      <div class='slider'><div class='fill' style='width:50%'></div><div class='knob' style='left:48%'></div></div></div>
    <div class='ctl'><button class='pill' style='background:#ff4b4b;color:#fff;border:none'>⬇️ Download results (xlsx)</button></div>
  </div>
  <div class='main'>
    <h1>🇰🇷 Korea Earnings-Revision Factor — Backtest <span class='badge'>preview of Streamlit app</span></h1>
    <div class='warn'>SYNTHETIC DEMO — numbers are a plumbing test, not findings about Korea. Upload a real point-in-time consensus panel for real results.</div>
    <div class='tabs'>{btns}</div>
    {panes}
  </div>
</div>
<script>
function show(i){{document.querySelectorAll('.pane').forEach((p,j)=>p.style.display=(i==j?'block':'none'));
document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('active',i==j));}}
</script>
</body></html>"""

path = os.path.join(OUT, "app_preview.html")
open(path, "w").write(HTML)
print("wrote", path, len(HTML), "bytes")
