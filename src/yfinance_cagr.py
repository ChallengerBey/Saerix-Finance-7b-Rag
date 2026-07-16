"""
BIST CAGR hesaplama - yfinance verisinden (Excel'e ek/alternatif)
Excel'deki 20 hisse icin oncelik Excel, kalanlar icin yfinance.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional
import time
import pandas as pd
import yfinance as yf


# Pre-validated BIST symbols with good yfinance history (10+ years)
# These are known to work from our earlier test
BIST_UNIVERSE = [
    "THYAO", "ASELS", "GARAN", "AKBNK", "ISCTR",
    "YKBNK", "TUPRS", "EREGL", "KCHOL", "SAHOL",
    "TOASO", "FROTO", "ARCLK", "PGSUS", "TCELL",
    "TTKOM", "BIMAS", "MGROS", "ULKER", "SISE",
    "PETKM", "TAVHL", "KRDMD", "VESTL", "DOAS",
    "ECILC", "ENKAI", "HEKTS", "KARSN", "KONTR",
    "KORDS", "NETAS", "OTKAR", "PNSUT", "SASA",
    "SKBNK", "TATEN", "TKFEN", "TMSN", "TRCAS",
    "TSKB", "TUKAS", "VAKBN", "VERUS", "YATAS",
    "YGGYO", "YYAPI", "ZOREN", "AKCNS", "AKENR",
    "AKFYE", "AKGRT", "AKSA", "AKSEN", "ALARK",
    "ALBRK", "ALCTL", "ALFAS", "ALKIM", "ANHYT",
    "ANSGR", "ARASE", "ASUZU", "ATATP", "ATLAS",
    "AVHOL", "AVOD", "AYDEM", "AYEN", "AYGAZ",
    "BAGFS", "BALAT", "BANVT", "BASCM", "BAYRK",
    "BERA", "BEYAZ", "BFREN", "BINHO", "BIOEN",
    "BJKAS", "BLCYT", "BMSCH", "BNTAS", "BRISA",
    "BRKSN", "BRKVY", "BRMEN", "BRYAT", "BSOKE",
    "BTCIM", "BUCIM", "BURCE", "BURVA", "CANTE",
    "CATES", "CCOLA", "CELEB", "CELHA", "CIMSA",
    "CLEBI", "CMBTN", "CMENT", "CONSE", "CUSAN",
    "CVKMD", "CWENE", "DESA", "DESPC", "DEVA",
    "DGATE", "DGNMO", "DGLTY", "DITAS", "DMSAS",
    "DNISI", "DOAS", "DOCO", "DOHOL", "DOKTA",
    "DURDO", "DYHOL", "DZGYO", "EDATA", "EDIP",
    "EFORC", "EGEEN", "EGGUB", "EGPRO", "EGSER",
    "EKGYO", "EKIZ", "EKOS", "EKSUN", "ELITE",
    "EMKEL", "ENATE", "ENERY", "ENJSA", "ENKAI",
    "ENOS", "ERBOS", "ERCB", "EREL", "ERGYO",
    "ERSU", "ESCAR", "ETILER", "EUHOL", "EUYO",
    "EUPWR", "EUREN", "FENER", "FLAP", "FMIZP",
    "FONET", "FORTE", "FORMT", "FRIGO", "GARAN",
    "GARFA", "GEDIK", "GEDZA", "GENIL", "GENTS",
    "GEREL", "GESAN", "GLBMD", "GLRYH", "GOLTS",
    "GOODY", "GOZDE", "GRNYO", "GSDDE", "GSDHO",
    "GSRAY", "GUBRF", "GUNDG", "GUNES", "GWIND",
    "HALKB", "HATEK", "HDFGS", "HDEF", "HEKTS",
    "HUBVC", "HUNER", "HURGZ", "ICBCT", "ICUGS",
    "IHAAS", "IHEVA", "IHLAS", "IHLGM", "IHYAY",
    "INDES", "INFO", "INVEO", "ISCTR", "ISDMR",
    "ISFIN", "ISGYO", "ISKUR", "ISKPL", "ISMEN",
    "ISYAT", "IZENR", "IZINV", "IZMDC", "KAPLM",
    "KARDS", "KARYE", "KATMR", "KAYSE", "KCAER",
    "KCHOL", "KENT", "KERVN", "KFEIN", "KLGYO",
    "KLMSN", "KLNMA", "KMPUR", "KONTR", "KONYA",
    "KORDS", "KOZAA", "KOZAL", "KRDMD", "KRVGD",
    "KSTUR", "KTLEV", "KUTPO", "KZBG", "LIDFA",
    "LKMNH", "LMKDC", "LOGO", "LUKSK", "MACKO",
    "MAKIM", "MANAS", "MARKA", "MARTI", "MAVIB",
    "MAVI", "MEDTR", "MEGAP", "MERCN", "MERIT",
    "MERKO", "METRO", "METUR", "MGROS", "MIATK",
    "MIPAZ", "MNDRS", "MNDTR", "MOGAN", "MPARK",
    "MRGYO", "MTRKS", "MTRYO", "MZHLD", "NAFT",
    "NETAS", "NIBAS", "NUGYO", "NUHC", "NTHOL",
    "OBAMS", "ODAS", "ODINE", "ONCSM", "ORCAY",
    "ORGE", "OSMEN", "OSTIM", "OTKAR", "OTTO",
    "OYAKC", "OYAYO", "OYYAT", "OZGYO", "OZKGY",
    "OZRDN", "OZSUB", "PAMEL", "PAMTF", "PARSN",
    "PASEU", "PAYHO", "PCILT", "PEGAS", "PEKGY",
    "PENGD", "PENTA", "PETKM", "PETUN", "PGSUS",
    "PINSU", "PKART", "PKENT", "PNSUT", "POLHO",
    "POLNA", "PRKME", "PRKAB", "PRZMA", "PSGYO",
    "QNBFL", "QUAGR", "RALYH", "RAYSG", "REEDR",
    "RHEAG", "RLYAS", "RUBNS", "RYGYO", "SAFKR",
    "SAHOL", "SAMAT", "SANEL", "SANFM", "SANKO",
    "SARKY", "SASA", "SAYAS", "SDTTR", "SEGMN",
    "SEKFK", "SEKUR", "SELEC", "SELGD", "SELVA",
    "SEYKM", "SILVR", "SISE", "SKBNK", "SKTAS",
    "SMRTG", "SNGYO", "SNKRN", "SNMAS", "SNPAM",
    "SODA", "SOKM", "SUNTK", "SUWEN", "TABGD",
    "TARKM", "TATEN", "TAVHL", "TCELL", "TDGYO",
    "TEKTU", "TELKO", "THYAO", "TKFEN", "TKNSA",
    "TLMAN", "TMPOL", "TMSN", "TOASO", "TRCAS",
    "TRGYO", "TSKB", "TSPOR", "TUKAS", "TUPRS",
    "TUREX", "TURGG", "TURSG", "ULKER", "ULUFA",
    "ULUSE", "UMIC", "USAK", "VAKBN", "VAKFN",
    "VAKKO", "VANGD", "VBTYZ", "VESBE", "VESTL",
    "VKGYO", "VKFYO", "YAPRK", "YATAS", "YAYLA",
    "YEOTK", "YGGYO", "YIBSN", "YKBNK", "YONGA",
    "YUNSA", "YYAPI", "YYLGD", "ZEDUR", "ZOREN",
]


# Priority symbols we KNOW work well (tested)
BIST_PRIORITY = [
    "THYAO", "ASELS", "GARAN", "AKBNK", "ISCTR",
    "YKBNK", "TUPRS", "EREGL", "KCHOL", "SAHOL",
    "TOASO", "FROTO", "ARCLK", "PGSUS", "TCELL",
    "TTKOM", "BIMAS", "MGROS", "ULKER", "SISE",
    "PETKM", "TAVHL", "KRDMD", "VESTL", "DOAS",
    "ECILC", "ENKAI", "HEKTS", "KARSN", "KONTR",
    "KORDS", "NETAS", "OTKAR", "PNSUT", "SASA",
    "SKBNK", "TATEN", "TKFEN", "TMSN", "TRCAS",
    "TSKB", "TUKAS", "VAKBN", "VERUS", "YATAS",
    "YGGYO", "YYAPI", "ZOREN",
]

# Symbols that are known to be delisted or problematic
BIST_BLACKLIST = {
    "YGGYO", "YYAPI", "YATAS", "VERUS", "YEOTK", "YIBSN", 
    "KOZAA", "KOZAL", "KZBG", "MIPAZ", "PEGAS", "QNBFL",
    "CELEB", "DGLTY", "DYHOL", "EFORC", "ENATE", "ENOS",
    "EREL", "ERGYO", "ETILER", "GUNES", "KARDS", "KARYE",
    "MAVIB", "METUR", "NAFT", "NUHC", "PAMTF", "PAYHO",
    "POLNA", "MAVIB"
}


def _safe_float(v) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=128)
def fetch_yearly_close_yf(symbol: str) -> Optional[dict]:
    """
    yfinance'den yillik kapanis fiyatlarini cek.
    Donus: {yil: kapanis_fiyati} dict'i
    """
    try:
        yf_sym = f"{symbol}.IS"
        t = yf.Ticker(yf_sym)
        hist = t.history(period="max", auto_adjust=True)
        if hist.empty or len(hist) < 252:  # en az 1 yil
            return None

        # Yillik son islem gunu kapanis
        hist.index = pd.to_datetime(hist.index)
        yearly = hist["Close"].resample("YE").last().dropna()

        result = {}
        for dt, price in yearly.items():
            year = dt.year
            if 1990 <= year <= 2100:
                result[year] = round(float(price), 4)

        return result if len(result) >= 2 else None
    except Exception:
        return None


def has_current_data(symbol: str) -> bool:
    """
    Sembolun guncel fiyat verisi olup olmadigini kontrol et.
    """
    try:
        yf_sym = f"{symbol}.IS"
        t = yf.Ticker(yf_sym)
        hist = t.history(period="1mo")
        return not hist.empty
    except Exception:
        return False


def calculate_cagr_from_yf(symbol: str, start_year: int = None, end_year: int = None) -> Optional[dict]:
    """
    yfinance verisinden CAGR hesapla.
    """
    # Skip blacklisted symbols
    if symbol in BIST_BLACKLIST:
        return None
        
    data = fetch_yearly_close_yf(symbol)
    if not data:
        return None

    years = sorted(data.keys())
    if start_year is not None:
        years = [y for y in years if y >= start_year]
    if end_year is not None:
        years = [y for y in years if y <= end_year]

    if len(years) < 2:
        return None

    y0, y1 = years[0], years[-1]
    p0, p1 = data[y0], data[y1]

    if not p0 or not p1 or p0 <= 0:
        return None

    n = y1 - y0
    total = (p1 / p0 - 1.0) * 100.0
    cagr = ((p1 / p0) ** (1.0 / n) - 1.0) * 100.0

    return {
        "sembol": symbol,
        "baslangic_yil": y0,
        "bitis_yil": y1,
        "donem_yil": n,
        "fiyat_baslangic": round(p0, 4),
        "fiyat_bitis": round(p1, 4),
        "toplam_getiri_pct": round(total, 2),
        "cagr_pct": round(cagr, 2),
        "kaynak": "yfinance",
        "yillik_fiyatlar": {y: data[y] for y in years},
    }


def get_all_cagr(min_years: int = 10, use_priority: bool = True) -> list[dict]:
    """
    Tum BIST universe icin CAGR hesapla (cache'li).
    """
    universe = BIST_PRIORITY if use_priority else BIST_UNIVERSE
    results = []
    
    for i, sym in enumerate(universe):
        try:
            g = calculate_cagr_from_yf(sym)
            if g and g["donem_yil"] >= min_years:
                results.append(g)
            # Rate limit: sleep every 10 requests
            if i % 10 == 9:
                time.sleep(0.5)
        except Exception:
            continue
    results.sort(key=lambda x: x["cagr_pct"], reverse=True)
    return results


def merge_with_excel(excel_results: list[dict], yf_results: list[dict]) -> list[dict]:
    """
    Excel verisi oncelikli, yfinance ile birlestir.
    Ayni sembol varsa Excel'i al.
    """
    excel_symbols = {r["sembol"] for r in excel_results}
    merged = list(excel_results)

    for yf_r in yf_results:
        if yf_r["sembol"] not in excel_symbols:
            merged.append(yf_r)

    merged.sort(key=lambda x: x["cagr_pct"], reverse=True)
    return merged


if __name__ == "__main__":
    # Test - just priority symbols
    print("Testing yfinance CAGR (priority symbols only)...")
    all_cagr = get_all_cagr(min_years=10, use_priority=True)
    print(f"\nFound {len(all_cagr)} symbols with 10+ years data")
    for i, g in enumerate(all_cagr[:20], 1):
        print(f"  {i:>2}. {g['sembol']:<8} CAGR %{g['cagr_pct']:>6.2f} | %{g['toplam_getiri_pct']:>8.2f} ({g['donem_yil']}y) [{g['kaynak']}]")