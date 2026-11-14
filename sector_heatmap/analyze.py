import pickle, pandas as pd, numpy as np
from universe import U
names,px=pickle.load(open("px.pkl","rb"))
px=px.sort_index()
d=px.pct_change(fill_method=None)
bad=(d.abs()>0.45)&(d.columns!="x")
print("suspicious daily jumps:",[(c,str(i.date()),round(d.loc[i,c],2)) for i,c in zip(*np.where(bad)) for i,c in [(d.index[i],d.columns[c])]][:20])
m=px.resample("ME").last()
mr=m.pct_change(fill_method=None)
mr=mr.iloc[1:]  # first partial month dropped (2014-08)
# equal-weight basket monthly returns
S={}
for (g,s),cs in U.items(): S[(g,s)]=mr[cs].mean(axis=1,skipna=True)
S=pd.DataFrame(S); S.columns=pd.MultiIndex.from_tuples(S.columns)
k=mr["KOSPI"]; q=mr["KOSDAQ"]
pickle.dump((S,k,q,mr),open("ret.pkl","wb"))
hist=S[(S.index.year>=2014)&(S.index.year<=2025)]
out=[]
for col in S.columns:
    r=hist[col]
    row={"grp":col[0],"sec":col[1]}
    for mo,lab in [(11,"Nov"),(12,"Dec")]:
        x=r[r.index.month==mo].dropna(); ex=(x-k[x.index])
        row[f"{lab}_avg"]=x.mean()*100; row[f"{lab}_med"]=x.median()*100
        row[f"{lab}_xs"]=ex.mean()*100; row[f"{lab}_xshit"]=(ex>0).mean()*100; row[f"{lab}_n"]=len(x)
    # Nov+Dec compounded
    nd=[]
    for y in range(2014,2026):
        a=r.get(pd.Timestamp(f"{y}-11-30")); b=r.get(pd.Timestamp(f"{y}-12-31"))
        ka=k.get(pd.Timestamp(f"{y}-11-30")); kb=k.get(pd.Timestamp(f"{y}-12-31"))
        if pd.notna(a) and pd.notna(b): nd.append(((1+a)*(1+b)-1-((1+ka)*(1+kb)-1))*100)
    row["ND_xs"]=np.mean(nd); row["ND_xshit"]=np.mean(np.array(nd)>0)*100
    # 2026 actual
    row["Oct26"]=S[col].get(pd.Timestamp("2026-10-31"))*100
    row["NovMTD26"]=S[col].get(pd.Timestamp("2026-11-30"))*100
    y=S[col]["2026"]; row["YTD26"]=((1+y).prod()-1)*100
    out.append(row)
T=pd.DataFrame(out).set_index("sec")
pd.set_option("display.width",250); pd.set_option("display.max_columns",30)
kh=k[(k.index.year>=2014)&(k.index.year<=2025)]
print("KOSPI Nov avg %.1f hit %.0f | Dec avg %.1f hit %.0f"%(kh[kh.index.month==11].mean()*100,(kh[kh.index.month==11]>0).mean()*100,kh[kh.index.month==12].mean()*100,(kh[kh.index.month==12]>0).mean()*100))
print("KOSPI Oct26 %.1f NovMTD %.1f YTD %.1f"%(k["2026-10"].iloc[0]*100,k["2026-11"].iloc[0]*100,((1+k["2026"]).prod()-1)*100))
print("KOSDAQ Oct26 %.1f NovMTD %.1f YTD %.1f"%(q["2026-10"].iloc[0]*100,q["2026-11"].iloc[0]*100,((1+q["2026"]).prod()-1)*100))
T.to_csv("table.csv")
print(T.round(1).sort_values("ND_xs",ascending=False).to_string())
