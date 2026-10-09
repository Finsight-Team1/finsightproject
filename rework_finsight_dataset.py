"""Rework of synthetic_nigerian_sme_transactions.csv -> FinSight schema. All values MOCK (NGN)."""
import numpy as np, pandas as pd
from datetime import datetime, timedelta
rng = np.random.default_rng(7)
src = pd.read_csv("/mnt/user-data/uploads/synthetic_nigerian_sme_transactions.csv")

# 1) Fix SME identity: each SME gets ONE industry + ONE state (original had every SME in all industries/states)
inds = ["Retail","Hospitality","Fashion & Apparel","Agribusiness","Manufacturing","Tech Startups"]
states = ["Lagos","FCT Abuja","Kano","Rivers","Oyo","Anambra","Kaduna"]
smes = sorted(src.SME_ID.unique())
NAMES = {"Retail":["Ade Stores","Bola Mart","Mama Ngozi Provisions"],"Hospitality":["Sunrise Eatery","Chop Corner","Naija Bites Kitchen"],
 "Fashion & Apparel":["Zuri Fashion","Ankara Hub","Tola Boutique"],"Agribusiness":["Arewa Farms","Green Harvest","Delta Agro"],
 "Manufacturing":["Kings Fabrication","Alaba Metals","Ibadan Steelworks"],"Tech Startups":["Pixel Labs","CodeNest","Byte Bridge"]}
