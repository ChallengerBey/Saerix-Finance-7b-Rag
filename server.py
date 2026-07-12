"""
Borsa Bot v3.0 — FastAPI Backend
Mevcut analiz mantığını (borsa_logic, borsa_simulation) web API'sine çevirir
ve Electron arayüzünü statik dosya olarak sunar.
"""

import os
import argparse
import asyncio
import json
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# Suppress yfinance internal logging noise - must be before borsa_logic import
os.environ["YFINANCE_LOG_LEVEL"] = "CRITICAL"
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.utils").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.data").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.ticker").setLevel(logging.CRITICAL)

from borsa_logic import analyze_stock, get_stock_data, calculate_indicators, get_signal_score
from borsa_simulation import run_simulation, monte_carlo_simulation, calculate_historical_returns

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ELECTRON_DIR = os.path.join(BASE_DIR, "electron")

app = FastAPI(title="Borsa Bot API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ───
_df_cache: dict[str, pd.DataFrame] = {}
_ws_clients: Set[WebSocket] = set()
_subscriptions: Dict[WebSocket, Set[str]] = {}
_price_cache: Dict[str, dict] = {}
_cache_ttl = 30  # seconds

# ─── Helpers ───

def _df_to_chart(df: pd.DataFrame):
    if df is None or df.empty:
        return None
    d = df.tail(90)

    def col(name):
        if name in d.columns:
            return [None if pd.isna(x) else round(float(x), 4) for x in d[name].tolist()]
        return [None] * len(d)

    dates = [str(x.date()) for x in d.index]
    return {
        "dates": dates,
        "close": col("Close"),
        "sma20": col("SMA20"),
        "sma50": col("SMA50"),
        "bb_upper": col("BB_Upper"),
        "bb_lower": col("BB_Lower"),
        "rsi": col("RSI"),
        "macd": col("MACD"),
        "macd_signal": col("MACD_Signal"),
        "macd_hist": col("MACD_Hist"),
    }


def _serialize(obj):
    """NumPy/pandas tiplerini JSON-serileştirilebilir hale getir."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if pd.isna(obj):
        return None
    return obj


async def _fetch_live_price(ticker: str) -> dict:
    """yfinance'den anlık fiyat çek (cache'li)."""
    now = datetime.now().timestamp()
    cached = _price_cache.get(ticker)
    if cached and now - cached["ts"] < _cache_ttl:
        return cached["data"]

    try:
        df_raw, full_ticker, _ = get_stock_data(ticker)
        if df_raw is None or df_raw.empty:
            return {"error": "Veri yok"}
        last = df_raw.iloc[-1]
        prev = df_raw.iloc[-2] if len(df_raw) > 1 else last
        change = float(last["Close"]) - float(prev["Close"])
        change_pct = (change / float(prev["Close"])) * 100 if float(prev["Close"]) else 0
        data = {
            "ticker": full_ticker,
            "price": round(float(last["Close"]), 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": int(last.get("Volume", 0)),
            "high": round(float(last.get("High", 0)), 2),
            "low": round(float(last.get("Low", 0)), 2),
            "open": round(float(last.get("Open", 0)), 2),
            "ts": now,
        }
        _price_cache[ticker] = {"ts": now, "data": data}
        return data
    except Exception as e:
        return {"error": str(e)}


async def _broadcast_prices():
    """Abone olan WS client'larına fiyat güncellemesi gönder."""
    if not _ws_clients:
        return
    tickers = set()
    for subs in _subscriptions.values():
        tickers.update(subs)
    if not tickers:
        return
    prices = {}
    for t in tickers:
        prices[t] = await _fetch_live_price(t)
    msg = json.dumps({"type": "prices", "data": prices})
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)
        _subscriptions.pop(ws, None)


async def _price_loop():
    """Periyodik fiyat yayını."""
    while True:
        await asyncio.sleep(5)
        await _broadcast_prices()


# ─── WebSocket ───

@app.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    _subscriptions[ws] = set()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("action") == "subscribe":
                    for t in msg.get("tickers", []):
                        _subscriptions[ws].add(t.strip().upper())
                elif msg.get("action") == "unsubscribe":
                    for t in msg.get("tickers", []):
                        _subscriptions[ws].discard(t.strip().upper())
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)
        _subscriptions.pop(ws, None)


# ─── REST Endpoints ───

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "4.0"}


@app.get("/api/analyze")
def analyze(ticker: str = Query(..., min_length=1)):
    ticker = ticker.strip().upper()
    result = analyze_stock(ticker)

    if not result.get("success"):
        return JSONResponse(
            status_code=200,
            content={"success": False, "ticker": ticker, "error": result.get("error", "Bilinmeyen hata")},
        )

    df = result.pop("df", None)
    result["chart"] = _df_to_chart(df)

    if df is not None:
        _df_cache[ticker] = df

    return JSONResponse(status_code=200, content=_serialize(result))


