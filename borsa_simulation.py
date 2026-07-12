"""
Borsa Bot v3.0 — Monte Carlo Simülasyon Motoru
Yatırım simülasyonu ve geçmiş performans hesaplama.
"""

import numpy as np
import pandas as pd


def calculate_historical_returns(df, investment_amount):
    """
    Geçmiş performansa göre yatırımın değerini hesapla.
    Son 1 ay, 3 ay ve 6 ay için.
    """
    if df is None or df.empty or len(df) < 5:
        return {}

    current_price = float(df.iloc[-1]['Close'])
    results = {}

    periods = {
        '1_ay': 22,   # ~1 ay iş günü
        '3_ay': 66,   # ~3 ay iş günü
        '6_ay': 132,  # ~6 ay iş günü
    }

    for period_name, days in periods.items():
        if len(df) >= days:
            past_price = float(df.iloc[-days]['Close'])
            return_pct = ((current_price - past_price) / past_price) * 100
            current_value = investment_amount * (1 + return_pct / 100)
            profit = current_value - investment_amount

            results[period_name] = {
                'value': round(current_value, 2),
                'return_pct': round(return_pct, 2),
                'profit': round(profit, 2),
            }
        else:
            results[period_name] = None

    return results


def monte_carlo_simulation(df, investment_amount, days=30, simulations=1000):
    """
    Monte Carlo simülasyonu ile gelecek projeksiyonu.
    Geçmiş günlük getirilerden rastgele yürüyüş oluşturur.
    """
    if df is None or df.empty or len(df) < 30:
        return None

    # Günlük getirileri hesapla
    daily_returns = df['Close'].pct_change().dropna()

    if len(daily_returns) < 10:
        return None

    mean_return = float(daily_returns.mean())
    std_return = float(daily_returns.std())

    # Simülasyon matrisi: her satır bir senaryo, her sütun bir gün
    np.random.seed(42)  # Tekrarlanabilirlik için
    random_returns = np.random.normal(mean_return, std_return, (simulations, days))

    # Kümülatif getiri hesapla
    price_paths = np.zeros((simulations, days + 1))
    price_paths[:, 0] = investment_amount

    for day in range(1, days + 1):
        price_paths[:, day] = price_paths[:, day - 1] * (1 + random_returns[:, day - 1])

    # Son gün değerleri
    final_values = price_paths[:, -1]

    # İstatistikler
    result = {
        'days': days,
        'simulations': simulations,
        'investment': investment_amount,
        'best': round(float(np.max(final_values)), 2),
        'worst': round(float(np.min(final_values)), 2),
        'average': round(float(np.mean(final_values)), 2),
        'median': round(float(np.median(final_values)), 2),
        'percentile_25': round(float(np.percentile(final_values, 25)), 2),
        'percentile_75': round(float(np.percentile(final_values, 75)), 2),
        'prob_profit': round(float(np.sum(final_values > investment_amount) / simulations * 100), 1),
        'scenarios': price_paths,  # Grafik için
    }

    return result


def run_simulation(df, investment_amount):
    """
    Tüm simülasyon sürecini yönetir.
    Geçmiş performans + Monte Carlo projeksiyonu.
    """
    result = {
        'investment': investment_amount,
        'historical': None,
        'monte_carlo': None,
    }

    try:
        result['historical'] = calculate_historical_returns(df, investment_amount)
    except Exception as e:
        result['historical'] = {}

    try:
        result['monte_carlo'] = monte_carlo_simulation(df, investment_amount)
    except Exception as e:
        result['monte_carlo'] = None

    return result
