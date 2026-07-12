"""
Borsa Bot v3.0 — Grafik Modülü
Teknik analiz, simülasyon ve geçmiş performans grafikleri.
"""

import matplotlib
matplotlib.use('Agg')  # Tkinter ile çakışmaması için
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np


# ═══════════════════════════════════════════════════
#  RENK PALETİ (Dark Theme)
# ═══════════════════════════════════════════════════

COLORS = {
    'bg': '#0f0f23',
    'card_bg': '#1a1a2e',
    'grid': '#2a2a3e',
    'text': '#e2e8f0',
    'text_dim': '#64748b',
    'price': '#00d2ff',
    'sma20': '#ffd700',
    'sma50': '#ff6b6b',
    'bb_fill': '#3b82f615',
    'bb_line': '#3b82f650',
    'macd': '#00d2ff',
    'macd_signal': '#ffd700',
    'macd_hist_pos': '#2ed573',
    'macd_hist_neg': '#ff4757',
    'rsi_line': '#a78bfa',
    'success': '#2ed573',
    'danger': '#ff4757',
    'warning': '#ffa502',
    'purple': '#a78bfa',
    'cyan': '#00d2ff',
}


def _style_axis(ax, show_x_labels=False):
    """Ortak eksen stilini uygula."""
    ax.set_facecolor(COLORS['card_bg'])
    ax.tick_params(colors=COLORS['text_dim'], labelsize=7)
    ax.grid(True, color=COLORS['grid'], alpha=0.3, linewidth=0.5)
    ax.spines['bottom'].set_color(COLORS['grid'])
    ax.spines['left'].set_color(COLORS['grid'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if not show_x_labels:
        ax.tick_params(axis='x', labelbottom=False)


# ═══════════════════════════════════════════════════
#  TEKNİK ANALİZ GRAFİĞİ (Fiyat + RSI + MACD)
# ═══════════════════════════════════════════════════

def create_stock_chart(df, ticker, parent_frame):
    """Fiyat + SMA + Bollinger + RSI + MACD grafiği oluşturur."""
    if df is None or df.empty:
        return None

    df_plot = df.tail(90).copy()

    fig = Figure(figsize=(7.5, 5.5), dpi=100, facecolor=COLORS['bg'])
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.08)

    ax_price = fig.add_subplot(gs[0])
    ax_rsi = fig.add_subplot(gs[1], sharex=ax_price)
    ax_macd = fig.add_subplot(gs[2], sharex=ax_price)

    # ─── Fiyat Grafiği ───
    _style_axis(ax_price)
    ax_price.plot(df_plot.index, df_plot['Close'], color=COLORS['price'], linewidth=1.5, label='Fiyat', zorder=3)

    if 'SMA20' in df_plot.columns:
        ax_price.plot(df_plot.index, df_plot['SMA20'], color=COLORS['sma20'], linewidth=1, label='SMA 20', alpha=0.8)
    if 'SMA50' in df_plot.columns:
        ax_price.plot(df_plot.index, df_plot['SMA50'], color=COLORS['sma50'], linewidth=1, label='SMA 50', alpha=0.8)

    if 'BB_Upper' in df_plot.columns and 'BB_Lower' in df_plot.columns:
        ax_price.fill_between(df_plot.index, df_plot['BB_Upper'], df_plot['BB_Lower'],
                              alpha=0.08, color='#3b82f6', label='Bollinger')
        ax_price.plot(df_plot.index, df_plot['BB_Upper'], color=COLORS['bb_line'], linewidth=0.5)
        ax_price.plot(df_plot.index, df_plot['BB_Lower'], color=COLORS['bb_line'], linewidth=0.5)

    ax_price.set_title(f'{ticker} — Son 90 Gün', color=COLORS['text'], fontsize=11, fontweight='bold', pad=8)
    ax_price.legend(loc='upper left', fontsize=7, facecolor=COLORS['card_bg'], edgecolor=COLORS['grid'],
                    labelcolor=COLORS['text'])
    ax_price.set_ylabel('Fiyat (TL)', color=COLORS['text_dim'], fontsize=8)

    # ─── RSI Grafiği ───
    _style_axis(ax_rsi)
    if 'RSI' in df_plot.columns:
        ax_rsi.plot(df_plot.index, df_plot['RSI'], color=COLORS['rsi_line'], linewidth=1.2)
        ax_rsi.axhline(y=70, color=COLORS['danger'], linestyle='--', linewidth=0.7, alpha=0.6)
        ax_rsi.axhline(y=30, color=COLORS['success'], linestyle='--', linewidth=0.7, alpha=0.6)
        ax_rsi.fill_between(df_plot.index, 70, 100, alpha=0.08, color=COLORS['danger'])
        ax_rsi.fill_between(df_plot.index, 0, 30, alpha=0.08, color=COLORS['success'])
        ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel('RSI', color=COLORS['text_dim'], fontsize=8)

    # ─── MACD Grafiği ───
    _style_axis(ax_macd, show_x_labels=True)
    if 'MACD' in df_plot.columns:
        ax_macd.plot(df_plot.index, df_plot['MACD'], color=COLORS['macd'], linewidth=1, label='MACD')
        ax_macd.plot(df_plot.index, df_plot['MACD_Signal'], color=COLORS['macd_signal'], linewidth=1, label='Signal')
        hist = df_plot['MACD_Hist']
        colors_hist = [COLORS['macd_hist_pos'] if v >= 0 else COLORS['macd_hist_neg'] for v in hist]
        ax_macd.bar(df_plot.index, hist, color=colors_hist, alpha=0.5, width=0.8)
    ax_macd.set_ylabel('MACD', color=COLORS['text_dim'], fontsize=8)
    ax_macd.legend(loc='upper left', fontsize=7, facecolor=COLORS['card_bg'], edgecolor=COLORS['grid'],
                   labelcolor=COLORS['text'])

    ax_macd.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax_macd.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax_macd.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=7)

    fig.subplots_adjust(left=0.1, right=0.95, top=0.94, bottom=0.1)

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)
    return canvas


