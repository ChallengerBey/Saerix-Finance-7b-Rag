"""
Borsa Bot v3.0 — Ana Mantık Katmanı
Teknik analiz, sinyal sistemi, şirket bilgileri, haberler, hedef fiyat ve AI yorumu.
"""

import os
import logging

# Suppress yfinance internal logging noise - must be before yfinance import
os.environ["YFINANCE_LOG_LEVEL"] = "CRITICAL"
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.utils").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.data").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.ticker").setLevel(logging.CRITICAL)

import yfinance as yf
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from borsa_simulation import run_simulation

# .env dosyasından API anahtarını yükle
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ═══════════════════════════════════════════════════
#  VERİ ÇEKME
# ═══════════════════════════════════════════════════

def get_stock_data(ticker):
    """Hisse senedi verilerini çeker.

    Türk hisseleri için otomatik olarak '.IS' ekler: önce kod olduğu gibi
    denenir, veri gelmezse '.IS' son ekiyle tekrar denenir. Böylece hem
    THYAO (BIST) hem de AAPL, TSLA gibi yabancı hisseler çalışır.
    """
    ticker = ticker.strip()

    # Nokta içeriyorsa (THYAO.IS, BRK.B vb.) doğrudan kullan
    if "." in ticker:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            if df.empty:
                return None, ticker, stock
            return df, ticker, stock
        except Exception as e:
            raise ConnectionError(f"Veri çekme hatası: {str(e)}")

    # 1) Olduğu gibi dene (yabancı hisse: AAPL, TSLA ...)
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        if not df.empty:
            return df, ticker, stock
    except Exception:
        pass  # sessizce .IS denemeye geç

    # 2) Türk hissesi olabilir, '.IS' ekiyle dene
    ticker_is = ticker + ".IS"
    try:
        stock = yf.Ticker(ticker_is)
        df = stock.history(period="6mo")
        if df.empty:
            return None, ticker_is, stock
        return df, ticker_is, stock
    except Exception as e:
        raise ConnectionError(f"Veri çekme hatası: {str(e)}")


# ═══════════════════════════════════════════════════
#  TEKNİK GÖSTERGELER
# ═══════════════════════════════════════════════════

def calculate_indicators(df):
    """Teknik göstergeleri hesaplar (RSI, SMA, MACD, Bollinger Bands)."""
    if df is None or df.empty:
        return None

    # SMA (Simple Moving Average)
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()

    # RSI (Relative Strength Index)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD (Moving Average Convergence Divergence)
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)

    return df


def get_rsi_status(rsi):
    """RSI değerine göre durum döndürür."""
    if rsi >= 70:
        return "Aşırı Alım", "#ff4757"
    elif rsi <= 30:
        return "Aşırı Satım", "#2ed573"
    elif rsi >= 60:
        return "Alım Bölgesi", "#ffa502"
    elif rsi <= 40:
        return "Satım Bölgesi", "#3742fa"
    else:
        return "Nötr", "#a4b0be"


def get_trend_status(current_price, sma20, sma50):
    """Fiyat-SMA ilişkisine göre trend durumu döndürür."""
    if current_price > sma20 > sma50:
        return "Güçlü Yükseliş", "#2ed573"
    elif current_price > sma20:
        return "Yükseliş", "#7bed9f"
    elif current_price < sma20 < sma50:
        return "Güçlü Düşüş", "#ff4757"
    elif current_price < sma20:
        return "Düşüş", "#ff6b81"
    else:
        return "Yatay", "#a4b0be"


# ═══════════════════════════════════════════════════
#  SİNYAL SİSTEMİ (AL / SAT / BEKLE)
# ═══════════════════════════════════════════════════

