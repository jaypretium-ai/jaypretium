import pickle, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from fetch import naver
from universe import U
codes = sorted({c for v in U.values() for c in v} | {"KOSPI","KOSDAQ"})
def f(c):
    try: return c, naver(c,"day",3000)
    except Exception as e: return c, (None, None)
with ThreadPoolExecutor(8) as ex: res=dict(ex.map(f,codes))
names={c:r[0] for c,r in res.items()}
px=pd.concat({c:r[1] for c,r in res.items() if r[1] is not None and len(r[1])},axis=1)
pickle.dump((names,px),open("px.pkl","wb"))
miss=[c for c in codes if res[c][1] is None or not len(res[c][1])]
print("n",len(codes),"missing",miss)
for k,v in U.items(): print(k[1], [names.get(c) for c in v])
