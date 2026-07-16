"""
Borsa RAG Pipeline - EVDS + yfinance + Ollama (local desktop)
Kullanim:
  pwsh scripts/setup_ollama_model.ps1   # modeli bir kez indir (~4.7 GB)
  python src/rag_pipeline.py build      # Index olustur/guncelle
  python src/rag_pipeline.py "THYAO analiz"
"""
import os, json, sys, time, re
from pathlib import Path
from typing import Optional
from datetime import datetime

# Fix 2: Console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import pandas as pd
import yfinance as yf
import faiss
import ollama
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from yearly_prices import growth_for_symbol, growth_context, all_symbols as yearly_symbols

try:
    import yaml
except ImportError:
    yaml = None


def _load_inference_config() -> dict:
    """configs/config.yaml + BORSA_OLLAMA_MODEL env."""
    cfg = {
        "ollama_model": "borsa-llm",
        "ollama_model_fallback": "hf.co/finansai/BIST-Financial-Qwen-7B:Q4_K_M",
        "temperature": 0.1,
        "top_p": 0.5,
        "num_predict": 400,
        "repeat_penalty": 1.1,
        "embedding_model": "all-MiniLM-L6-v2",
        "vector_db_path": "data/processed/faiss_index",
        "docs_path": "data/docs",
        "chunk_size": 800,
        "chunk_overlap": 100,
    }
    config_path = ROOT / "configs" / "config.yaml"
    if yaml and config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        inf = raw.get("inference") or {}
        rag = raw.get("rag") or {}
        for k in (
            "ollama_model",
            "ollama_model_fallback",
            "temperature",
            "top_p",
            "num_predict",
            "repeat_penalty",
        ):
            if k in inf:
                cfg[k] = inf[k]
        for k in (
            "embedding_model",
            "vector_db_path",
            "docs_path",
            "chunk_size",
            "chunk_overlap",
        ):
            if k in rag:
                cfg[k] = rag[k]
    env_model = os.environ.get("BORSA_OLLAMA_MODEL")
    if env_model:
        cfg["ollama_model"] = env_model
    return cfg


INFER_CFG = _load_inference_config()


def resolve_ollama_model() -> str:
    """Kurulu alias varsa onu, yoksa HF GGUF tag'ini kullan."""
    preferred = INFER_CFG["ollama_model"]
    fallback = INFER_CFG["ollama_model_fallback"]
    try:
        names = {m.model for m in ollama.list().models}
        if preferred in names or any(n.startswith(preferred + ":") for n in names):
            return preferred
        if fallback in names or any(fallback in n for n in names):
            return fallback
    except Exception:
        pass
    return preferred


OLLAMA_MODEL = resolve_ollama_model()
EMBED_MODEL = SentenceTransformer(INFER_CFG["embedding_model"])
EMBED_DIM = EMBED_MODEL.get_embedding_dimension()
FAISS_PATH = INFER_CFG["vector_db_path"]
SYMBOLS = [
    "THYAO.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS", "ISCTR.IS",
    "YKBNK.IS", "TUPRS.IS", "EREGL.IS", "KCHOL.IS", "SAHOL.IS",
    "TOASO.IS", "FROTO.IS", "ARCLK.IS", "PGSUS.IS", "TCELL.IS",
    "TTKOM.IS", "BIMAS.IS", "MGROS.IS", "ULKER.IS", "SISE.IS",
]
BUGUN = datetime.now().strftime("%d-%m-%Y")


# ===================== Fix 2: Structured Output (JSON Schema) =====================
class FinansalAnaliz(BaseModel):
    """LLM ciktisinin zorunlu semasi. Sayisal alanlar Python ile doldurulur."""
    sirket: str = Field(description="Hisse kodu, orn. THYAO")
    guncel_fiyat: Optional[float] = Field(default=None, description="TL son fiyat — context'teki guncel_fiyat_TL")
    guncel_fk: Optional[float] = Field(default=None, description="F/K — context'teki guncel_fk")
    guncel_piyasa_degeri: Optional[float] = Field(default=None, description="Piyasa degeri USD — context'teki guncel_piyasa_degeri_USD")
    temettu_verimi: Optional[float] = Field(default=None, description="Temettu % — context'teki temettu_verimi_pct")
    uzun_vade_donem: Optional[str] = Field(default=None, description="Orn. 2010-2025 Excel donemi")
    uzun_vade_toplam_getiri_pct: Optional[float] = Field(default=None, description="Excel toplam getiri %")
    uzun_vade_cagr_pct: Optional[float] = Field(default=None, description="Excel CAGR % (yillik bilesik)")
    teknik_yorum: str = Field(description="Trend/SMA; sadece context. Kesin tahmin yok")
    temel_yorum: str = Field(
        description="F/K ve Excel CAGR/toplam getiriye dayali kisa yorum; uydurma rakam yok"
    )
    riskler: str = Field(description="Kisa risk notu, yatirim tavsiyesi yok")
    veri_eksik: bool = Field(default=False, description="Kritik canli veri yoksa true")