def get_signal_score(price, rsi, sma20, sma50, macd, macd_signal, bb_upper, bb_lower):
    """
    Teknik göstergelere dayalı puan tabanlı AL/SAT sinyal sistemi.
    0-100 arası skor döndürür.
    """
    total_points = 0
    details = []

    # ─── RSI Sinyali (±25 puan) ───
    if rsi < 30:
        pts = 25
        signal = "GÜÇLÜ AL"
        reason = f"RSI {rsi:.1f} — Aşırı satım bölgesi, toparlanma beklenir"
        color = "#2ed573"
    elif rsi < 40:
        pts = 15
        signal = "AL"
        reason = f"RSI {rsi:.1f} — Satım bölgesinde, dipten dönüş olabilir"
        color = "#7bed9f"
    elif rsi > 70:
        pts = -25
        signal = "GÜÇLÜ SAT"
        reason = f"RSI {rsi:.1f} — Aşırı alım bölgesi, düzeltme gelebilir"
        color = "#ff4757"
    elif rsi > 60:
        pts = -15
        signal = "SAT"
        reason = f"RSI {rsi:.1f} — Alım bölgesinde, dikkatli ol"
        color = "#ff6b81"
    else:
        pts = 0
        signal = "NÖTR"
        reason = f"RSI {rsi:.1f} — Nötr bölgede"
        color = "#ffa502"

    total_points += pts
    details.append({'name': 'RSI (14)', 'signal': signal, 'color': color, 'reason': reason, 'points': pts})

    # ─── SMA Sinyali (±25 puan) ───
    if price > sma20 > sma50:
        pts = 25
        signal = "GÜÇLÜ AL"
        reason = "Golden Cross — Fiyat > SMA20 > SMA50, güçlü yükseliş trendi"
        color = "#2ed573"
    elif price > sma20:
        pts = 10
        signal = "AL"
        reason = "Fiyat SMA20 üzerinde, kısa vadeli yükseliş"
        color = "#7bed9f"
    elif price < sma20 < sma50:
        pts = -25
        signal = "GÜÇLÜ SAT"
        reason = "Death Cross — Fiyat < SMA20 < SMA50, güçlü düşüş trendi"
        color = "#ff4757"
    elif price < sma20:
        pts = -10
        signal = "SAT"
        reason = "Fiyat SMA20 altında, kısa vadeli düşüş"
        color = "#ff6b81"
    else:
        pts = 0
        signal = "NÖTR"
        reason = "Fiyat ortalamalara yakın"
        color = "#ffa502"

    total_points += pts
    details.append({'name': 'SMA (20/50)', 'signal': signal, 'color': color, 'reason': reason, 'points': pts})

    # ─── MACD Sinyali (±25 puan) ───
    if macd > macd_signal:
        diff_pct = abs(macd - macd_signal) / abs(macd_signal) * 100 if macd_signal != 0 else 0
        if diff_pct > 20:
            pts = 25
            signal = "GÜÇLÜ AL"
            reason = "MACD signal üzerinde ve ayrışma güçlü"
            color = "#2ed573"
        else:
            pts = 15
            signal = "AL"
            reason = "MACD signal üzerinde, momentum pozitif"
            color = "#7bed9f"
    else:
        diff_pct = abs(macd - macd_signal) / abs(macd_signal) * 100 if macd_signal != 0 else 0
        if diff_pct > 20:
            pts = -25
            signal = "GÜÇLÜ SAT"
            reason = "MACD signal altında ve ayrışma güçlü"
            color = "#ff4757"
        else:
            pts = -15
            signal = "SAT"
            reason = "MACD signal altında, momentum negatif"
            color = "#ff6b81"

    total_points += pts
    details.append({'name': 'MACD', 'signal': signal, 'color': color, 'reason': reason, 'points': pts})

    # ─── Bollinger Sinyali (±25 puan) ───
    bb_range = bb_upper - bb_lower
    if bb_range > 0:
        bb_position = (price - bb_lower) / bb_range  # 0 = alt band, 1 = üst band
    else:
        bb_position = 0.5

    if bb_position < 0.1:
        pts = 25
        signal = "GÜÇLÜ AL"
        reason = f"Fiyat alt Bollinger bandına çok yakın (%{bb_position*100:.0f}), sıçrama beklenir"
        color = "#2ed573"
    elif bb_position < 0.3:
        pts = 15
        signal = "AL"
        reason = f"Fiyat alt bölgede (%{bb_position*100:.0f})"
        color = "#7bed9f"
    elif bb_position > 0.9:
        pts = -25
        signal = "GÜÇLÜ SAT"
        reason = f"Fiyat üst Bollinger bandına çok yakın (%{bb_position*100:.0f}), düzeltme gelebilir"
        color = "#ff4757"
    elif bb_position > 0.7:
        pts = -15
        signal = "SAT"
        reason = f"Fiyat üst bölgede (%{bb_position*100:.0f})"
        color = "#ff6b81"
    else:
        pts = 0
        signal = "NÖTR"
        reason = f"Fiyat bantların ortasında (%{bb_position*100:.0f})"
        color = "#ffa502"

    total_points += pts
    details.append({'name': 'Bollinger', 'signal': signal, 'color': color, 'reason': reason, 'points': pts})

    # ─── Toplam Skor (0-100) ───
    # total_points aralığı: -100 ile +100. Bunu 0-100'e çeviriyoruz.
    score = int(max(0, min(100, 50 + total_points / 2)))

    # Sinyal metni
    if score >= 80:
        text, color, emoji = "GÜÇLÜ AL", "#2ed573", "💚"
    elif score >= 60:
        text, color, emoji = "AL", "#7bed9f", "🟢"
    elif score >= 40:
        text, color, emoji = "BEKLE", "#ffa502", "🟡"
    elif score >= 20:
        text, color, emoji = "SAT", "#ff6b81", "🔴"
    else:
        text, color, emoji = "GÜÇLÜ SAT", "#ff4757", "❤️‍🔥"

    return {
        'score': score,
        'text': text,
        'color': color,
        'emoji': emoji,
        'details': details,
    }


