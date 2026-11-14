import re, sys, json, time, urllib.request, pandas as pd
def naver(sym, tf="month", count=300):
    u=f"https://fchart.stock.naver.com/sise.nhn?symbol={sym}&timeframe={tf}&count={count}&requestType=0"
    for i in range(3):
        try:
            raw=urllib.request.urlopen(u,timeout=20).read().decode("euc-kr","ignore");break
        except Exception as e: time.sleep(2)
    name=re.search(r'name="([^"]*)"',raw); rows=re.findall(r'data="([^"]+)"',raw)
    s=pd.Series({pd.Timestamp(r.split("|")[0]):float(r.split("|")[4]) for r in rows},name=sym).sort_index()
    return (name.group(1) if name else sym), s
if __name__=="__main__":
    for s in sys.argv[1:]:
        n,x=naver(s); print(s,n,len(x),x.index.min().date() if len(x) else None, x.tail(2).to_dict())