# ═══════════════════════════════════════════════════
#  MONTE CARLO SİMÜLASYON GRAFİĞİ
# ═══════════════════════════════════════════════════

def create_simulation_chart(monte_carlo_result, ticker, parent_frame):
    """Monte Carlo simülasyon sonuçlarını görselleştirir."""
    if monte_carlo_result is None:
        return None

    mc = monte_carlo_result
    scenarios = mc['scenarios']
    days = mc['days']
    investment = mc['investment']

    fig = Figure(figsize=(7.5, 4.5), dpi=100, facecolor=COLORS['bg'])
    ax = fig.add_subplot(111)
    _style_axis(ax, show_x_labels=True)

    x = np.arange(days + 1)

    # 50 rastgele senaryo çiz (ince, yarı saydam)
    n_display = min(50, len(scenarios))
    indices = np.random.choice(len(scenarios), n_display, replace=False)
    for idx in indices:
        ax.plot(x, scenarios[idx], color=COLORS['cyan'], alpha=0.06, linewidth=0.5)

    # 25-75 persentil arasını doldur
    p25 = np.percentile(scenarios, 25, axis=0)
    p75 = np.percentile(scenarios, 75, axis=0)
    ax.fill_between(x, p25, p75, alpha=0.15, color=COLORS['purple'], label='%25-%75 Aralık')

    # Medyan, en iyi, en kötü
    median_path = np.median(scenarios, axis=0)
    best_path = scenarios[np.argmax(scenarios[:, -1])]
    worst_path = scenarios[np.argmin(scenarios[:, -1])]

    ax.plot(x, best_path, color=COLORS['success'], linewidth=1.5, label=f'En İyi: {mc["best"]:,.0f} TL', alpha=0.8)
    ax.plot(x, median_path, color=COLORS['warning'], linewidth=2, label=f'Medyan: {mc["median"]:,.0f} TL')
    ax.plot(x, worst_path, color=COLORS['danger'], linewidth=1.5, label=f'En Kötü: {mc["worst"]:,.0f} TL', alpha=0.8)

    # Başlangıç çizgisi
    ax.axhline(y=investment, color=COLORS['text_dim'], linestyle='--', linewidth=1, alpha=0.6, label=f'Yatırım: {investment:,.0f} TL')

    # Kâr olasılığı yazısı
    prob = mc['prob_profit']
    prob_color = COLORS['success'] if prob >= 50 else COLORS['danger']
    ax.text(0.98, 0.95, f'Kâr Olasılığı: %{prob:.1f}',
            transform=ax.transAxes, fontsize=10, fontweight='bold',
            color=prob_color, ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=COLORS['card_bg'], edgecolor=prob_color, alpha=0.9))

    ax.set_title(f'{ticker} — {days} Günlük Simülasyon ({mc["simulations"]} Senaryo)',
                 color=COLORS['text'], fontsize=11, fontweight='bold', pad=8)
    ax.set_xlabel('Gün', color=COLORS['text_dim'], fontsize=9)
    ax.set_ylabel('Portföy Değeri (TL)', color=COLORS['text_dim'], fontsize=9)
    ax.legend(loc='upper left', fontsize=7, facecolor=COLORS['card_bg'], edgecolor=COLORS['grid'],
              labelcolor=COLORS['text'])

    fig.subplots_adjust(left=0.12, right=0.95, top=0.9, bottom=0.15)

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)
    return canvas