# ═══════════════════════════════════════════════════
#  ŞİRKET BİLGİLERİ
# ═══════════════════════════════════════════════════

def get_company_info(ticker_obj):
    """yfinance'dan şirket bilgilerini çeker."""
    try:
        info = ticker_obj.info
        return {
            'name': info.get('longName', info.get('shortName', 'Bilinmiyor')),
            'sector': info.get('sector', 'Bilinmiyor'),
            'industry': info.get('industry', 'Bilinmiyor'),
            'employees': info.get('fullTimeEmployees', 0),
            'market_cap': info.get('marketCap', 0),
            'pe_ratio': info.get('trailingPE', 0),
            'forward_pe': info.get('forwardPE', 0),
            'dividend_yield': info.get('dividendYield', 0),
            'week52_high': info.get('fiftyTwoWeekHigh', 0),
            'week52_low': info.get('fiftyTwoWeekLow', 0),
            'avg_volume': info.get('averageVolume', 0),
            'description': (info.get('longBusinessSummary', '') or '')[:500],
            'currency': info.get('currency', 'TRY'),
            'exchange': info.get('exchange', ''),
            'website': info.get('website', ''),
        }
    except Exception as e:
        return {
            'name': 'Bilinmiyor', 'sector': '-', 'industry': '-',
            'employees': 0, 'market_cap': 0, 'pe_ratio': 0,
            'forward_pe': 0, 'dividend_yield': 0,
            'week52_high': 0, 'week52_low': 0, 'avg_volume': 0,
            'description': f'Şirket bilgileri alınamadı: {str(e)}',
            'currency': 'TRY', 'exchange': '', 'website': '',
        }


# ═══════════════════════════════════════════════════
#  HABERLER
# ═══════════════════════════════════════════════════

def get_news(ticker_obj):
    """yfinance'dan şirketle ilgili son haberleri çeker."""
    try:
        news_list = ticker_obj.news
        if not news_list:
            return []

        results = []
        for item in news_list[:10]:
            content = item.get('content', {})
            results.append({
                'title': content.get('title', item.get('title', 'Başlık yok')),
                'publisher': content.get('provider', {}).get('displayName', item.get('publisher', 'Bilinmiyor')),
                'link': content.get('canonicalUrl', {}).get('url', item.get('link', '#')),
                'date': content.get('pubDate', item.get('providerPublishTime', '')),
            })

        return results
    except Exception:
        return []


# ═══════════════════════════════════════════════════
#  FİYAT HEDEFLERİ & ANALİST GÖRÜŞLERİ
# ═══════════════════════════════════════════════════

