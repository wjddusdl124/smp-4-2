"""11.11 발표용 사건 판정(기업 1104 기준 v1.1).
육지 급등: smp_land >= 같은 시각 직전 28일 중앙값 + 20 (그날 제외), 연속 시간 = 1구간
육지 급락: 11~15시 smp_land < 30, 연속 = 1구간
제주 급락: smp_jeju == 0 (<=0), 연속 = 1구간
구간은 하루 안에서만 이어 붙입니다(같은 날 끊기면 2구간)."""
import os, pandas as pd, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "data", "processed", "smp_dataset_hourly.csv")

def load():
    d = pd.read_csv(DATA, encoding="utf-8-sig", low_memory=False, parse_dates=["date"])
    d = d.dropna(subset=["smp_land"]).sort_values(["date", "hour_n"]).reset_index(drop=True)
    d["holiday"] = ((d.is_weekend == 1) | (d.is_holiday == 1)).astype(int)
    return d

def med28(d, col="smp_land"):
    w = d.pivot(index="date", columns="hour_n", values=col)
    w = w.reindex(pd.date_range(w.index.min(), w.index.max()))
    m = w.shift(1).rolling(28, min_periods=25).median()  # 7/31 결측 1일 허용
    m[m.index < "2021-01-29"] = np.nan
    s = m.stack(future_stack=True).rename("med28").reset_index().rename(columns={"level_0": "date"})
    return d.merge(s, on=["date", "hour_n"], how="left")

def flags(d):
    d = d.copy()
    d["ev_spike"] = (d.smp_land >= d.med28 + 20) & d.med28.notna()
    d["ev_drop"] = d.hour_n.between(11, 15) & (d.smp_land < 30)
    d["ev_jeju"] = d.smp_jeju <= 0
    return d

def segments(d, col):
    """col(bool) 연속 구간 → DataFrame(date, start, end, hours, holiday)."""
    out = []
    for dt, g in d[d[col]].groupby("date"):
        h = g.hour_n.values
        br = np.where(np.diff(h) != 1)[0]
        starts = np.r_[0, br + 1]; ends = np.r_[br, len(h) - 1]
        for s, e in zip(starts, ends):
            out.append((dt, h[s], h[e], h[e] - h[s] + 1, int(g.holiday.iloc[0])))
    return pd.DataFrame(out, columns=["date", "start", "end", "hours", "holiday"])

def eval_days(d):
    return d[d.med28.notna()]

if __name__ == "__main__":
    d = flags(med28(load()))
    d = eval_days(d)
    print("판정일", d.date.nunique(), d.date.min().date(), d.date.max().date())
    rows = []
    for col, nm in [("ev_spike", "육지급등"), ("ev_drop", "육지급락"), ("ev_jeju", "제주0원")]:
        s = segments(d, col); s["year"] = s.date.dt.year
        t = s.groupby(["year", "holiday"]).size().unstack(fill_value=0)
        for y in t.index:
            rows.append((y, nm, f"{t.loc[y].get(1,0)} / {t.loc[y].get(0,0)}"))
        if col == "ev_spike":
            print("급등 구간 있는 날 비율", round(s.date.nunique() / d.date.nunique() * 100, 1))
    r = pd.DataFrame(rows, columns=["연도", "사건", "휴일/평일"]).pivot(index="연도", columns="사건", values="휴일/평일")
    print(r.to_string())