@app.get("/api/simulate")
def simulate(ticker: str = Query(...), amount: float = Query(...)):
    ticker = ticker.strip().upper()
    df = _df_cache.get(ticker)

    if df is None:
        try:
            df_raw, _, _ = get_stock_data(ticker)
            df = calculate_indicators(df_raw)
        except Exception as e:
            return JSONResponse(
                status_code=200,
                content={"success": False, "error": f"Simülasyon için veri alınamadı: {e}"},
            )

    sim = run_simulation(df, amount)
    return JSONResponse(status_code=200, content=_serialize({"success": True, **sim}))


@app.get("/api/quote")
async def quote(tickers: str = Query(..., description="Virgülle ayrılmış hisse kodları")):
    """Toplu anlık fiyat (watchlist/portföy için)."""
    syms = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    results = {}
    for s in syms:
        results[s] = await _fetch_live_price(s)
    return JSONResponse(content=_serialize(results))


@app.get("/api/heatmap")
async def heatmap(index: str = Query("BIST100", description="BIST100, BIST30, SECTOR")):
    """Sektör/Endeks ısı haritası verisi."""
    bist100 = [
        "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "ASELS", "TUPRS", "KCHOL",
        "TOASO", "FROTO", "BIMAS", "SAHOL", "KOZAA", "KOZAL", "EREGL", "PETKM",
        "TCELL", "ARCLK", "FROTO", "SAHOL", "EKGYO", "ULKER", "KRDMD", "HEKTS",
        "MGROS", "VESTL", "CIMSA", "GOODY", "BRISA", "TUPRS", "KCHOL", "SISE"
    ][:20]  # Demo için 20

    # Paralel fetch
    tasks = [_fetch_live_price(sym) for sym in bist100]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    data = []
    for sym, q in zip(bist100, results):
        if isinstance(q, dict) and "error" not in q:
            data.append({
                "symbol": sym,
                "price": q["price"],
                "change_pct": q["change_pct"],
                "volume": q["volume"],
            })
    return JSONResponse(content=_serialize({"index": index, "stocks": data, "ts": datetime.now().timestamp()}))


# ─── Backtest Engine ───

class BacktestEngine:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 100000):
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0
        self.entry_price = 0
        self.trades = []
        self.equity_curve = []

    def run(self, strategy_fn):
        """strategy_fn(row, i, df) -> 'buy' | 'sell' | 'hold'"""
        for i in range(1, len(self.df)):
            row = self.df.iloc[i]
            signal = strategy_fn(row, i, self.df)

            price = float(row["Close"])

            if signal == "buy" and self.position == 0:
                self.position = self.capital / price
                self.entry_price = price
                self.capital = 0
                self.trades.append({"type": "buy", "price": price, "date": str(row.name.date()), "shares": self.position})
            elif signal == "sell" and self.position > 0:
                self.capital = self.position * price
                pnl = (price - self.entry_price) * self.position
                pnl_pct = (price - self.entry_price) / self.entry_price * 100
                self.trades.append({"type": "sell", "price": price, "date": str(row.name.date()), "pnl": pnl, "pnl_pct": pnl_pct})
                self.position = 0
                self.entry_price = 0

            # Equity
            equity = self.capital + (self.position * price if self.position else 0)
            self.equity_curve.append({"date": str(row.name.date()), "equity": round(equity, 2)})

        # Final close
        if self.position > 0:
            price = float(self.df.iloc[-1]["Close"])
            self.capital = self.position * price
            self.position = 0

        return self._results()

    def _results(self):
        if not self.trades:
            return {"error": "İşlem yok"}

        sells = [t for t in self.trades if t["type"] == "sell"]
        wins = [t for t in sells if t.get("pnl", 0) > 0]
        losses = [t for t in sells if t.get("pnl", 0) <= 0]

        total_return = (self.capital - self.initial_capital) / self.initial_capital * 100
        win_rate = len(wins) / len(sells) * 100 if sells else 0
        avg_win = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
        avg_loss = np.mean([t["pnl_pct"] for t in losses]) if losses else 0
        profit_factor = abs(sum(t["pnl"] for t in wins) / sum(t["pnl"] for t in losses)) if losses else float("inf")

        # Max drawdown
        equity_vals = [e["equity"] for e in self.equity_curve]
        peak = equity_vals[0]
        max_dd = 0
        for v in equity_vals:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return {
            "initial_capital": self.initial_capital,
            "final_capital": round(self.capital, 2),
            "total_return_pct": round(total_return, 2),
            "total_trades": len(sells),
            "win_rate": round(win_rate, 1),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
            "max_drawdown_pct": round(max_dd, 2),
            "trades": self.trades,
            "equity_curve": self.equity_curve,
        }


