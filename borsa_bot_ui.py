"""
Borsa Bot v3.0 — Premium Arayüz
6 sekmeli tam kapsamlı yatırım asistanı.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
from borsa_logic import analyze_stock
from borsa_chart import create_stock_chart, create_simulation_chart, create_historical_chart
from borsa_simulation import run_simulation


# ═══════════════════════════════════════════════════
#  RENK PALETİ — Premium Dark Theme
# ═══════════════════════════════════════════════════

T = {
    'bg':           '#0a0a1a',
    'bg_main':      '#0f0f23',
    'bg_card':      '#161630',
    'bg_card_alt':  '#1a1a3e',
    'bg_input':     '#1e1e3f',
    'bg_hover':     '#252550',
    'bg_tab':       '#12122a',
    'bg_tab_sel':   '#1e1e44',

    'accent':       '#00d2ff',
    'accent_dark':  '#0099cc',
    'success':      '#2ed573',
    'success_dim':  '#1a8a4a',
    'danger':       '#ff4757',
    'danger_dim':   '#a62d38',
    'warning':      '#ffa502',
    'purple':       '#a78bfa',
    'gold':         '#ffd700',

    'text':         '#e2e8f0',
    'text_dim':     '#94a3b8',
    'text_dark':    '#475569',
    'border':       '#2a2a4a',
}


# ═══════════════════════════════════════════════════
#  FORMAT YARDIMCILARI
# ═══════════════════════════════════════════════════

def format_money(val):
    """Sayıyı okunabilir formata çevir: 1.5B, 250M, 12K"""
    if val is None or val == 0:
        return "—"
    if val >= 1e12:
        return f"{val / 1e12:.1f}T TL"
    if val >= 1e9:
        return f"{val / 1e9:.1f}B TL"
    if val >= 1e6:
        return f"{val / 1e6:.1f}M TL"
    if val >= 1e3:
        return f"{val / 1e3:.1f}K TL"
    return f"{val:,.2f} TL"


def format_pct(val):
    """Yüzdeyi formatla."""
    if val is None or val == 0:
        return "—"
    return f"%{val:.2f}"


# ═══════════════════════════════════════════════════
#  ANA UYGULAMA
# ═══════════════════════════════════════════════════

class BorsaBotUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Borsa Bot v3.0 — Gemini AI Yatırım Asistanı")
        self.window.geometry("1100x950")
        self.window.minsize(900, 700)
        self.window.configure(bg=T['bg'])

        self.result_data = None
        self.loading = False
        self.loading_dots = 0
        self.chart_canvases = []
        self._tab_canvases = []

        self._setup_styles()
        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.window.update_idletasks()
        w = self.window.winfo_width()
        h = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (w // 2)
        y = (self.window.winfo_screenheight() // 2) - (h // 2) - 30
        self.window.geometry(f'{w}x{h}+{x}+{max(0, y)}')

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Notebook (tab) stili
        self.style.configure('Custom.TNotebook', background=T['bg'], borderwidth=0)
        self.style.configure('Custom.TNotebook.Tab',
                             background=T['bg_tab'], foreground=T['text_dim'],
                             padding=[14, 8], font=('Segoe UI', 9, 'bold'),
                             borderwidth=0)
        self.style.map('Custom.TNotebook.Tab',
                       background=[('selected', T['bg_tab_sel'])],
                       foreground=[('selected', T['accent'])])

    def _build_ui(self):
        # ─── HEADER ───
        header = tk.Frame(self.window, bg=T['bg'])
        header.pack(fill='x', padx=20, pady=(12, 0))

        # Gradient bar
        self.gradient_bar = tk.Canvas(header, height=3, bg=T['bg'], highlightthickness=0)
        self.gradient_bar.pack(fill='x', pady=(0, 8))
        self.gradient_bar.bind('<Configure>', lambda e: self._draw_gradient(self.gradient_bar, e.width))

        title_row = tk.Frame(header, bg=T['bg'])
        title_row.pack(fill='x')

        tk.Label(title_row, text="📈", font=("Segoe UI Emoji", 24),
                 bg=T['bg'], fg=T['text']).pack(side='left', padx=(0, 6))

        title_col = tk.Frame(title_row, bg=T['bg'])
        title_col.pack(side='left')
        tk.Label(title_col, text="BORSA BOT", font=("Segoe UI", 22, "bold"),
                 bg=T['bg'], fg=T['accent']).pack(anchor='w')
        tk.Label(title_col, text="Gemini AI Destekli Yatırım Asistanı  •  v3.0",
                 font=("Segoe UI", 9), bg=T['bg'], fg=T['text_dark']).pack(anchor='w')

        # ─── SEARCH BAR ───
        search = tk.Frame(self.window, bg=T['bg_card'], highlightbackground=T['border'],
                          highlightthickness=1, padx=18, pady=12)
        search.pack(fill='x', padx=20, pady=(12, 0))

        inner = tk.Frame(search, bg=T['bg_card'])
        inner.pack(fill='x')

        tk.Label(inner, text="🔍", font=("Segoe UI Emoji", 13),
                 bg=T['bg_card'], fg=T['text']).pack(side='left', padx=(0, 6))
        tk.Label(inner, text="Hisse Kodu", font=("Segoe UI", 10, "bold"),
                 bg=T['bg_card'], fg=T['text']).pack(side='left', padx=(0, 10))

        self.ticker_entry = tk.Entry(inner, font=("Segoe UI", 13, "bold"), width=10,
                                     bg=T['bg_input'], fg=T['accent'], insertbackground=T['accent'],
                                     highlightbackground=T['border'], highlightcolor=T['accent'],
                                     highlightthickness=1, relief='flat')
        self.ticker_entry.pack(side='left', ipady=5, padx=(0, 4))
        self.ticker_entry.insert(0, "THYAO")
        self.ticker_entry.bind('<Return>', lambda e: self.start_analysis())
        self.ticker_entry.bind('<FocusIn>', lambda e: self.ticker_entry.select_range(0, 'end'))

        tk.Label(inner, text=".IS", font=("Segoe UI", 9),
                 bg=T['bg_card'], fg=T['text_dark']).pack(side='left', padx=(0, 12))

        self.btn = tk.Button(inner, text="⚡ Analiz Et", font=("Segoe UI", 10, "bold"),
                             bg=T['accent_dark'], fg='white', activebackground=T['accent'],
                             activeforeground='white', relief='flat', cursor='hand2',
                             padx=18, pady=5, command=self.start_analysis)
        self.btn.pack(side='right')
        self.btn.bind('<Enter>', lambda e: self.btn.configure(bg=T['accent']))
        self.btn.bind('<Leave>', lambda e: self.btn.configure(bg=T['accent_dark']))

        # ─── STATUS ───
        self.status = tk.Label(self.window, text="", font=("Segoe UI", 9),
                               bg=T['bg'], fg=T['text_dim'], anchor='w')
        self.status.pack(fill='x', padx=22, pady=(6, 0))

        # ─── SIGNAL CARD (sabit, sekmelerin üstünde) ───
        self.signal_frame = tk.Frame(self.window, bg=T['bg'])
        self.signal_frame.pack(fill='x', padx=20, pady=(6, 0))
        # Başlangıçta boş

        # ─── NOTEBOOK (SEKMELER) ───
        self.notebook = ttk.Notebook(self.window, style='Custom.TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=20, pady=(6, 10))

        # Sekme sayfaları
        self.tab_teknik = self._make_tab_page()
        self.tab_sirket = self._make_tab_page()
        self.tab_haber = self._make_tab_page()
        self.tab_hedef = self._make_tab_page()
        self.tab_sim = self._make_tab_page()
        self.tab_ai = self._make_tab_page()

        self.notebook.add(self.tab_teknik['outer'], text="📊 Teknik")
        self.notebook.add(self.tab_sirket['outer'], text="🏢 Şirket")
        self.notebook.add(self.tab_haber['outer'], text="📰 Haberler")
        self.notebook.add(self.tab_hedef['outer'], text="🎯 Hedef")
        self.notebook.add(self.tab_sim['outer'], text="💰 Simülasyon")
        self.notebook.add(self.tab_ai['outer'], text="🤖 AI Yorum")

        # Sadece seçili sekmeyi kaydıran global tekerlek bağlantısı
        self.window.bind_all("<MouseWheel>", self._on_mousewheel)

        # ─── FOOTER ───
        footer = tk.Frame(self.window, bg=T['bg'])
        footer.pack(fill='x', padx=20, pady=(0, 8))
        tk.Label(footer, text="⚠️ Bu uygulama yatırım tavsiyesi vermez. Kendi araştırmanızı yapınız.",
                 font=("Segoe UI", 7), bg=T['bg'], fg=T['text_dark']).pack()
        tk.Label(footer, text="Borsa Bot v3.0  •  Powered by Gemini AI & yfinance",
                 font=("Segoe UI", 7), bg=T['bg'], fg=T['text_dark']).pack()

    def _make_tab_page(self):
        """Scrollable sekme sayfası oluştur."""
        outer = tk.Frame(self.notebook, bg=T['bg'])
        canvas = tk.Canvas(outer, bg=T['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=T['bg'])

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._tab_canvases.append(canvas)

        return {'outer': outer, 'canvas': canvas, 'inner': inner}

    def _on_mousewheel(self, event):
        """Sadece görünür (seçili) sekmenin canvas'ını kaydırır."""
        try:
            idx = self.notebook.index(self.notebook.select())
            canvas = self._tab_canvases[idx]
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except (tk.TclError, IndexError):
            pass

    def _draw_gradient(self, canvas, width):
        canvas.delete("all")
        for i in range(max(1, width)):
            ratio = i / max(1, width)
            if ratio < 0.5:
                r, g, b = 0, int(210 * ratio * 2), 255
            else:
                r = int(167 * (ratio - 0.5) * 2)
                g = int(210 - 71 * (ratio - 0.5) * 2)
                b = int(255 - 5 * (ratio - 0.5) * 2)
            canvas.create_line(i, 0, i, 3, fill=f'#{r:02x}{g:02x}{b:02x}')

    # ═══════════════════════════════════════════════
    #  ANALİZ AKIŞI
    # ═══════════════════════════════════════════════

    def start_analysis(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Uyarı", "Lütfen bir hisse kodu girin!")
            return
        if self.loading:
            return

        self.loading = True
        self.loading_dots = 0
        self.btn.configure(state='disabled', text="⏳ Yükleniyor", bg=T['text_dark'])
        self._clear_all()
        self.status.configure(text=f"🔄 {ticker} analiz ediliyor...", fg=T['accent'])
        self._animate()

        thread = threading.Thread(target=self._run_analysis, args=(ticker,), daemon=True)
        thread.start()

    def _animate(self):
        if not self.loading:
            return
        dots = "." * (self.loading_dots % 4)
        stages = ["Veriler çekiliyor", "Göstergeler hesaplanıyor", "Şirket bilgileri alınıyor",
                   "Haberler taranıyor", "AI yorumu bekleniyor"]
        stage = stages[min(self.loading_dots // 3, len(stages) - 1)]
        self.status.configure(text=f"🔄 {stage}{dots}")
        self.loading_dots += 1
        self.window.after(400, self._animate)

    def _run_analysis(self, ticker):
        try:
            result = analyze_stock(ticker)
            self.window.after(0, lambda: self._show_results(result))
        except Exception as e:
            self.window.after(0, lambda: self._show_error(str(e)))

    def _clear_all(self):
        for w in self.signal_frame.winfo_children():
            w.destroy()
        for tab in [self.tab_teknik, self.tab_sirket, self.tab_haber,
                     self.tab_hedef, self.tab_sim, self.tab_ai]:
            for w in tab['inner'].winfo_children():
                w.destroy()
        self.chart_canvases.clear()

    def _show_error(self, msg):
        self.loading = False
        self.btn.configure(state='normal', text="⚡ Analiz Et", bg=T['accent_dark'])
        self.status.configure(text=f"❌ {msg}", fg=T['danger'])

    def _show_results(self, r):
        self.loading = False
        self.btn.configure(state='normal', text="⚡ Analiz Et", bg=T['accent_dark'])

        if not r['success']:
            self._show_error(r.get('error', 'Bilinmeyen hata'))
            return

        self.result_data = r
        self.status.configure(text=f"✅ {r['ticker']} analizi tamamlandı", fg=T['success'])

        self._build_signal_card(r)
        self._build_tab_teknik(r)
        self._build_tab_sirket(r)
        self._build_tab_haber(r)
        self._build_tab_hedef(r)
        self._build_tab_sim(r)
        self._build_tab_ai(r)

        self.notebook.select(0)

    # ═══════════════════════════════════════════════
    #  SİNYAL KARTI (Sekmelerin Üstünde)
    # ═══════════════════════════════════════════════

    def _build_signal_card(self, r):
        for w in self.signal_frame.winfo_children():
            w.destroy()

        sig = r.get('signal', {})
        score = sig.get('score', 50)
        text = sig.get('text', 'BEKLE')
        color = sig.get('color', T['warning'])
        emoji = sig.get('emoji', '🟡')

        card = tk.Frame(self.signal_frame, bg=T['bg_card'],
                        highlightbackground=color, highlightthickness=2,
                        padx=16, pady=10)
        card.pack(fill='x')

        # Sol: Sinyal metni
        left = tk.Frame(card, bg=T['bg_card'])
        left.pack(side='left', fill='y')

        tk.Label(left, text=f"{emoji} {text}", font=("Segoe UI", 18, "bold"),
                 bg=T['bg_card'], fg=color).pack(anchor='w')

        change_color = T['success'] if r['change'] >= 0 else T['danger']
        change_arrow = "▲" if r['change'] >= 0 else "▼"
        tk.Label(left, text=f"{r['ticker']}  •  {r['price']:.2f} TL  {change_arrow} {abs(r['change_pct']):.2f}%",
                 font=("Segoe UI", 10), bg=T['bg_card'], fg=change_color).pack(anchor='w')

        # Sağ: Skor barı
        right = tk.Frame(card, bg=T['bg_card'])
        right.pack(side='right', padx=(20, 0))

        tk.Label(right, text=f"{score}/100", font=("Segoe UI", 20, "bold"),
                 bg=T['bg_card'], fg=color).pack()

        # Progress bar
        bar_frame = tk.Frame(right, bg=T['text_dark'], height=8, width=160)
        bar_frame.pack(pady=(4, 0))
        bar_frame.pack_propagate(False)

        fill_width = int(160 * score / 100)
        if fill_width > 0:
            fill = tk.Frame(bar_frame, bg=color, height=8, width=fill_width)
            fill.pack(side='left')

    # ═══════════════════════════════════════════════
    #  SEKME 1: TEKNİK ANALİZ
    # ═══════════════════════════════════════════════

    def _build_tab_teknik(self, r):
        parent = self.tab_teknik['inner']

        # Sinyal detayları
        sig = r.get('signal', {})
        details = sig.get('details', [])

        if details:
            sec = self._section(parent, "⚡ Sinyal Detayları")
            for d in details:
                row = tk.Frame(sec, bg=T['bg_card'], pady=4)
                row.pack(fill='x', padx=8)

                tk.Label(row, text=d['name'], font=("Segoe UI", 10, "bold"),
                         bg=T['bg_card'], fg=T['text'], width=12, anchor='w').pack(side='left')

                tk.Label(row, text=d['signal'], font=("Segoe UI", 9, "bold"),
                         bg=T['bg_card'], fg=d['color'], width=10).pack(side='left')

                tk.Label(row, text=d['reason'], font=("Segoe UI", 8),
                         bg=T['bg_card'], fg=T['text_dim'], anchor='w').pack(side='left', fill='x', expand=True)

        # Gösterge kartları
        sec2 = self._section(parent, "📊 Teknik Göstergeler")
        cards_row = tk.Frame(sec2, bg=T['bg_card'])
        cards_row.pack(fill='x', padx=8, pady=4)

        self._mini_card(cards_row, "RSI", f"{r['rsi']:.1f}", r['rsi_status'], r['rsi_color'])
        self._mini_card(cards_row, "SMA20", f"{r['sma20']:.2f}", "", T['gold'])
        self._mini_card(cards_row, "SMA50", f"{r['sma50']:.2f}", "", T['danger'])

        macd_c = T['success'] if r['macd_hist'] >= 0 else T['danger']
        self._mini_card(cards_row, "MACD", f"{r['macd']:.4f}", "Yükseliş" if r['macd_hist'] >= 0 else "Düşüş", macd_c)

        # Grafik
        chart_sec = self._section(parent, "📈 Fiyat Grafiği")
        try:
            c = create_stock_chart(r['df'], r['ticker'], chart_sec)
            if c:
                self.chart_canvases.append(c)
        except Exception as e:
            tk.Label(chart_sec, text=f"Grafik hatası: {e}", bg=T['bg_card'], fg=T['danger']).pack(pady=10)

    # ═══════════════════════════════════════════════
    #  SEKME 2: ŞİRKET BİLGİLERİ
    # ═══════════════════════════════════════════════

    def _build_tab_sirket(self, r):
        parent = self.tab_sirket['inner']
        co = r.get('company', {})

        # Şirket başlık
        header_sec = self._section(parent, f"🏢 {co.get('name', 'Şirket Bilgileri')}")
        tk.Label(header_sec, text=f"{co.get('sector', '')}  •  {co.get('industry', '')}",
                 font=("Segoe UI", 10), bg=T['bg_card'], fg=T['purple'], padx=12).pack(anchor='w')

        if co.get('website'):
            link = tk.Label(header_sec, text=f"🌐 {co['website']}", font=("Segoe UI", 9, "underline"),
                            bg=T['bg_card'], fg=T['accent'], cursor='hand2', padx=12)
            link.pack(anchor='w', pady=(2, 6))
            link.bind('<Button-1>', lambda e: webbrowser.open(co['website']))

        # Finansal veriler
        fin_sec = self._section(parent, "💰 Finansal Veriler")
        data_frame = tk.Frame(fin_sec, bg=T['bg_card'])
        data_frame.pack(fill='x', padx=12, pady=6)

        financial_data = [
            ("Piyasa Değeri", format_money(co.get('market_cap', 0))),
            ("F/K Oranı", f"{co.get('pe_ratio', 0):.2f}" if co.get('pe_ratio') else "—"),
            ("İleriye Dönük F/K", f"{co.get('forward_pe', 0):.2f}" if co.get('forward_pe') else "—"),
            ("Temettü Verimi", f"%{co.get('dividend_yield', 0) * 100:.2f}" if co.get('dividend_yield') else "—"),
            ("52H En Yüksek", f"{co.get('week52_high', 0):.2f} TL" if co.get('week52_high') else "—"),
            ("52H En Düşük", f"{co.get('week52_low', 0):.2f} TL" if co.get('week52_low') else "—"),
            ("Ort. Hacim", f"{co.get('avg_volume', 0):,.0f}" if co.get('avg_volume') else "—"),
            ("Çalışan Sayısı", f"{co.get('employees', 0):,}" if co.get('employees') else "—"),
        ]

        for i, (label, value) in enumerate(financial_data):
            row_bg = T['bg_card'] if i % 2 == 0 else T['bg_card_alt']
            row = tk.Frame(data_frame, bg=row_bg, pady=5, padx=8)
            row.pack(fill='x')
            tk.Label(row, text=label, font=("Segoe UI", 10),
                     bg=row_bg, fg=T['text_dim'], anchor='w', width=20).pack(side='left')
            tk.Label(row, text=value, font=("Segoe UI", 10, "bold"),
                     bg=row_bg, fg=T['text'], anchor='e').pack(side='right')

        # Şirket açıklaması
        if co.get('description'):
            desc_sec = self._section(parent, "📄 Hakkında")
            tk.Label(desc_sec, text=co['description'], font=("Segoe UI", 9),
                     bg=T['bg_card'], fg=T['text_dim'], wraplength=700, justify='left',
                     padx=12, pady=8).pack(fill='x')

    # ═══════════════════════════════════════════════
    #  SEKME 3: HABERLER
    # ═══════════════════════════════════════════════

    def _build_tab_haber(self, r):
        parent = self.tab_haber['inner']
        news = r.get('news', [])

        sec = self._section(parent, f"📰 Son Haberler ({len(news)} adet)")

        if not news:
            tk.Label(sec, text="Bu hisse için haber bulunamadı.",
                     font=("Segoe UI", 10), bg=T['bg_card'], fg=T['text_dim'], pady=20).pack()
            return

        for i, item in enumerate(news):
            row_bg = T['bg_card'] if i % 2 == 0 else T['bg_card_alt']
            row = tk.Frame(sec, bg=row_bg, padx=12, pady=8)
            row.pack(fill='x')

            # Başlık (tıklanabilir)
            title = tk.Label(row, text=item.get('title', 'Başlık yok'),
                             font=("Segoe UI", 10, "bold"), bg=row_bg, fg=T['accent'],
                             cursor='hand2', wraplength=700, justify='left', anchor='w')
            title.pack(fill='x')

            link = item.get('link', '')
            if link and link != '#':
                title.bind('<Button-1>', lambda e, url=link: webbrowser.open(url))
                title.bind('<Enter>', lambda e, lbl=title: lbl.configure(fg=T['gold']))
                title.bind('<Leave>', lambda e, lbl=title: lbl.configure(fg=T['accent']))

            # Alt bilgi
            meta = f"📡 {item.get('publisher', 'Bilinmiyor')}"
            if item.get('date'):
                meta += f"  •  {str(item['date'])[:16]}"
            tk.Label(row, text=meta, font=("Segoe UI", 8),
                     bg=row_bg, fg=T['text_dark'], anchor='w').pack(fill='x')

    # ═══════════════════════════════════════════════
    #  SEKME 4: HEDEF FİYAT & ANALİST
    # ═══════════════════════════════════════════════

    def _build_tab_hedef(self, r):
        parent = self.tab_hedef['inner']
        tgt = r.get('targets', {})

        if not tgt or not tgt.get('available', False):
            sec = self._section(parent, "🎯 Analist Hedef Fiyatları")
            tk.Label(sec, text="Bu hisse için analist verisi bulunamadı.\nBIST hisseleri için sınırlı veri mevcut olabilir.",
                     font=("Segoe UI", 10), bg=T['bg_card'], fg=T['text_dim'], pady=20,
                     justify='center').pack()
            return

        # Hedef fiyatlar
        sec = self._section(parent, "🎯 Analist Hedef Fiyatları")

        # Fiyat karşılaştırma barı
        bar_frame = tk.Frame(sec, bg=T['bg_card'], padx=15, pady=10)
        bar_frame.pack(fill='x')

        price_data = [
            ("En Düşük", tgt.get('low', 0), T['danger']),
            ("Mevcut", tgt.get('current', 0), T['accent']),
            ("Medyan Hedef", tgt.get('median', 0), T['gold']),
            ("En Yüksek", tgt.get('high', 0), T['success']),
        ]

        for label, val, color in price_data:
            if val:
                row = tk.Frame(bar_frame, bg=T['bg_card'], pady=3)
                row.pack(fill='x')
                tk.Label(row, text=label, font=("Segoe UI", 10),
                         bg=T['bg_card'], fg=T['text_dim'], width=14, anchor='w').pack(side='left')
                tk.Label(row, text=f"{val:.2f} TL", font=("Segoe UI", 12, "bold"),
                         bg=T['bg_card'], fg=color).pack(side='left')

        # Potansiyel
        pot = tgt.get('potential_pct', 0)
        if pot:
            pot_color = T['success'] if pot > 0 else T['danger']
            pot_text = f"{'▲' if pot > 0 else '▼'} %{abs(pot):.1f} Potansiyel"
            tk.Label(bar_frame, text=pot_text, font=("Segoe UI", 14, "bold"),
                     bg=T['bg_card'], fg=pot_color, pady=8).pack()

        # Analist tavsiyeleri
        recs = tgt.get('recommendations', {})
        total = sum(recs.values())
        if total > 0:
            rec_sec = self._section(parent, f"👥 Analist Tavsiyeleri ({total} Analist)")
            rec_frame = tk.Frame(rec_sec, bg=T['bg_card'], padx=15, pady=8)
            rec_frame.pack(fill='x')

            rec_items = [
                ("Güçlü Al", recs.get('strongBuy', 0), T['success']),
                ("Al", recs.get('buy', 0), '#7bed9f'),
                ("Tut", recs.get('hold', 0), T['warning']),
                ("Sat", recs.get('sell', 0), '#ff6b81'),
                ("Güçlü Sat", recs.get('strongSell', 0), T['danger']),
            ]

            for label, count, color in rec_items:
                row = tk.Frame(rec_frame, bg=T['bg_card'], pady=2)
                row.pack(fill='x')

                tk.Label(row, text=label, font=("Segoe UI", 10),
                         bg=T['bg_card'], fg=T['text'], width=10, anchor='w').pack(side='left')

                # Mini bar
                bar_outer = tk.Frame(row, bg=T['text_dark'], height=14, width=200)
                bar_outer.pack(side='left', padx=(8, 8))
                bar_outer.pack_propagate(False)
                if count > 0 and total > 0:
                    bw = int(200 * count / total)
                    tk.Frame(bar_outer, bg=color, height=14, width=max(bw, 2)).pack(side='left')

                tk.Label(row, text=str(count), font=("Segoe UI", 10, "bold"),
                         bg=T['bg_card'], fg=color).pack(side='left')

    # ═══════════════════════════════════════════════
    #  SEKME 5: SİMÜLASYON
    # ═══════════════════════════════════════════════

    def _build_tab_sim(self, r):
        parent = self.tab_sim['inner']

        # Yatırım miktarı girişi
        input_sec = self._section(parent, "💰 Yatırım Simülasyonu")

        input_row = tk.Frame(input_sec, bg=T['bg_card'], padx=12, pady=8)
        input_row.pack(fill='x')

        tk.Label(input_row, text="Yatırım Miktarı (TL):", font=("Segoe UI", 10, "bold"),
                 bg=T['bg_card'], fg=T['text']).pack(side='left', padx=(0, 8))

        self.sim_entry = tk.Entry(input_row, font=("Segoe UI", 12, "bold"), width=12,
                                  bg=T['bg_input'], fg=T['gold'], insertbackground=T['gold'],
                                  highlightbackground=T['border'], highlightcolor=T['gold'],
                                  highlightthickness=1, relief='flat')
        self.sim_entry.pack(side='left', ipady=4, padx=(0, 10))
        self.sim_entry.insert(0, "10000")

        sim_btn = tk.Button(input_row, text="🚀 Simüle Et", font=("Segoe UI", 10, "bold"),
                            bg=T['success_dim'], fg='white', activebackground=T['success'],
                            relief='flat', cursor='hand2', padx=16, pady=4,
                            command=lambda: self._run_simulation(r))
        sim_btn.pack(side='left')
        sim_btn.bind('<Enter>', lambda e: sim_btn.configure(bg=T['success']))
        sim_btn.bind('<Leave>', lambda e: sim_btn.configure(bg=T['success_dim']))

        self.sim_entry.bind('<Return>', lambda e: self._run_simulation(r))

        # Simülasyon sonuçları buraya gelecek
        self.sim_results_frame = tk.Frame(parent, bg=T['bg'])
        self.sim_results_frame.pack(fill='x')

    def _run_simulation(self, r):
        """Simülasyonu çalıştır."""
        import re
        try:
            raw = self.sim_entry.get().strip().replace(',', '.')
            raw = re.sub(r'[^\d.]', '', raw)          # sadece rakam ve nokta kalsın
            parts = raw.split('.')
            if len(parts) > 1:
                raw = parts[0] + '.' + ''.join(parts[1:])   # tek ondalık ayraç
            amount = float(raw)
        except (ValueError, IndexError):
            messagebox.showwarning("Uyarı", "Geçerli bir miktar girin!")
            return

        if amount <= 0:
            messagebox.showwarning("Uyarı", "Miktar 0'dan büyük olmalı!")
            return

        # Temizle
        for w in self.sim_results_frame.winfo_children():
            w.destroy()

        df = r.get('df')
        if df is None:
            return

        sim_result = run_simulation(df, amount)
        self._display_simulation(sim_result, r['ticker'])

    def _display_simulation(self, sim, ticker):
        parent = self.sim_results_frame

        # Geçmiş performans tablosu
        hist = sim.get('historical', {})
        if hist:
            sec = self._section(parent, "📅 Geçmiş Performans")
            table = tk.Frame(sec, bg=T['bg_card'], padx=12, pady=6)
            table.pack(fill='x')

            # Başlık satırı
            header_row = tk.Frame(table, bg=T['bg_card_alt'], pady=4, padx=8)
            header_row.pack(fill='x')
            for col, w in [("Dönem", 8), ("Değer", 12), ("Kâr/Zarar", 12), ("Getiri", 8)]:
                tk.Label(header_row, text=col, font=("Segoe UI", 9, "bold"),
                         bg=T['bg_card_alt'], fg=T['text_dim'], width=w, anchor='center').pack(side='left', padx=4)

            period_names = {'1_ay': '1 Ay', '3_ay': '3 Ay', '6_ay': '6 Ay'}
            for key in ['1_ay', '3_ay', '6_ay']:
                data = hist.get(key)
                if data is None:
                    continue
                color = T['success'] if data['profit'] >= 0 else T['danger']
                row = tk.Frame(table, bg=T['bg_card'], pady=3, padx=8)
                row.pack(fill='x')

                tk.Label(row, text=period_names[key], font=("Segoe UI", 10, "bold"),
                         bg=T['bg_card'], fg=T['text'], width=8, anchor='center').pack(side='left', padx=4)
                tk.Label(row, text=f"{data['value']:,.2f} TL", font=("Segoe UI", 10),
                         bg=T['bg_card'], fg=T['text'], width=12, anchor='center').pack(side='left', padx=4)

                prefix = "+" if data['profit'] >= 0 else ""
                tk.Label(row, text=f"{prefix}{data['profit']:,.2f} TL", font=("Segoe UI", 10, "bold"),
                         bg=T['bg_card'], fg=color, width=12, anchor='center').pack(side='left', padx=4)
                tk.Label(row, text=f"{prefix}{data['return_pct']:.1f}%", font=("Segoe UI", 10, "bold"),
                         bg=T['bg_card'], fg=color, width=8, anchor='center').pack(side='left', padx=4)

            # Geçmiş performans grafiği
            try:
                c = create_historical_chart(hist, sim['investment'], ticker, sec)
                if c:
                    self.chart_canvases.append(c)
            except Exception:
                pass

        # Monte Carlo sonuçları
        mc = sim.get('monte_carlo')
        if mc:
            mc_sec = self._section(parent, "🎲 Monte Carlo Simülasyonu (30 Gün)")

            # Özet kartlar
            summary = tk.Frame(mc_sec, bg=T['bg_card'], padx=12, pady=8)
            summary.pack(fill='x')

            mc_data = [
                ("En İyi Senaryo", f"{mc['best']:,.0f} TL", T['success']),
                ("Medyan", f"{mc['median']:,.0f} TL", T['warning']),
                ("Ortalama", f"{mc['average']:,.0f} TL", T['accent']),
                ("En Kötü", f"{mc['worst']:,.0f} TL", T['danger']),
                ("Kâr Olasılığı", f"%{mc['prob_profit']:.1f}", T['success'] if mc['prob_profit'] >= 50 else T['danger']),
            ]

            row_frame = tk.Frame(summary, bg=T['bg_card'])
            row_frame.pack(fill='x')
            for label, value, color in mc_data:
                self._mini_card(row_frame, label, value, "", color)

            # Simülasyon grafiği
            try:
                c = create_simulation_chart(mc, ticker, mc_sec)
                if c:
                    self.chart_canvases.append(c)
            except Exception:
                pass

    # ═══════════════════════════════════════════════
    #  SEKME 6: AI YORUM
    # ═══════════════════════════════════════════════

    def _build_tab_ai(self, r):
        parent = self.tab_ai['inner']
        sec = self._section(parent, "🤖 Gemini AI — Kapsamlı Analiz")

        text = tk.Text(sec, wrap='word', font=("Segoe UI", 10),
                       bg=T['bg_card'], fg=T['text'], relief='flat',
                       highlightthickness=0, padx=15, pady=12,
                       spacing1=2, spacing3=2)
        text.pack(fill='x')
        text.insert('1.0', r.get('ai_advice', 'AI yorumu alınamadı.'))
        text.configure(state='disabled')

        lines = int(text.index('end-1c').split('.')[0])
        text.configure(height=min(max(lines, 10), 35))

    # ═══════════════════════════════════════════════
    #  YARDIMCI WIDGETLAR
    # ═══════════════════════════════════════════════

    def _section(self, parent, title):
        """Başlıklı kart bölümü oluştur."""
        frame = tk.Frame(parent, bg=T['bg_card'], highlightbackground=T['border'],
                         highlightthickness=1)
        frame.pack(fill='x', pady=(0, 8), padx=4)

        header = tk.Frame(frame, bg=T['bg_card_alt'], padx=12, pady=6)
        header.pack(fill='x')
        tk.Label(header, text=title, font=("Segoe UI", 11, "bold"),
                 bg=T['bg_card_alt'], fg=T['text']).pack(anchor='w')

        return frame

    def _mini_card(self, parent, title, value, subtitle, color):
        """Küçük gösterge kartı."""
        card = tk.Frame(parent, bg=T['bg_card_alt'], padx=10, pady=6,
                        highlightbackground=T['border'], highlightthickness=1)
        card.pack(side='left', fill='x', expand=True, padx=(0, 4))

        tk.Label(card, text=title, font=("Segoe UI", 8, "bold"),
                  bg=T['bg_card_alt'], fg=T['text_dim']).pack(anchor='w')
        tk.Label(card, text=value, font=("Segoe UI", 13, "bold"),
                  bg=T['bg_card_alt'], fg=color).pack(anchor='w')
        if subtitle:
            tk.Label(card, text=subtitle, font=("Segoe UI", 8, "bold"),
                     bg=T['bg_card_alt'], fg=color).pack(anchor='w')

    # ═══════════════════════════════════════════════
    #  RUN
    # ═══════════════════════════════════════════════

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = BorsaBotUI()
    app.run()