def embed(texts: list[str]) -> np.ndarray:
    return EMBED_MODEL.encode(texts, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


def load_evds():
    from fetchers.evds_excel import load_evds_excel, format_macro_context, format_inflation_context
    df = load_evds_excel()
    return format_macro_context(df), format_inflation_context(df)


# ===================== Fix 5: Financial Math in Python =====================
def safe_round(val, decimals=2):
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return None


def fmt_market_cap(val_usd: Optional[float]) -> str:
    """Market cap'i insan okuyabilir formata cevir (Trilyon/Milyar/Milyon)."""
    if val_usd is None:
        return "YOK"
    if val_usd >= 1e12:
        return f"{val_usd / 1e12:.2f} Trilyon USD"
    if val_usd >= 1e9:
        return f"{val_usd / 1e9:.2f} Milyar USD"
    if val_usd >= 1e6:
        return f"{val_usd / 1e6:.2f} Milyon USD"
    return f"{val_usd:,.0f} USD"


def get_usdtry_series(period: str = "6mo") -> pd.Series:
    """USD/TRY kapanis serisini TEK SEFERDE ceker (tum semboller icin paylasilir).
    Her sembol icin ayri ayri cagirmak Yahoo'nun rate-limit'ine takilip
    diger verilerin (fiyat, hacim) NaN donmesine sebep olabiliyordu."""
    try:
        df = yf.download("USDTRY=X", period=period, progress=False)
        close = df["Close"].squeeze()
        return close.dropna()
    except Exception:
        return pd.Series(dtype=float)


def fetch_stock(symbol: str, period: str = "6mo", usdtry_series: pd.Series = None) -> dict:
    s = yf.Ticker(symbol)
    info = s.info or {}
    hist = s.history(period=period)

    # Bug fix: piyasa kapanmadan cekilen son satirin Close'u NaN gelebiliyor
    # (Volume dolu ama gun henuz finalize edilmemis). Bu satiri atmazsak
    # fiyat, SMA ve getiri hesaplarinin hepsi NaN'a doner.
    if not hist.empty:
        hist = hist.dropna(subset=["Close"])

    if usdtry_series is None:
        usdtry_series = get_usdtry_series(period)

    code = symbol.replace(".IS", "")
    firma = info.get("longName", code)
    sektor = info.get("industry", info.get("sector", "Bilinmiyor"))
    raw_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if raw_price is None and not hist.empty:
        raw_price = hist["Close"].iloc[-1]
    fiyat = safe_round(raw_price)

    # Market cap: BIST (.IS) icin TL->USD cevir, digerleri (ABD, EU) zaten USD
    is_bist = symbol.endswith(".IS")
    usdtry_rate = float(usdtry_series.iloc[-1]) if not usdtry_series.empty else None
    piyasa_degeri_tl = safe_round(info.get("marketCap"))
    if is_bist:
        piyasa_degeri = safe_round(piyasa_degeri_tl / usdtry_rate) if piyasa_degeri_tl and usdtry_rate else None
    else:
        piyasa_degeri = piyasa_degeri_tl  # ABD hisseleri zaten USD

    pe = safe_round(info.get("trailingPE"))
    pb = safe_round(info.get("priceToBook"))
    ev = safe_round(info.get("enterpriseValue"))
    favok = safe_round(info.get("ebitda"))
    fd_favok = safe_round(ev / favok) if ev and favok and favok != 0 else None
    kar_marji = safe_round(info.get("profitMargins") * 100) if info.get("profitMargins") else None
    roe = safe_round(info.get("returnOnEquity") * 100) if info.get("returnOnEquity") else None
    borc_ebitda = safe_round(info.get("totalDebt") / info.get("ebitda")) if info.get("totalDebt") and info.get("ebitda") and info["ebitda"] != 0 else None
    hedef = safe_round(info.get("targetMeanPrice"))
    kar_buyume = safe_round(info.get("earningsGrowth") * 100) if info.get("earningsGrowth") else None
    gelir_buyume = safe_round(info.get("revenueGrowth") * 100) if info.get("revenueGrowth") else None

    # Dividend yield: yfinance bazen kesir (0.005 = %0.5), bazen yuzde (0.53 = %0.53) doner.
    # Gercek temettu %12'yi gecmez. >12 ise zaten yuzde, <0.1 ise kesir, arasi belirsiz.
    raw_dy = info.get("dividendYield")
    if raw_dy is not None:
        if raw_dy > 12:          # 12 uzeri -> zaten yuzde (orn. 3.5 = %3.5)
            temettu = safe_round(raw_dy)
        elif raw_dy < 0.1:       # 0.1 altı -> kesir (orn. 0.005 = %0.5)
            temettu = safe_round(raw_dy * 100)
        else:                    # 0.1-12 arasi -> muhtemelen yuzde (orn. 0.53 = %0.53)
            temettu = safe_round(raw_dy)
    else:
        temettu = None

    p = {}
    if not hist.empty:
        last = hist.iloc[-1]
        p = {
            "fiyat": safe_round(last["Close"]),
            "hacim": int(last["Volume"]),
            "sma20": safe_round(hist["Close"].rolling(20).mean().iloc[-1]),
            "sma50": safe_round(hist["Close"].rolling(50).mean().iloc[-1]),
            "1ay": safe_round((last["Close"] / hist.iloc[-22]["Close"] - 1) * 100) if len(hist) >= 22 else None,
            "3ay": safe_round((last["Close"] / hist.iloc[-66]["Close"] - 1) * 100) if len(hist) >= 66 else None,
        }
        sma200 = hist["Close"].rolling(200).mean().dropna()
        if len(sma200) > 0:
            p["sma200"] = safe_round(sma200.iloc[-1])
            p["trend"] = "yukari" if last["Close"] > sma200.iloc[-1] else "asagi"

        # Dolar bazli getiri (Fix 5) - ayni USDTRY serisini tekrar kullan (ekstra indirme yok)
        try:
            if not usdtry_series.empty and len(hist) > 1:
                fytl_0 = float(hist["Close"].iloc[0])
                fytl_s = float(last["Close"])
                usd_0 = float(usdtry_series.iloc[0])
                usd_s = float(usdtry_series.iloc[-1])
                if usd_0 > 0 and usd_s > 0:
                    usd_bas = fytl_0 / usd_0
                    usd_sim = fytl_s / usd_s
                    p["dolar_getiri_6ay"] = safe_round((usd_sim / usd_bas - 1) * 100)
        except Exception:
            pass

    return {
        "sembol": code, "firma": firma, "sektor": sektor,
        "fiyat": fiyat, "piyasa_degeri": piyasa_degeri,
        "piyasa_degeri_tl": piyasa_degeri_tl, "usdtry_rate": usdtry_rate,
        "pe": pe, "pb": pb, "fd_favok": fd_favok,
        "kar_marji": kar_marji, "roe": roe,
        "borc_ebitda": borc_ebitda, "hedef": hedef,
        "kar_buyume": kar_buyume, "gelir_buyume": gelir_buyume,
        "temettu": temettu, "detay": p
    }


def stock_context(data: dict) -> str:
    """Canli veri. Alan adlari JSON semasiyla ayni — model kopyalasin, Python da ezer."""
    s = data["sembol"]
    p = data.get("detay") or {}
    fx = p.get("fiyat") if p.get("fiyat") is not None else data.get("fiyat")

    lines = [f"=== {s} ({data['firma']}) — CANLI (yfinance) ==="]
    lines.append(f"  Sektor: {data['sektor']}")
    lines.append(f"  Tarih: {BUGUN}")
    # Acik anahtarlar: LLM + post-fill ayni isimleri okur
    lines.append(f"  guncel_fiyat_TL: {fx if fx is not None else 'YOK'}")
    lines.append(f"  guncel_fk: {data['pe'] if data.get('pe') is not None else 'YOK'}")
    lines.append(
        f"  guncel_piyasa_degeri_USD: {fmt_market_cap(data.get('piyasa_degeri'))}"
    )
    lines.append(
        f"  piyasa_degeri_TL: {fmt_market_cap(data.get('piyasa_degeri_tl')) if data.get('piyasa_degeri_tl') is not None else 'YOK'}"
        f" | usdtry: {data.get('usdtry_rate') if data.get('usdtry_rate') is not None else 'YOK'}"
    )
    if data.get("temettu") is not None and data["temettu"] > 0:
        lines.append(f"  temettu_verimi_pct: {data['temettu']}")
    else:
        lines.append("  temettu_verimi_pct: YOK")

    if fx is not None:
        if p.get("hacim") is not None:
            lines.append(f"  Hacim: {p['hacim']} lot")
        lines.append(
            f"  SMA20: {p.get('sma20', '?')} | SMA50: {p.get('sma50', '?')} | SMA200: {p.get('sma200', '?')}"
        )
        lines.append(f"  Trend: {p.get('trend', '?')}")
        if p.get("1ay") is not None or p.get("3ay") is not None:
            lines.append(
                f"  1 ay getiri: %{p.get('1ay') if p.get('1ay') is not None else '?'} | "
                f"3 ay: %{p.get('3ay') if p.get('3ay') is not None else '?'}"
            )
        if p.get("dolar_getiri_6ay") is not None:
            lines.append(f"  Dolar bazli 6 ay getiri: %{p['dolar_getiri_6ay']:+.2f}")

    lines.append(
        f"  P/B: {data['pb'] if data.get('pb') is not None else '?'} | "
        f"FD/FAVOK: {data['fd_favok'] if data.get('fd_favok') is not None else '?'}"
    )
    if data.get("kar_marji") is not None:
        lines.append(f"  Kar marji: %{data['kar_marji']:.1f} | ROE: %{data.get('roe') or 0:.1f}")
    if data.get("borc_ebitda") is not None:
        lines.append(f"  Borc/EBITDA: {data['borc_ebitda']}x")
    if data.get("kar_buyume") is not None:
        lines.append(
            f"  Kar buyume: %{data['kar_buyume']:+.1f} | "
            f"Gelir buyume: %{data.get('gelir_buyume') or 0:+.1f}"
        )
    if data.get("hedef") and fx:
        pot = (data["hedef"] / fx - 1) * 100
        lines.append(f"  Analist hedefi: {data['hedef']} TL (potansiyel %{pot:+.1f})")

    return "\n".join(lines)


def detect_symbol(question: str) -> Optional[str]:
    """Sorudan BIST kodu cikar (THYAO / THYAO.IS). Bilinen listede yoksa yfinance sembol pattern'i ara."""
    q = (question or "").upper()
    # Once bilinen liste
    codes = [s.replace(".IS", "") for s in SYMBOLS]
    for code in codes:
        if code in q:
            return code
    # Excel'deki digerleri
    for code in yearly_symbols():
        if code in q:
            return code
    # Bilinen listede yoksa: yaygin yfinance sembol pattern'leri ara (AAPL, TSLA, MSFT, GOOGL, etc.)
    import re
    # 1-5 harfli buyuk harf, opsiyonel .IS/.US gibi uzanti
    matches = re.findall(r"\b([A-Z]{1,5})(?:\.(?:IS|US|AS|L|PA|DE|TO|V|HK|JP|CN|TW|KS|KQ|SI|KL|JK|TH|MY|PH|TW|VN|ID|BR|MX|AR|CL|CO|PE|ZA|NG|EG|KE|MA|TN|DZ|GH|SN|CI|CM|TG|BJ|BF|ML|NE|MR|LR|SL|GN|GW|CV|ST|KM|MU|SC|YT|RE|MF|BL|GP|MQ|GF|PM|WF|PF|NC|TK|NU|CK|PN|TV|FM|MH|KI|NR|PW|WS|TO|FJ|VU|NC|PF|PG|SB|VU|NF|NF|FM|MH|KI|NR|PW|TV|WS|FJ|PG|SB|VU|NF|WF|PF|NC|TK|NU|CK|PN|TV|FM|MH|KI|NR|PW|WS|TO|FJ|PG|SB|VU|NF|WF|PF|NC|TK|NU|CK|PN|TV|FM|MH|KI|NR|PW|TV|WS|TO|FJ|PG|SB|VU|NF|WF|PF|NC|TK|NU|CK|PN|TV|FM|MH|KI|NR|PW|TV|WS|TO|FJ|PG|SB|VU|NF|WF|PF|NC|TK|NU|CK|PN|TV|FM|MH|KI|NR|PW|TV|WS|TO|FJ|PG|SB|VU|NF|WF|PF|NC|TK|NU|CK|PN|TV|FM|MH|KI|NR|PW|TV|WS|TO|FJ|PG|SB|VU|NF|WF|PF|NC|TK|NU|CK|PN))\b", q)
    if matches:
        return matches[0] + ".IS" if matches[0] in codes else matches[0]
    # Basit pattern: buyuk harf 1-5 karakter (AAPL, TSLA, MSFT, GOOGL, NVDA, etc.)
    simple = re.findall(r"\b([A-Z]{1,5})\b", q)
    for s in simple:
        if s not in ("VE", "VEYA", "ILE", "ICIN", "BIR", "BU", "DA", "DE", "KI", "MI", "MU", "NE", "NASIL", "NEDIR", "ANALIZ", "HISSE", "FIYAT", "GETIRI", "YATIRIM", "RISK", "PORTFOY", "BIST", "NASDAQ", "NYSE", "SP500", "DOW", "VIX", "USD", "TRY", "EUR", "GBP", "JPY", "CNY", "BTC", "ETH", "BNB", "SOL", "ADA", "DOT", "LINK", "UNI", "MATIC", "AVAX", "ATOM", "NEAR", "ALGO", "XRP", "DOGE", "SHIB", "TRX", "TON", "OKB", "LEO", "CRO", "HT", "KCS", "BGB", "GT", "MX", "HTX", "BIT", "COIN", "BINANCE", "BYBIT", "OKX", "KUCOIN", "HUOBI", "GATE", "MEXC", "BITGET", "BINGX", "PHEMEX", "DERIBIT", "DYDX", "GMX", "PERP", "APEX", "ORDERLY", "VERTEX", "SYNTHETIX", "DYDX", "GMX", "PERP", "APEX", "ORDERLY", "VERTEX"):
            return s
    return None


def fill_from_python(cevap: dict, live: Optional[dict], growth: Optional[dict]) -> dict:
    """
    LLM uydurma/null biraksin — sayisal alanlari Python ezer.
    Bu, guncel_fiyat null kalma bug'unu cozer.
    """
    if live:
        p = live.get("detay") or {}
        fx = p.get("fiyat") if p.get("fiyat") is not None else live.get("fiyat")
        cevap["sirket"] = live.get("sembol") or cevap.get("sirket")
        if live.get("firma"):
            cevap["sirket"] = f"{live['sembol']} ({live['firma']})"
        cevap["guncel_fiyat"] = fx
        cevap["guncel_fk"] = live.get("pe")
        cevap["guncel_piyasa_degeri"] = live.get("piyasa_degeri")
        cevap["temettu_verimi"] = live.get("temettu")
        # Canli fiyat yoksa veri_eksik
        if fx is None and live.get("pe") is None:
            cevap["veri_eksik"] = True
        else:
            cevap["veri_eksik"] = False

        # Fallback: teknik_yorum bos/genelse Python uret
        if not cevap.get("teknik_yorum") or "yeterli" in cevap["teknik_yorum"].lower() or "eksik" in cevap["teknik_yorum"].lower():
            sma20 = p.get("sma20")
            sma50 = p.get("sma50")
            sma200 = p.get("sma200")
            trend = p.get("trend")
            g1 = p.get("1ay")
            g3 = p.get("3ay")
            parts = []
            if fx and sma20 and sma50:
                if fx > sma20 and fx > sma50:
                    parts.append("Fiyat SMA20 ve SMA50 uzerinde")
                elif fx < sma20 and fx < sma50:
                    parts.append("Fiyat SMA20 ve SMA50 altinda")
                else:
                    parts.append("Fiyat SMA20/SMA50 karisik")
            if sma200 and fx:
                parts.append(f"SMA200 {'ustunde' if fx > sma200 else 'altinda'}")
            if trend:
                parts.append(f"Trend {trend}")
            if g1 is not None or g3 is not None:
                parts.append(f"1a %{g1 or '?'} | 3a %{g3 or '?'}")
            if parts:
                cevap["teknik_yorum"] = "; ".join(parts) + "."

    if growth:
        cevap["uzun_vade_donem"] = f"{growth['baslangic_yil']}-{growth['bitis_yil']}"
        cevap["uzun_vade_toplam_getiri_pct"] = growth["toplam_getiri_pct"]
        cevap["uzun_vade_cagr_pct"] = growth["cagr_pct"]

    return cevap


# ===================== FAISS =====================
class VectorDB:
    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)
        self.chunks: list[dict] = []

    def add(self, texts: list[str], metas: list[dict] = None):
        vecs = embed(texts)
        self.index.add(vecs)
        for i, t in enumerate(texts):
            self.chunks.append({"text": t, "meta": metas[i] if metas else {}})

    def search(self, query: str, k: int = 5) -> list[dict]:
        if not self.chunks:
            return []
        qv = embed([query])
        d, idx = self.index.search(qv, min(k, len(self.chunks)))
        return [{"text": self.chunks[i]["text"], "meta": self.chunks[i]["meta"], "score": float(d[0][j])}
                for j, i in enumerate(idx[0])]

    def save(self, path: str = FAISS_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, f"{path}.index")
        with open(f"{path}.json", "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False)

    def load(self, path: str = FAISS_PATH) -> bool:
        if not Path(f"{path}.index").exists():
            return False
        self.index = faiss.read_index(f"{path}.index")
        with open(f"{path}.json", "r", encoding="utf-8") as f:
            self.chunks = json.load(f)
        print(f"FAISS yuklendi: {len(self.chunks)} chunk")
        return True


def build_index():
    print("Index olusturuluyor (sifirdan)...")
    # Bug fix: onceden db.load() ile eski index yuklenip ustune ekleniyordu,
    # bu da her build'de eski/bozuk kayitlarin index'te birikmesine
    # (duplicate stale chunks) sebep oluyordu. Artik her build TEMIZ baslar.
    db = VectorDB()

    macro, infl = load_evds()
    db.add([f"Tarih: {BUGUN}\n{macro}"], [{"type": "evds_macro"}])
    db.add([infl], [{"type": "evds_inflation"}])

    # USD/TRY serisini TEK SEFERDE cek, tum semboller bunu paylassin.
    # (Onceki versiyon her sembol icin ayri indirme yapiyordu, bu da
    # Yahoo'nun rate-limit'ine takilip fiyat/hacim verilerinin NaN
    # donmesine sebep oluyordu.)
    usdtry_series = get_usdtry_series()

    for sym in SYMBOLS:
        try:
            data = fetch_stock(sym, usdtry_series=usdtry_series)
            ctx = stock_context(data)
            code = sym.replace(".IS", "")
            db.add([ctx], [{"type": "stock", "symbol": code}])
            # Excel uzun vadeli getiri — AYRI chunk, ayni symbol etiketi (tum BIST tek chunk degil)
            g = growth_for_symbol(code)
            if g:
                db.add(
                    [growth_context(g)],
                    [{"type": "yearly_growth", "symbol": code}],
                )
            detay = data.get("detay") or {}
            fiyat = detay.get("fiyat") if detay.get("fiyat") is not None else data.get("fiyat")
            cagr = f" CAGR%{g['cagr_pct']}" if g else ""
            print(f" + {sym}: {fiyat} TL{cagr}")
            # Console ciktisi disinda live veri dict'ine de fiyat ekle
            if "detay" in data:
                data["detay"]["fiyat"] = fiyat
            else:
                data["fiyat"] = fiyat
        except Exception as e:
            print(f"  x {sym}: {e}")
        time.sleep(0.5)  # Yahoo rate-limit'ine takilmamak icin kucuk bekleme

    # Opsiyonel: data/docs (docx/txt/csv)
    docs_dir = INFER_CFG.get("docs_path", "data/docs")
    chunk_size = int(INFER_CFG.get("chunk_size", 800))
    chunk_overlap = int(INFER_CFG.get("chunk_overlap", 100))
    print(f"Kullanici dokumanlari: {docs_dir}")
    try:
        from docs_loader import load_docs_dir

        doc_texts, doc_metas = load_docs_dir(
            docs_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        if doc_texts:
            db.add(doc_texts, doc_metas)
            print(f"  docs toplam: {len(doc_texts)} chunk")
        else:
            print("  (data/docs bos)")
    except Exception as e:
        print(f"  docs atlandi: {e}")

    db.save()
    print(f"Kaydedildi: {len(db.chunks)} chunk")


# Popular US stocks for analysis (no Excel long-term data, just live yfinance)
US_STOCKS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "JPM", "V", "MA", "UNH", "HD", "PG", "JNJ", "XOM", "LLY", "MRK",
    "COST", "ABBV", "PEP", "KO", "ADBE", "CRM", "NFLX", "INTC", "AMD",
    "QCOM", "TXN", "AMAT", "INTU", "ISRG", "BKNG", "GILD", "MDT", "ADP",
    "BMY", "CVX", "WMT", "DIS", "NKE", "RTX", "UPS", "HON", "LOW", "CAT"
]


# ===================== Top Performers Analysis =====================
def top_performers(top_n: int = 10, min_cagr: float = 15.0, live_analysis: bool = False, market: str = "BIST"):
    """
    Analyze top performers by CAGR (BIST) or momentum (US).
    market: "BIST" or "US"
    live_analysis=True: LLM analysis per stock (slow)
    live_analysis=False: Just table + live data summary (fast)
    """
    from yearly_prices import growth_for_symbol, all_symbols

    print(f"\n{'='*60}")
    if market == "BIST":
        print(f"BIST UZUN VADELI PERFORMANS ANALIZI (Excel + yfinance merged)")
    else:
        print(f"US STOCKS MOMENTUM ANALIZI (Live yfinance)")
    print(f"{'='*60}")

    if market == "BIST":
        # Merge Excel + yfinance data (Excel takes priority)
        from yfinance_cagr import get_all_cagr, merge_with_excel
        
        excel_results = []
        for sym in all_symbols():
            g = growth_for_symbol(sym)
            if g:
                excel_results.append(g)
        
        print("yfinance verisi cekiliyor...")
        yf_results = get_all_cagr(min_years=10)
        
        merged = merge_with_excel(excel_results, yf_results)
        results = [g for g in merged if g["cagr_pct"] >= min_cagr]
        results.sort(key=lambda x: x["cagr_pct"], reverse=True)
        top = results[:top_n]

        print(f"\nTop {len(top)} / {len(results)} hisse (CAGR >= %{min_cagr}):\n")
        print(f"{'#':>2} {'Sembol':<8} {'CAGR%':>8} {'Toplam%':>10} {'Baslangic':>10} {'Bitis':>10} {'Donem':>4} {'Kaynak'}")
        print("-" * 85)
        for i, g in enumerate(top, 1):
            print(f"{i:>2} {g['sembol']:<8} {g['cagr_pct']:>8.2f} {g['toplam_getiri_pct']:>10.2f} "
                  f"{g['fiyat_baslangic']:>10.2f} {g['fiyat_bitis']:>10.2f}  {g['donem_yil']}y  {g.get('kaynak', 'excel')}")

    else:  # US stocks
        top = US_STOCKS[:top_n]
        print(f"\nTop {len(top)} US hisse (populer buyuk cap):\n")
        print(f"{'#':>2} {'Sembol':<8} {'Sektor/Not'}")
        print("-" * 40)
        for i, sym in enumerate(top, 1):
            print(f"{i:>2} {sym:<8}")

    if not live_analysis:
        print(f"\n>>> Canli analiz icin: python src/rag_pipeline.py top {top_n} --live --market {market}")
        return

    # Canli veri cek ve analiz yap
    print(f"\n{'='*60}")
    print("CANLI VERI + ALIM ANALIZI (yfinance + LLM)")
    print(f"{'='*60}")

    usdtry_series = get_usdtry_series() if market == "BIST" else None

    for i, item in enumerate(top, 1):
        if market == "BIST":
            g = item
            sym = g["sembol"]
            yf_sym = f"{sym}.IS"
            print(f"\n--- #{i} {sym} ---")
            src = g.get('kaynak', 'excel')
            period = f"{g['baslangic_yil']}-{g['bitis_yil']}"
            print(f"  {src.upper()} CAGR ({period}): %{g['cagr_pct']:.2f} | Toplam: %{g['toplam_getiri_pct']:.2f}")
            growth_ctx = growth_context(g)
        else:
            sym = item
            yf_sym = sym
            print(f"\n--- #{i} {sym} ---")
            growth_ctx = ""

        try:
            live = fetch_stock(yf_sym, usdtry_series=usdtry_series)
            p = live.get("detay") or {}
            fx = p.get("fiyat") if p.get("fiyat") is not None else live.get("fiyat")

            currency = "TL" if market == "BIST" else "USD"
            print(f"  Guncel Fiyat: {fx if fx else 'YOK'} {currency}")
            if live.get('piyasa_degeri'):
                cap_str = f"${live.get('piyasa_degeri', 0):,.0f}"
                print(f"  F/K: {live.get('pe', 'YOK')} | Piyasa Degeri: {cap_str}")
            print(f"  Temettu: %{live.get('temettu', 'YOK')} | Kar Marji: %{live.get('kar_marji', 'YOK')} | ROE: %{live.get('roe', 'YOK')}")

            if p.get("sma20") and p.get("sma50") and fx:
                pos = "USTUNDE" if fx > p["sma20"] and fx > p["sma50"] else "ALTINDA" if fx < p["sma20"] and fx < p["sma50"] else "KARISIK"
                print(f"  Teknik: Fiyat SMA20({p['sma20']:.2f})/SMA50({p['sma50']:.2f}) {pos} | Trend: {p.get('trend', '?')}")
                print(f"  Getiriler: 1a %{p.get('1ay', '?')} | 3a %{p.get('3ay', '?')}", end="")
                if p.get('dolar_getiri_6ay') is not None:
                    print(f" | \$6a %{p.get('dolar_getiri_6ay', '?')}", end="")
                print()

            # LLM ile "neden alinmali" analizi
            context = stock_context(live)
            if growth_ctx:
                context += "\n\n" + growth_ctx
            question = f"{sym} icin yatirim gerekcelesi analizi yap. Guncel teknikal ve temel verileri kullanarak neden alinmali/alinmamali kisa ozetle."
            _ = sor(question)

            time.sleep(0.5)

        except Exception as e:
            print(f"  HATA: {e}")
SYSTEM_PROMPT = (
    "Sen bir finans asistanisin. SADECE GUNCEL VERILER bolumundeki rakamlari kullan. "
    "Baska kaynaktan rakam UYDURMA.\n"
    "KURALLAR:\n"
    "- guncel_fiyat, guncel_fk, guncel_piyasa_degeri, temettu, uzun_vade_* alanlarini "
    "context'teki ayni isimli degerlerden kopyala (Python da ezecek).\n"
    "- Yorumlarda SADECE bu hisseye ait context kullan; baska hisse/BIST geneli ekleme.\n"
    "- Uzun vadeli artis icin context'teki CAGR ve toplam_getiri'yi referans al; "
    "kendin yuzde hesaplama. 2026 yillik kapanis dosyada YOK.\n"
    "- KESIN Fiyat TAHMINI / yatirim tavsiyesi VERME. Risk belirt.\n"
    "- Sadece JSON semasina uygun SAF JSON yaz.\n"
    "- Yanitlari kesinlikle Turkce dilbilgisi kurallarina uygun, dogru karakterlerle (ı, ğ, ü, ş, ö, ç) yaz.\n"
    "- teknik_yorum icin context'te SMA20/50/200, trend, 1-3 ay getirileri varsa onlari kullanarak KISA ozet yaz; "
    "veri yoksa 'Yeterli teknik veri bulunamadi' yaz.\n"
    "- METRİK KARIŞTIRMASI YAPMA: Temettü Verimi (%), F/K (çarpan), P/B (çarpan), Piyasa Değeri (Trilyon/Milyar USD) "
    "her birini doğru birimle tanımla ve birbirine karıştırma.\n"
    "- Bugun: {tarih}."
)


def sor(question: str, db: VectorDB = None):
    if db is None:
        db = VectorDB()
        if not db.load():
            print("Index yok, once 'build' calistir")
            return

    code = detect_symbol(question)
    live = None
    growth = None
    context_parts: list[str] = []
    sources: list[str] = []

    # --- 1) Canli yfinance + Excel getiri (sadece sorulan hisse) ---
    if code:
        # BIST hisseleri icin .IS eki gerekli, ABD hisseleri icin gerekmez
        is_bist = code in [s.replace(".IS", "") for s in SYMBOLS] or code in yearly_symbols()
        yf_symbol = f"{code}.IS" if is_bist else code
        try:
            live = fetch_stock(yf_symbol)
            context_parts.append(stock_context(live))
            sources.append(f"{code}:live")
        except Exception as e:
            context_parts.append(f"=== {code} CANLI VERI HATA: {e} ===")
            sources.append(f"{code}:live_err")

        growth = growth_for_symbol(code)
        if growth:
            context_parts.append(growth_context(growth))
            sources.append(f"{code}:excel_2010_2025")
        else:
            context_parts.append(
                f"=== {code} Excel uzun vadeli getiri: dosyada yok veya eksik ==="
            )

    # --- 2) RAG: SADECE bu sembol (+ genel makro), tum BIST dump yok ---
    if db and db.chunks:
        if code:
            # Once bu sembole ait chunk'lar
            sym_chunks = [
                c
                for c in db.chunks
                if (c.get("meta") or {}).get("symbol", "").upper() == code
            ]
            # Makro (sembol etiketsiz evds) — en fazla 1
            macro = [
                c
                for c in db.chunks
                if (c.get("meta") or {}).get("type", "").startswith("evds")
            ][:1]
            # Semantic sadece sembol filtresi icinde
            try:
                hits = db.search(question, k=6)
            except Exception:
                hits = []
            filtered_hits = [
                h
                for h in hits
                if (h.get("meta") or {}).get("symbol", "").upper() in ("", code)
                or (h.get("meta") or {}).get("type", "").startswith("evds")
            ]
            # Birlestir, tekrar yok (text'e gore)
            seen_txt = set()
            for c in sym_chunks + macro + filtered_hits:
                t = c.get("text") or ""
                if t and t not in seen_txt:
                    # Canliyi zaten ekledik; index'teki eski stock canlisini atla
                    mtype = (c.get("meta") or {}).get("type", "")
                    if mtype == "stock" and code:
                        continue
                    seen_txt.add(t)
                    context_parts.append(t)
                    sources.append(
                        (c.get("meta") or {}).get("symbol")
                        or (c.get("meta") or {}).get("type")
                        or "rag"
                    )
        else:
            # Sembol yoksa: semantik top-k ama her chunk tek sembol kalsin
            for h in db.search(question, k=3):
                context_parts.append(h["text"])
                sources.append(
                    (h.get("meta") or {}).get("symbol")
                    or (h.get("meta") or {}).get("type")
                    or "rag"
                )

    context = "\n\n".join(context_parts)
    if not context.strip():
        print("Context bos — sembol belirt (orn. THYAO analiz) veya build calistir")
        return {"veri_eksik": True, "hata": "context_bos"}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tarih=BUGUN)},
        {
            "role": "user",
            "content": (
                f"GUNCEL VERILER ({BUGUN}) — SADECE asagidaki hisse/baglam:\n"
                f"{context}\n\n"
                f"SORU: {question}\n"
                "JSON alanlarina context'teki guncel_fiyat_TL, guncel_fk, "
                "guncel_piyasa_degeri_USD, temettu_verimi_pct, CAGR/toplam_getiri degerlerini yaz. "
                "teknik_yorum icin context'teki SMA20, SMA50, SMA200, Trend, 1 ay/3 ay getirilerini kullan. "
                "Yorumda baska hisse ekleme."
            ),
        },
    ]

    print(f"\nSoru: {question}")
    print(f"Sembol: {code or 'belirsiz'}")
    print(f"Kaynak: {', '.join(dict.fromkeys(str(s) for s in sources))}")
    print("-" * 50)

    model_name = resolve_ollama_model()
    result = ollama.chat(
        model=model_name,
        messages=messages,
        format=FinansalAnaliz.model_json_schema(),
        options={
            "temperature": float(INFER_CFG["temperature"]),
            "num_predict": max(int(INFER_CFG["num_predict"]), 500),
            "top_p": float(INFER_CFG["top_p"]),
            "repeat_penalty": float(INFER_CFG["repeat_penalty"]),
        },
    )
    ham_cevap = result["message"]["content"]

    try:
        analiz = FinansalAnaliz.model_validate_json(ham_cevap)
        cevap = analiz.model_dump()
    except Exception as e:
        print(f"\n[UYARI] Model semaya uygun JSON dondurmedi ({e}). Ham cikti:")
        print(ham_cevap)
        cevap = {
            "veri_eksik": True,
            "hata": "Model gecerli JSON uretemedi",
            "ham_cikti": ham_cevap,
            "sirket": code or "",
            "teknik_yorum": "",
            "temel_yorum": "",
            "riskler": "",
        }

    # KRITIK: sayilari Python ezer (null / yanlis model ciktisi duzelir)
    cevap = fill_from_python(cevap, live, growth)
    print(f"\n{json.dumps(cevap, ensure_ascii=False, indent=2)}")
    return cevap


def cli():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "build":
            build_index()
        elif cmd == "top":
            # --live flag kontrolu
            live = "--live" in sys.argv
            # market kontrolu (--tr, --us)
            market = "BIST"  # default
            for a in sys.argv[2:]:
                if a == "--us":
                    market = "US"
                elif a == "--tr":
                    market = "BIST"
            # numeric args
            args = [a for a in sys.argv[2:] if a not in ("--live", "--tr", "--us")]
            n = int(args[0]) if args else 10
            min_cagr = float(args[1]) if len(args) > 1 else 15.0
            top_performers(n, min_cagr, live, market)
        else:
            sor(" ".join(sys.argv[1:]))
    else:
        db = VectorDB()
        if not db.load():
            print("Ilk kullanim: python src/rag_pipeline.py build")
            return
        print("\nBorsa RAG (q cikis)")
        while True:
            q = input("\nSoru: ").strip()
            if q.lower() in ("q", "quit", "exit"):
                break
            sor(q, db)


if __name__ == "__main__":
    cli()