# Built-in strategies
def strategy_rsi_bb(row, i, df):
    rsi = row.get("RSI", 50)
    close = row["Close"]
    bb_lower = row.get("BB_Lower", 0)
    bb_upper = row.get("BB_Upper", 0)
    if rsi < 30 and close <= bb_lower * 1.01:
        return "buy"
    if rsi > 70 and close >= bb_upper * 0.99:
        return "sell"
    return "hold"


def strategy_macd_cross(row, i, df):
    macd = row.get("MACD", 0)
    signal = row.get("MACD_Signal", 0)
    prev_macd = df.iloc[i-1].get("MACD", 0) if i > 0 else macd
    prev_signal = df.iloc[i-1].get("MACD_Signal", 0) if i > 0 else signal
    if prev_macd <= prev_signal and macd > signal:
        return "buy"
    if prev_macd >= prev_signal and macd < signal:
        return "sell"
    return "hold"


def strategy_sma_cross(row, i, df):
    sma20 = row.get("SMA20", 0)
    sma50 = row.get("SMA50", 0)
    prev_sma20 = df.iloc[i-1].get("SMA20", 0) if i > 0 else sma20
    prev_sma50 = df.iloc[i-1].get("SMA50", 0) if i > 0 else sma50
    if prev_sma20 <= prev_sma50 and sma20 > sma50:
        return "buy"
    if prev_sma20 >= prev_sma50 and sma20 < sma50:
        return "sell"
    return "hold"


STRATEGIES = {
    "rsi_bb": strategy_rsi_bb,
    "macd_cross": strategy_macd_cross,
    "sma_cross": strategy_sma_cross,
}


@app.get("/api/backtest")
def backtest(
    ticker: str = Query(...),
    strategy: str = Query("rsi_bb"),
    capital: float = Query(100000),
):
    ticker = ticker.strip().upper()
    try:
        df_raw, full_ticker, _ = get_stock_data(ticker)
        df = calculate_indicators(df_raw)
        if df is None or df.empty:
            return JSONResponse(content={"success": False, "error": "Veri yok"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=200)

    strat_fn = STRATEGIES.get(strategy)
    if not strat_fn:
        return JSONResponse(content={"success": False, "error": f"Strateji yok: {strategy}"}, status_code=200)

    engine = BacktestEngine(df, capital)
    result = engine.run(strat_fn)
    return JSONResponse(content=_serialize({"success": True, "ticker": full_ticker, "strategy": strategy, **result}))


# ─── Risk Metrics ───

def calculate_risk_metrics(df: pd.DataFrame, risk_free_rate: float = 0.05) -> dict:
    """VaR, Sharpe, Sortino, MaxDD, Corelasyon."""
    returns = df["Close"].pct_change().dropna()
    if len(returns) < 20:
        return {"error": "Yetersiz veri"}

    # Daily metrics
    mean_ret = returns.mean()
    std_ret = returns.std()
    downside = returns[returns < 0].std() or std_ret

    # Annualized
    ann_mean = mean_ret * 252
    ann_std = std_ret * np.sqrt(252)
    ann_downside = downside * np.sqrt(252)

    sharpe = (ann_mean - risk_free_rate) / ann_std if ann_std else 0
    sortino = (ann_mean - risk_free_rate) / ann_downside if ann_downside else 0

    # VaR 95% (historical)
    var_95 = np.percentile(returns, 5) * 100
    var_99 = np.percentile(returns, 1) * 100

    # Max Drawdown
    cum = (1 + returns).cumprod()
    peak = cum.expanding().max()
    dd = (cum - peak) / peak
    max_dd = dd.min() * 100

    # Calmar
    calmar = (ann_mean / abs(max_dd / 100)) if max_dd != 0 else 0

    return {
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "calmar": round(calmar, 2),
        "var_95_pct": round(var_95, 2),
        "var_99_pct": round(var_99, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "annual_return_pct": round(ann_mean * 100, 2),
        "annual_vol_pct": round(ann_std * 100, 2),
        "downside_vol_pct": round(ann_downside * 100, 2),
    }


@app.get("/api/risk")
def risk_metrics(ticker: str = Query(...), risk_free: float = Query(0.05)):
    ticker = ticker.strip().upper()
    try:
        df_raw, full_ticker, _ = get_stock_data(ticker)
        df = calculate_indicators(df_raw)
        metrics = calculate_risk_metrics(df, risk_free)
        return JSONResponse(content=_serialize({"success": True, "ticker": full_ticker, **metrics}))
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=200)


# ─── Correlation Matrix ───

@app.get("/api/correlation")
def correlation(tickers: str = Query(...), period: str = Query("6mo")):
    """Portföy/değişkenler arası korelasyon matrisi."""
    syms = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    if len(syms) < 2:
        return JSONResponse(content={"success": False, "error": "En az 2 hisse gerekli"}, status_code=200)

    try:
        closes = {}
        for s in syms:
            df_raw, full_s, _ = get_stock_data(s)
            df = calculate_indicators(df_raw)
            if df is not None and not df.empty:
                closes[full_s] = df["Close"]
        if len(closes) < 2:
            return JSONResponse(content={"success": False, "error": "Veri alınamadı"}, status_code=200)

        combined = pd.DataFrame(closes).dropna()
        corr = combined.pct_change().dropna().corr()
        return JSONResponse(content=_serialize({"success": True, "symbols": list(corr.columns), "matrix": corr.round(4).values.tolist()}))
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=200)