# ═══════════════════════════════════════════════════
#  GEÇMİŞ PERFORMANS GRAFİĞİ
# ═══════════════════════════════════════════════════

def create_historical_chart(historical_result, investment_amount, ticker, parent_frame):
    """Geçmiş performans bar grafiği oluşturur."""
    if not historical_result:
        return None

    fig = Figure(figsize=(7.5, 3.5), dpi=100, facecolor=COLORS['bg'])
    ax = fig.add_subplot(111)
    _style_axis(ax, show_x_labels=True)

    labels = []
    values = []
    colors = []
    period_names = {'1_ay': '1 Ay', '3_ay': '3 Ay', '6_ay': '6 Ay'}

    for period_key in ['1_ay', '3_ay', '6_ay']:
        data = historical_result.get(period_key)
        if data is not None:
            labels.append(period_names[period_key])
            values.append(data['return_pct'])
            colors.append(COLORS['success'] if data['return_pct'] >= 0 else COLORS['danger'])

    if not labels:
        return None

    x_pos = np.arange(len(labels))
    bars = ax.bar(x_pos, values, color=colors, width=0.5, alpha=0.85, edgecolor='none')

    # Değer etiketleri
    for bar, val in zip(bars, values):
        y_pos = bar.get_height()
        offset = 0.5 if val >= 0 else -1.5
        ax.text(bar.get_x() + bar.get_width() / 2, y_pos + offset,
                f'{"+" if val >= 0 else ""}{val:.1f}%',
                ha='center', va='bottom' if val >= 0 else 'top',
                fontsize=11, fontweight='bold', color=COLORS['text'])

    ax.axhline(y=0, color=COLORS['text_dim'], linewidth=0.8, alpha=0.5)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, fontsize=10, color=COLORS['text'])
    ax.set_ylabel('Getiri (%)', color=COLORS['text_dim'], fontsize=9)
    ax.set_title(f'{ticker} — Geçmiş Performans ({investment_amount:,.0f} TL Yatırım)',
                 color=COLORS['text'], fontsize=11, fontweight='bold', pad=8)

    fig.subplots_adjust(left=0.1, right=0.95, top=0.88, bottom=0.15)

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)
    return canvas