_loc=[0,1,2,3,4,5,6,0,1,2,3,4,5,6,0,1]
sme_tbl = {s:(NAMES[inds[i%6]][i//6], inds[i%6], states[_loc[i]]) for i,s in enumerate(smes)}

# 2) Industry-specific income/expense profiles: (income desc, exp [(desc,category,cp)], amt scale, channels weights)
P = {
 "Retail":[["POS sales","Customer transfer","Cash sales"],[("Inventory purchase","Inventory",["Honeywell Wholesale","Dangote Distributors"]),("Shop rent","Rent",["Landlord"]),("Electricity token","Utilities",["IKEDC"]),("Transport","Transport",["Dispatch Rider"])],(5e3,150e3)],
 "Hospitality":[["Room booking","Restaurant sales","Event hall payment"],[("Food supplies","Inventory",["Mile 12 Market","Foodco Suppliers"]),("Generator fuel","Utilities",["Fuel Station"]),("Staff wages","Salaries",["Staff Payroll"]),("Cleaning supplies","Maintenance",["CleanPro"])],(10e3,400e3)],
 "Fashion & Apparel":[["Online order payment","POS sales","Walk-in sales"],[("Fabric purchase","Inventory",["Balogun Market Supplier","Lagos Fabric Hub"]),("Social media ads","Marketing",["Meta Ads"]),("Courier fees","Transport",["GIG Logistics"]),("Tailor wages","Salaries",["Staff Payroll"])],(8e3,250e3)],
 "Agribusiness":[["Produce sale","Bulk grain order","Market sales"],[("Seed & fertiliser","Inventory",["AgroInputs Ltd"]),("Farm labour","Salaries",["Farm Workers"]),("Haulage","Transport",["Truck Haulage Co"]),("Irrigation fuel","Utilities",["Fuel Station"])],(15e3,600e3)],
 "Manufacturing":[["Customer order payment","Distributor payment","Cash sales"],[("Raw materials","Inventory",["Alaba Steel Depot","PlastCo Supply"]),("Factory electricity","Utilities",["Eko DisCo"]),("Machine repairs","Maintenance",["TechFix Engineers"]),("Staff wages","Salaries",["Staff Payroll"])],(30e3,800e3)],
 "Tech Startups":[["Client invoice payment","Subscription revenue","Project milestone"],[("Cloud hosting","Software",["AWS / Cloud Provider"]),("Contractor payment","Salaries",["Freelance Dev"]),("Internet / data","Utilities",["MTN Business"]),("Co-working rent","Rent",["Hub Landlord"])],(20e3,700e3)],
}
CUST = [f"Customer {c}" for c in "ABCDEFGHIJKLMNOP"]
pm_ok = ["Bank Transfer","POS","USSD","Cash"]

rows=[]
ts = pd.to_datetime(src.Timestamp)
for i,(r,t) in enumerate(zip(src.itertuples(), ts)):
    name, ind, st = sme_tbl[r.SME_ID]
    inc_d, exp_l, (lo,hi) = P[ind]
    is_inc = rng.random() < 0.62
    amt = float(np.clip(rng.lognormal(np.log((lo+hi)/4), 0.7), lo, hi))
    if is_inc:
        desc, cat, cp, typ = rng.choice(inc_d), "Sales", rng.choice(CUST), "income"
    else:
        d,cat,cps = exp_l[rng.integers(len(exp_l))]; desc, cp, typ = d, rng.choice(cps), "expense"; amt*=0.7
    pm = r.Payment_Method
    if cat in ("Rent","Salaries") : pm = "Bank Transfer"
    chan = "Online" if pm in ("USSD",) or (is_inc and "Online" in desc) else r.Channel
    rows.append([r.Transaction_ID, t, r.SME_ID, name, ind, st, round(amt,2), "NGN", typ, cat, desc, pm, chan, r.Status, cp, 0, ""])
df = pd.DataFrame(rows, columns=["transaction_id","datetime","sme_id","business_name","industry","location","amount","currency","type","category","description","payment_method","channel","status","counterparty","is_synthetic_anomaly","anomaly_type"])
# failed transactions: keep as-is but flag so metrics can exclude them
def tag(idx,k): df.loc[idx,["is_synthetic_anomaly","anomaly_type"]]=[1,k]
ok = df.index[df.status=="Successful"].to_numpy()
for i in rng.choice(ok,12,replace=False): df.loc[i,"amount"]=round(df.loc[i,"amount"]*rng.uniform(5,9),2); tag(i,"large_amount")
for i in rng.choice(ok,10,replace=False):
    df.loc[i,"datetime"]=df.loc[i,"datetime"].replace(hour=int(rng.integers(0,5))); tag(i,"odd_hour")
for i in rng.choice(df.index[(df.type=="expense")&(df.status=="Successful")],8,replace=False):
    df.loc[i,["amount","counterparty","payment_method","description"]]=[2000000.0,"Unknown Beneficiary","Bank Transfer","Transfer"]; tag(i,"round_amount_unknown_party")
# SME with burst of rapid repeat payments
b = df[(df.sme_id=="SME-104")&(df.type=="expense")&(df.status=="Successful")].sample(1,random_state=2).iloc[0]
burst=[]
for k in range(6):
    x=b.copy(); x["transaction_id"]=f"TXN-B{k+1:03d}"; x["datetime"]=b["datetime"]+timedelta(minutes=k+1); x["amount"]=45000.0; x["is_synthetic_anomaly"]=1; x["anomaly_type"]="rapid_repeat"; burst.append(x)
dups = df.sample(12,random_state=5).copy()
dups["datetime"]+=pd.to_timedelta(rng.integers(1,10,len(dups)),unit="m"); dups["is_synthetic_anomaly"]=1; dups["anomaly_type"]="duplicate_transaction"
dups.iloc[:6,dups.columns.get_loc("transaction_id")] = df.loc[dups.index[:6],"transaction_id"].values
dups.iloc[6:,dups.columns.get_loc("transaction_id")] = [f"TXN-D{i+1:03d}" for i in range(6)]
df = pd.concat([df,pd.DataFrame(burst),dups]).sort_values("datetime").reset_index(drop=True)
df.loc[df.sample(12,random_state=9).index,"counterparty"]=""   # missing values to test validation
df["date"]=df.datetime.dt.strftime("%Y-%m-%d"); df["time"]=df.datetime.dt.strftime("%H:%M:%S")
df["datetime"]=df.datetime.dt.strftime("%Y-%m-%d %H:%M:%S")
cols=["transaction_id","datetime","date","time","sme_id","business_name","industry","location","description","amount","currency","type","category","payment_method","channel","status","counterparty","is_synthetic_anomaly","anomaly_type"]
df[cols].to_csv("finsight_transactions_v2.csv",index=False)

# invoices for the 16 SMEs
inv=[];n=1;END=datetime(2026,9,30)
for s,(name,ind,st) in sme_tbl.items():
    for _ in range(12):
        idt=datetime(2026,1,1)+timedelta(days=int(rng.integers(0,260))); terms=int(rng.choice([7,14,30])); due=idt+timedelta(days=terms)
        amt=round(float(rng.uniform(*P[ind][2]))/500)*500; r=rng.random()
        if r<.55: paid,pd_=amt,due-timedelta(days=int(rng.integers(0,terms)))
        elif r<.75: paid,pd_=amt,due+timedelta(days=int(rng.integers(3,30)))
        elif r<.88: paid,pd_=round(amt*rng.uniform(.3,.7)/500)*500,due+timedelta(days=int(rng.integers(0,20)))
        else: paid,pd_=0,None
        if pd_ and pd_>END: paid,pd_=0,None
        inv.append([f"INV{n:04d}",s,name,str(rng.choice(CUST)),idt.date(),due.date(),amt,paid,pd_.date() if pd_ else "","paid" if paid>=amt else "partial" if paid>0 else "unpaid"]);n+=1
pd.DataFrame(inv,columns=["invoice_id","sme_id","business_name","customer","invoice_date","due_date","amount_due","amount_paid","payment_date","status"]).to_csv("finsight_invoices_v2.csv",index=False)
print(len(df), df.anomaly_type.value_counts().to_dict()); print(df.groupby("type").amount.sum().round(0).to_dict())
print(df.groupby("sme_id")[["industry","location"]].nunique().max().to_dict())