# ─── AI Portfolio Suggestion ───

@app.get("/api/ai/portfolio")
def ai_portfolio(
    budget: float = Query(...),
    risk: str = Query("medium", description="low|medium|high"),
    count: int = Query(5, ge=3, le=15),
):
    """Risk profiline göre AI portföy önerisi."""
    # BIST likit hisseler havuzu
    pool = [
        "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "ASELS", "TUPRS", "KCHOL",
        "TOASO", "FROTO", "BIMAS", "SAHOL", "KOZAA", "EREGL", "PETKM", "TCELL",
        "ARCLK", "EKGYO", "ULKER", "KRDMD", "MGROS", "VESTL", "CIMSA", "GOODY",
        "BRISA", "SISE", "HEKTS", "DOAS", "TKFEN", "TTKOM",
    ]

    # Risk profiline göre filtre (basit proxy: beta/volatilite)
    # Gerçek impl: her hisse için risk metrikleri çekip optimize et
    # Şimdilik: low -> büyük bankalar/holding, high -> small cap/volatile
    if risk == "low":
        selected = pool[:count]  # Blue chip
    elif risk == "high":
        selected = pool[-count:]  # Daha volatile
    else:
        selected = pool[count//2:count//2+count]

    # Basit eşit ağırlık (gerçek: mean-variance optimization)
    weight = 1.0 / len(selected)
    allocation = budget * weight

    # Her hisse için hızlı analiz
    suggestions = []
    for sym in selected:
        try:
            df_raw, full_s, _ = get_stock_data(sym)
            df = calculate_indicators(df_raw)
            last = df.iloc[-1]
            signal = get_signal_score(
                float(last["Close"]), float(last["RSI"]), float(last["SMA20"]), float(last["SMA50"]),
                float(last["MACD"]), float(last["MACD_Signal"]), float(last["BB_Upper"]), float(last["BB_Lower"])
            )
            suggestions.append({
                "symbol": full_s,
                "weight_pct": round(weight * 100, 1),
                "allocation": round(allocation, 2),
                "signal_score": signal["score"],
                "signal_text": signal["text"],
                "price": round(float(last["Close"]), 2),
            })
        except Exception:
            continue

    return JSONResponse(content=_serialize({
        "success": True,
        "budget": budget,
        "risk_profile": risk,
        "count": len(suggestions),
        "suggestions": suggestions,
        "disclaimer": "Bu bir yatırım tavsiyesi değildir. Kendi araştırmanızı yapın."
    }))


# ─── Strategies List ───

@app.get("/api/strategies")
def list_strategies():
    """Mevcut backtest stratejileri."""
    return JSONResponse(content={
        "success": True,
        "strategies": [
            {"id": "rsi_bb", "name": "RSI + Bollinger Bands", "desc": "RSI <30 & alt banda yakın → AL, RSI >70 & üst banda yakın → SAT"},
            {"id": "macd_cross", "name": "MACD Cross", "desc": "MACD sinyal çizgisini yukarı/aşağı kesen"},
            {"id": "sma_cross", "name": "SMA Cross (20/50)", "desc": "SMA20 SMA50'yi yukarı/aşağı kesen (Golden/Death Cross)"},
        ]
    })


# ─── Earnings Calendar (Mock - gerçek API entegrasyonu gerekir) ───

@app.get("/api/earnings")
def earnings_calendar(ticker: str = Query(None)):
    """Bilanço takvimi (mock veri - gerçek için Alpha Vantage/Twelve Data gerekir)."""
    # Placeholder
    return JSONResponse(content={"success": True, "data": [], "note": "Gerçek veri için Alpha Vantage/Twelve Data API key gerekir"})


# ─── Statik Arayüz ───
if os.path.isdir(ELECTRON_DIR):
    app.mount("/", StaticFiles(directory=ELECTRON_DIR, html=True), name="ui")


def main():
    parser = argparse.ArgumentParser(description="Borsa Bot API Sunucusu")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    import uvicorn
    # Start background price loop
    import threading
    def run_loop():
        asyncio.run(_price_loop())
    threading.Thread(target=run_loop, daemon=True).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
