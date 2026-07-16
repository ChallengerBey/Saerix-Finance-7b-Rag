"""
BIST yillik kapanis fiyatlari (Excel) -> toplam getiri + CAGR.

Kaynak: bist30_yillik_fiyatlar_2010_2025.xlsx
Not: 2026 yili yok; canli fiyat yfinance'den gelir.
Hesaplar Python'da yapilir — LLM uydurmasin.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = ROOT / "bist30_yillik_fiyatlar_2010_2025.xlsx"


def _safe_float(v) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=2)
def load_yearly_table(path: str | None = None) -> pd.DataFrame:
    p = Path(path) if path else DEFAULT_XLSX
    if not p.exists():
        raise FileNotFoundError(f"Yillik fiyat Excel yok: {p}")
    df = pd.read_excel(p)
    # Ilk sutun Hisse
    if "Hisse" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Hisse"})
    df["Hisse"] = df["Hisse"].astype(str).str.strip().str.upper()
    return df


def year_columns(df: pd.DataFrame) -> list[int]:
    years = []
    for c in df.columns:
        if c == "Hisse":
            continue
        try:
            y = int(c)
            if 1990 <= y <= 2100:
                years.append(y)
        except (TypeError, ValueError):
            continue
    return sorted(years)


def growth_for_symbol(
    symbol: str,
    path: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> Optional[dict]:
    """
    Tek hisse icin uzun vadeli getiri.

    yil_sayisi = bitis - baslangic (ornek 2010->2025 = 15 donem).
    toplam_getiri_pct = (P_end/P_start - 1) * 100
    cagr_pct = ((P_end/P_start)^(1/n) - 1) * 100
    """
    code = symbol.replace(".IS", "").strip().upper()
    try:
        df = load_yearly_table(path)
    except FileNotFoundError:
        return None

    row = df.loc[df["Hisse"] == code]
    if row.empty:
        return None
    row = row.iloc[0]
    years = year_columns(df)
    if not years:
        return None

    # Istenen aralikta ilk/son DOLU yil
    y_lo = start_year if start_year is not None else years[0]
    y_hi = end_year if end_year is not None else years[-1]
    usable = [y for y in years if y_lo <= y <= y_hi and _safe_float(row.get(y)) is not None]
    if len(usable) < 2:
        return None

    y0, y1 = usable[0], usable[-1]
    p0 = _safe_float(row.get(y0))
    p1 = _safe_float(row.get(y1))
    if not p0 or not p1 or p0 <= 0:
        return None

    n = y1 - y0  # donem sayisi
    if n <= 0:
        return None

    total = (p1 / p0 - 1.0) * 100.0
    cagr = ((p1 / p0) ** (1.0 / n) - 1.0) * 100.0

    # Yillik seriyi kisa metin icin
    series = {y: round(_safe_float(row.get(y)), 4) for y in usable if _safe_float(row.get(y)) is not None}

    return {
        "sembol": code,
        "baslangic_yil": y0,
        "bitis_yil": y1,
        "donem_yil": n,
        "fiyat_baslangic": round(p0, 4),
        "fiyat_bitis": round(p1, 4),
        "toplam_getiri_pct": round(total, 2),
        "cagr_pct": round(cagr, 2),
        "kaynak": "bist30_yillik_fiyatlar_2010_2025.xlsx",
        "not": "2026 yillik kapanis bu dosyada YOK; guncel fiyat yfinance'den.",
        "yillik_fiyatlar": series,
    }


def growth_context(g: dict) -> str:
    """RAG / prompt icin TEK hisse metni (tum BIST dump yok)."""
    if not g:
        return ""
    kaynak = g.get("kaynak", "bilinmiyor")
    note = g.get("not", "2026 yillik kapanis henuz yok." if kaynak == "bist30_yillik_fiyatlar_2010_2025.xlsx" else "yfinance verisinden hesaplandi.")
    lines = [
        f"=== {g['sembol']} UZUN VADELI GETIRI ({kaynak}) ===",
        f"  Kaynak: {kaynak}",
        f"  Donem: {g['baslangic_yil']}-{g['bitis_yil']} ({g['donem_yil']} yil)",
        f"  Yilsonu fiyat {g['baslangic_yil']}: {g['fiyat_baslangic']} TL",
        f"  Yilsonu fiyat {g['bitis_yil']}: {g['fiyat_bitis']} TL",
        f"  Toplam getiri ({g['baslangic_yil']}-{g['bitis_yil']}): %{g['toplam_getiri_pct']:+.2f}",
        f"  CAGR (yillik bilesik getiri): %{g['cagr_pct']:+.2f}",
        f"  Not: {note}",
        "  (Ongoru yorumunda bu CAGR'i referans al; 2026 yillik henuz yok.)",
    ]
    return "\n".join(lines)


def all_symbols(path: str | None = None) -> list[str]:
    try:
        df = load_yearly_table(path)
        return df["Hisse"].tolist()
    except FileNotFoundError:
        return []