def get_price_targets(ticker_obj, current_price):
    """Analist hedef fiyatlarını ve tavsiyeleri çeker."""
    result = {
        'low': 0, 'median': 0, 'high': 0, 'mean': 0,
        'current': current_price, 'potential_pct': 0,
        'analyst_count': 0,
        'recommendations': {
            'strongBuy': 0, 'buy': 0, 'hold': 0, 'sell': 0, 'strongSell': 0
        },
        'available': False,
    }

    try:
        # Analist hedef fiyatları
        targets = ticker_obj.analyst_price_targets
        if targets is not None:
            if isinstance(targets, dict):
                result['low'] = targets.get('low', 0) or 0
                result['median'] = targets.get('median', 0) or 0
                result['high'] = targets.get('high', 0) or 0
                result['mean'] = targets.get('mean', 0) or 0
            elif hasattr(targets, 'low'):
                result['low'] = getattr(targets, 'low', 0) or 0
                result['median'] = getattr(targets, 'median', 0) or 0
                result['high'] = getattr(targets, 'high', 0) or 0
                result['mean'] = getattr(targets, 'mean', 0) or 0

            if result['median'] > 0 and current_price > 0:
                result['potential_pct'] = ((result['median'] - current_price) / current_price) * 100
                result['available'] = True
    except Exception:
        pass

    try:
        # Analist tavsiyeleri
        recs = ticker_obj.recommendations_summary
        if recs is not None and not recs.empty:
            last_rec = recs.iloc[-1] if len(recs) > 0 else recs.iloc[0]
            result['recommendations'] = {
                'strongBuy': int(last_rec.get('strongBuy', 0)),
                'buy': int(last_rec.get('buy', 0)),
                'hold': int(last_rec.get('hold', 0)),
                'sell': int(last_rec.get('sell', 0)),
                'strongSell': int(last_rec.get('strongSell', 0)),
            }
            result['analyst_count'] = sum(result['recommendations'].values())
            if result['analyst_count'] > 0:
                result['available'] = True
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════
#  AI YORUMU (GEMİNİ)
# ═══════════════════════════════════════════════════

