import os
import requests
import pandas as pd
from datetime import datetime, timedelta

EVDS_KEY = os.getenv("EVDS_API_KEY", "")
BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
HEADERS = {"key": EVDS_KEY}

import yaml

def load_series(groups=None):
    with open("config/evds_series.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    series = []
    for grp in (groups or ["core", "credit_rates"]):
        for key, s in cfg.get(grp, {}).items():
            series.append((key, s))
    return series, cfg


def fetch(code: str, start: str, end: str):
    url = f"{BASE_URL}/series={code}&startDate={start}&endDate={end}&type=json"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json().get("items", [])


def to_df(items: list, code: str):
    df = pd.DataFrame(items)
    if df.empty:
        return df
    col_dates = [c for c in df.columns if "tarih" in c.lower()]
    date_col = col_dates[0] if col_dates else None
    if date_col:
        fmt = "%Y-%m" if df[date_col].str.match(r"^\d{4}-\d{2}$").all() else "%d-%m-%Y"
        df[date_col] = pd.to_datetime(df[date_col], format=fmt, errors="coerce")
    val_cols = [c for c in df.columns if c not in (date_col, "UNIXTIME") and date_col and c != date_col]
    for c in val_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values(date_col) if date_col else df


def get_macro_summary(days_back=90):
    start = (datetime.now() - timedelta(days=days_back)).strftime("%d-%m-%Y")
    end = datetime.now().strftime("%d-%m-%Y")
    series_list, cfg = load_series()
    lines = [f"MAKRO VERI ({start} -> {end}):", ""]

    for key, s in series_list:
        code = s["code"]
        try:
            items = fetch(code, start, end)
            df = to_df(items, code)
            if df.empty:
                lines.append(f"  {s['name']}: veri yok")
                continue
            for val_col in [c for c in df.columns if c not in ("UNIXTIME",) and "tarih" not in c.lower()]:
                pass
            val_cols = [c for c in df.columns if c not in ("UNIXTIME",) and "tarih" not in c.lower()]
            if not val_cols:
                lines.append(f"  {s['name']}: değer sütunu bulunamadı")
                continue
            val_col = val_cols[0]
            son = df.iloc[-1]
            ilk = df.iloc[0]
            son_val = son[val_col]
            if pd.notna(son_val):
                degisim = ""
                ilk_val = ilk[val_col]
                if pd.notna(ilk_val) and ilk_val != 0:
                    pct = (son_val - ilk_val) / ilk_val * 100
                    degisim = f" ({pct:+.2f}% donem basi)"
                lines.append(f"  {s['name']}: {son_val:.4f}{degisim}")
            else:
                lines.append(f"  {s['name']}: NaN")
        except Exception as e:
            lines.append(f"  {s['name']}: HATA - {e}")

    return "\n".join(lines)


if __name__ == "__main__":
    print(get_macro_summary(days_back=60))