def get_comprehensive_ai_advice(ticker, result_dict, currency="TL"):
    """Gemini AI'dan tüm verilere dayalı kapsamlı analiz alır."""
    if not GEMINI_API_KEY:
        return "⚠️ API anahtarı bulunamadı. Lütfen .env dosyasına GEMINI_API_KEY ekleyin."

    model = genai.GenerativeModel('gemini-2.5-flash')

    # Haberleri özetle
    news_text = ""
    if result_dict.get('news'):
        news_titles = [n['title'] for n in result_dict['news'][:5]]
        news_text = "Son Haberler:\n" + "\n".join(f"- {t}" for t in news_titles)

    # Hedef fiyat bilgisi
    target_text = ""
    targets = result_dict.get('targets', {})
    if targets and targets.get('available'):
        target_text = f"""
Analist Hedef Fiyatları:
- Düşük: {targets.get('low', 0):.2f} {currency}
- Medyan: {targets.get('median', 0):.2f} {currency}
- Yüksek: {targets.get('high', 0):.2f} {currency}
- Potansiyel: %{targets.get('potential_pct', 0):.1f}
"""

    # Şirket bilgisi
    company_text = ""
    company = result_dict.get('company', {})
    if company:
        mc = company.get('market_cap', 0)
        mc_str = f"{mc / 1e9:.1f} Milyar {currency}" if mc > 1e9 else f"{mc / 1e6:.0f} Milyon {currency}" if mc > 1e6 else str(mc)
        company_text = f"""
Şirket: {company.get('name', '')}
Sektör: {company.get('sector', '')} / {company.get('industry', '')}
Piyasa Değeri: {mc_str}
F/K Oranı: {company.get('pe_ratio', 0):.2f}
"""

    # Sinyal bilgisi
    signal = result_dict.get('signal', {})
    signal_text = f"Sinyal Skoru: {signal.get('score', 50)}/100 ({signal.get('text', 'BEKLE')})"

    prompt = f"""
    Sen tecrübeli bir borsa analistisin. {ticker} hissesi için kapsamlı bir analiz raporu hazırla.
    Lütfen bir arkadaşına tavsiye veriyormuş gibi samimi bir dil kullan. Emoji kullan.
    
    TEKNİK VERİLER:
    - Güncel Fiyat: {result_dict.get('price', 0):.2f} {currency}
    - Değişim: %{result_dict.get('change_pct', 0):.2f}
    - RSI (14): {result_dict.get('rsi', 0):.2f} ({result_dict.get('rsi_status', '')})
    - SMA 20: {result_dict.get('sma20', 0):.2f}
    - SMA 50: {result_dict.get('sma50', 0):.2f}
    - MACD: {result_dict.get('macd', 0):.4f}
    - MACD Signal: {result_dict.get('macd_signal', 0):.4f}
    - Trend: {result_dict.get('trend', '')}
    - {signal_text}
    
    {company_text}
    {target_text}
    {news_text}
    
    RAPORUNDA ŞU BÖLÜMLER OLSUN:
    
    📊 TEKNİK ANALİZ ÖZETİ
    - RSI, SMA, MACD, Bollinger bazlı değerlendirme
    
    🏢 TEMEL ANALİZ
    - Şirket verileri ve finansal durumu hakkında yorum (varsa)
    
    📰 HABER DEĞERLENDİRMESİ
    - Son haberlerin fiyat üzerindeki olası etkisi (varsa)
    
    🎯 FİYAT HEDEFİ & BEKLENTİ
    - Kısa vadeli (1-2 hafta) ve orta vadeli (1-3 ay) beklenti
    
    ✅ GENEL SONUÇ
    - Net bir değerlendirme: ne yapmalı?
    
    Sonunda "⚠️ Bu bir yatırım tavsiyesi değildir. Kendi araştırmanızı yapınız." uyarısını eklemeyi unutma.
    Cevabını Türkçe yaz.
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ AI yorumu alınırken hata oluştu: {str(e)}"


# ═══════════════════════════════════════════════════
#  ANA ANALİZ FONKSİYONU
# ═══════════════════════════════════════════════════

def analyze_stock(ticker):
    """Tüm analiz sürecini yönetir. Kapsamlı dict döndürür."""
    result = {
        'success': False,
        'ticker': ticker,
        'error': None,
        'price': 0,
        'change': 0,
        'change_pct': 0,
        'rsi': 0,
        'rsi_status': '',
        'rsi_color': '',
        'sma20': 0,
        'sma50': 0,
        'macd': 0,
        'macd_signal': 0,
        'macd_hist': 0,
        'bb_upper': 0,
        'bb_lower': 0,
        'trend': '',
        'trend_color': '',
        'signal': {},
        'company': {},
        'news': [],
        'targets': {},
        'ai_advice': '',
        'df': None,
    }

    try:
        # 1. Veri çek
        df, full_ticker, ticker_obj = get_stock_data(ticker)
        result['ticker'] = full_ticker

        if df is None or df.empty:
            result['error'] = "Hisse verisi bulunamadı. Lütfen kodu kontrol et (örn: THYAO)."
            return result

        # 2. Teknik göstergeleri hesapla
        df = calculate_indicators(df)
        last_row = df.iloc[-1]

        # Fiyat bilgileri
        result['price'] = float(last_row['Close'])
        if len(df) >= 2:
            prev_close = float(df.iloc[-2]['Close'])
            result['change'] = result['price'] - prev_close
            result['change_pct'] = (result['change'] / prev_close) * 100

        # Teknik göstergeler
        result['rsi'] = float(last_row['RSI'])
        result['sma20'] = float(last_row['SMA20'])
        result['sma50'] = float(last_row['SMA50'])
        result['macd'] = float(last_row['MACD'])
        result['macd_signal'] = float(last_row['MACD_Signal'])
        result['macd_hist'] = float(last_row['MACD_Hist'])
        result['bb_upper'] = float(last_row['BB_Upper'])
        result['bb_lower'] = float(last_row['BB_Lower'])

        # Durum yorumları
        rsi_status, rsi_color = get_rsi_status(result['rsi'])
        result['rsi_status'] = rsi_status
        result['rsi_color'] = rsi_color

        trend, trend_color = get_trend_status(result['price'], result['sma20'], result['sma50'])
        result['trend'] = trend
        result['trend_color'] = trend_color

        # 3. Sinyal skoru
        result['signal'] = get_signal_score(
            result['price'], result['rsi'], result['sma20'], result['sma50'],
            result['macd'], result['macd_signal'], result['bb_upper'], result['bb_lower']
        )

        # 4. Şirket bilgileri
        result['company'] = get_company_info(ticker_obj)

        # 5. Haberler
        result['news'] = get_news(ticker_obj)

        # 6. Hedef fiyatlar
        result['targets'] = get_price_targets(ticker_obj, result['price'])

        # 7. DataFrame'i grafik için sakla
        result['df'] = df

        # 8. AI yorumu (en son — tüm verilere ihtiyacı var)
        result['ai_advice'] = get_comprehensive_ai_advice(
            full_ticker, result, result['company'].get('currency', 'TL')
        )

        result['success'] = True

    except ConnectionError as e:
        result['error'] = str(e)
    except Exception as e:
        result['error'] = f"Beklenmeyen hata: {str(e)}"

    return result
