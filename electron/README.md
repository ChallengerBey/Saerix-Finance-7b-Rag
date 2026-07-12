# borsa-llm-desktop

Borsa Bot v4.0 — Gemini AI Destekli Yatırım Asistanı (Electron UI). Bu klasör, `[Electron 33 + Chart.js + IndexedDB]` ile çalışan ve Python FastAPI backend'ini (`../server.py`) `127.0.0.1:8765` üzerinden tüketen ön-uçtır.

> Backend kurulumu, API endpoint'leri ve veri kaynakları için kök dizindeki [`../README.md`](../README.md)'ye bak.

---

## Bu Klasörde Ne Var?

```
electron/
├── main.js            # Electron main process — Python sunucusunu başlatır, pencere açar
├── index.html         # UI iskeleti (tek sayfa, 11 sekme + yan panel)
├── renderer.js        # Renderer process mantığı (ES modül)
├── db.js              # IndexedDB sarıcı (watchlist/portföy/alarm/cache/backtest/quotes)
├── styles.css         # Tüm stiller (dark/light theme, erişilebilirlik teması)
├── sw.js              # Service Worker (offline-first PWA, push bildirim)
├── package.json       # Proje meta + "start": "electron ."
└── package-lock.json  # Bağımlılık kilidi
```

Sorumluluk dağılımı:

| Dosya | Görev |
|-------|-------|
| `main.js` | Python `python`/`python3` tespiti → `server.py` spawn → `/api/health` polling → 200 olunca `BrowserWindow` açar, DevTools otomatik açılır, kapatılınca sunucuyu da öldürür |
| `index.html` | DOM şablonu, modal/dialog, font (Inter) ve Chart.js CDN |
| `renderer.js` | Tüm UI mantığı: ticker girişi, sinyal/şirket/haber/hedef render, portföy+alarm CRUD, simülasyon, WebSocket bağlantısı, komut paleti, tur, tema |
| `db.js` | IndexedDB v3; `IDB.exportAll/importAll` bulk op'lar |
| `styles.css` | CSS değişkenleriyle tema, grid layout, Chart.js tooltip stili |
| `sw.js` | Cache-first (statik) + network-first (API) + push notification |

---

## Kurulum

```bash
cd electron
npm install
npm start
```

`npm start` şunu yapar:

1. `../server.py` zaten `127.0.0.1:8765`'te dinliyor mu diye `/api/health` polling
2. Değilse `python` veya `python3` bulunur → `python ../server.py --host 127.0.0.1 --port 8765` spawn
3. Sağlık 200 olunca `BrowserWindow` açılır → `ready-to-show` → göster + DevTools aç
4. Pencere kapanınca `serverProc.kill()` (Windows'ta `taskkill` davranışı)

> Backend'in ayrı çalıştırılması gerekiyorsa (örn. uzaktan backend'e bağlanmak için), bir terminalde kök dizinden `python ../server.py` çalıştır, sonra bu klasörde `npm start`. DevTools otomatik açılır, istenirse kapatılabilir.

### Gereksinimler

- Node.js 18+ (Electron 33 binary gerektirir)
- Backend için Python 3.11+ (ana dizine bak)

---

## mimari Detay

### Ana Süreç — `main.js`

```
app.whenReady
  └─ startPythonServer()
       ├─ checkServerUp()   # /api/health
       ├─ isPyAvailable(python) → isPyAvailable(python3)
       └─ spawn(pyCmd, ["server.py", "--host", "127.0.0.1", "--port", "8765"])
            └─ tryHealth() until 200
  └─ createWindow()
       ├─ BrowserWindow 1280×900 (min 1000×700)
       ├─ webPreferences: contextIsolation:true, nodeIntegration:false
       ├─ console-message forward → [renderer-console]
       └─ loadURL http://127.0.0.1:8765/
```

### Renderer — Akış

`renderer.js` `index.html`'e `<script type="module">` olarak yüklenir. `db.js`'ten `IDB`'yi içe aktarır.

Veri akışı:

```
[input: tickerInput] → analyze(ticker)
  ├─ fetch /api/analyze?ticker=...
  ├─ renderSignal / renderCompany / renderNews
  ├─ renderTargets / renderAI / renderCharts
  ├─ renderSimulation / renderRisk
  ├─ updatePortfolioPrices / checkAlerts
  └─ subscribeWS() → WebSocket /ws/prices
         └─ (5 sn'de bir) handlePriceUpdate(data)
               ├─ updateWLCache / updatePortfolioCache
               ├─ checkAlertsCache (tetikleme)
               └─ updateSignalPrice (canlı tick)
```

`connectWS` bağlantı kopunca 3 sn sonra yeniden dener.

### Service Worker — `sw.js`

`STATIC_CACHE` ve `API_CACHE` ayrı tutulur.

| Kaynak tipi | Strateji | Cache |
|-------------|----------|-------|
| `/api/*` | Network-first, cache fallback | `borsabot-api-v6` |
| `/`, `styles.css`, `index.html`, CDN scriptleri, fontlar | Cache-first | `borsabot-static-v6` |
| Diğer | Network-first | – |

`activate` eski önbellekleri temizler. `push` event'i ile sistem bildirimi gelir (`data.title/body/url`), `notificationclick` uygulamayı açar.

> Service Worker aynı-origin olduğu için FastAPI tarafında `ELECTRON_DIR`'in `/`'e mount edilmiş olması gerekir — `server.py` zaten bunu yapıyor.

### IndexedDB Şeması — `db.js`

DB: `BorsaBotDB` v3.

| Store | Key | Ek | İçerik |
|-------|-----|-----|--------|
| `watchlist` | `symbol` | – | `{symbol, added}` |
| `portfolio` | `id` | auto-inc | `{symbol, qty, buyPrice, buyDate, sector, added}` |
| `alerts` | `id` | auto-inc | `{symbol, condition, value, triggered, created}` |
| `settings` | `key` | – | `{key, value}` (tema, otomatik yenileme vb.) |
| `cache` | `key` | – | `{key, data, ts}` (5 dk TTL ile API yanıtları) |
| `backtest` | `id` | auto-inc + `ts` index | `{..., ts}` |
| `quotes` | `symbol` | – | `{symbol, data, ts}` (canlı fiyat cache) |

Bulk dışa/içe aktarma: `IDB.exportAll()` / `IDB.importAll(data)` — tüm store'ları gezer.

---

## UI Bileşenleri

### Yan Panel (`<aside id="sidebar">`)

8 sekme: `watchlist`, `portfolio`, `alerts`, `settings` + 4 panel (`heatmap`, `backtest`, `risk`, `ai-portfolio`). Sekme tıklamak hem yan paneli hem ana içerik sekmesini değiştirir.

Sekme paneli arası resize handle (`#sidebarResize`) sürüklenebilir 240–480 px arası.

### Ana İçerik

11 sekme (`#mainTabs`):

1. **teknik** — Mum/çizgi/Heikin-Ashi, 8 zaman dilimi (1G/1H/1A/3A/6A/YTD/1Y/MAX), indikatör toggle, fullscreen, PNG export
2. **sirket** — Şirket kartı + finansal tablo + açıklama
3. **haberler** — Tarih sıralı liste
4. **hedef** — Hedef ızgarası + potansiyel getiri + tavsiye dağılımı
5. **simulasyon** — Geçmiş getiri + Monte Carlo (medyan/en iyi/en kötü)
6. **ai** — AI yorumu + karar rozeti
7. **portfolio** — Aynı sidebar portföyünün sekme görünümü
8. **heatmap** — BIST100 ısı haritası
9. **backtest** — Strateji seçimi, sonuçlar, kayıtlı backtestler
10. **risk** — VaR/CVaR/Sharpe/Sortino/Calmar/MaxDD
11. **ai-portfolio** — Bütçe + risk profili slider + öneri tablosu

Sekme geçmişi (`tabHistory`) — `Alt+←/→` ile ileri-geri, `tabBackBtn` / `tabForwardBtn`.

### Modallar

- `#addWatchlistModal`, `#addPortfolioModal`, `#addAlertModal` — veri girişi
- `#cmdPalette` — Ctrl+K komut listesi
- `#helpModal` — Klavye kısayolları (??)
- `#tourOverlay` — İlk açılış onboarding

### Klavye Kısayolları

| Tuş | İşlev |
|-----|-------|
| `Ctrl+K` | Komut Paleti |
| `Ctrl+B` | Yan panel aç/kapa |
| `Ctrl+T` | Tema değiştir |
| `Ctrl+Shift+S` | Bölünmüş görünüm |
| `Alt+←/→` | Sekme geri/ileri |
| `1`-`7` | Ana sekmeye atla |
| `F` | Tam ekran grafik |
| `?` (iki kez) | Yardım |
| `Esc` | Modal kapat |

---

## Tasarım Sistemi

CSS değişkenleri tema paleti (`styles.css`):

```css
:root[data-theme="dark"] {
  --bg: #0a0a1a;
  --card: #141925;
  --border: #232b3b;
  --accent: #5b8cff;
  --up: #25c26e;
  --down: #f0506e;
  --warn: #f0a830;
  --text: #e7ebf3;
  --text-dim: #9aa3b8;
}
```

Tema değişimi `document.documentElement.dataset.theme = "light"|"dark"` ile olur, `localStorage["bl_theme"]`'e kaydedilir.

Erişilebilirlik dataset anahtarları:

- `data-highcontrast="true"` — yüksek kontrast
- `data-reducemotion="true"` — animasyonları azalt
- `data-colorblind="protan|deutan|tritan"` — renk körlüğü modu

---

## Veri Akışı — Özet

```
Ticker Input ──► analyze(t)
   │
   ├─ GET  /api/analyze?ticker=...   → tam analiz (sinyal+grafik+news+hedef+AI+risk)
   ├─ GET  /api/simulate?...          → Monte Carlo
   ├─ GET  /api/heatmap?index=BIST100 → ısı haritası
   ├─ GET  /api/backtest?...          → strateji
   ├─ GET  /api/risk?...              → metrikler
   ├─ GET  /api/ai/portfolio?...      → bütçe+risk
   └─ WS   /ws/prices                 → canlı yayın
                 │
                 └─ (5 sn) handlePriceUpdate
                       ├─ updateWLRow / updatePortfolioCache
                       ├─ checkAlertsCache → toast + notifySystem + IDB.updateAlert
                       └─ updateSignalPrice (canlı tick)
```

Hata durumunda:

- Backend 200 + `success:false` dönerse → toast `error`, `#alertBanner` gösterilir
- Bağlantı yoksa → offline banner, cache'ten fallback
- Service Worker `/api/*` için cache'ten döndürebilir

---

## Geliştirme İpuçları

- **Renderer'da Hata Ayıklama**: DevTools otomatik açılır. Tüm `console.log` ana süreçte `[renderer-console]` prefix'iyle yazılır
- **Sıfırlama**: Ayarlar paneli → "Tüm Yerel Verileri Temizle" (`localStorage` + `IDB.clearCache()`)
- **SW Sıfırlama**: DevTools → Application → Service Workers → Unregister, veya `navigator.serviceWorker.getRegistrations()` ile
- **Port değiştirme**: `main.js`'te `PORT` ve `HOST`, `[../server.py](../server.py)`'da `--port`
- **Cache TTL**: `db.js`'te `getCache(key, maxAge = 300000)` (5 dk), `server.py`'da `_cache_ttl = 30` sn (fiyat)
- **Yeni Sekme**: `index.html`'e `[role=tab][data-tab=...]` + `<section class="tab-panel" id="panel-..">` + `renderer.js`'te `el.panelX` referansı + render fonksiyonu

### Chart.js Entegrasyonu

`index.html` `<head>`'inde:

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-financial"></script>
```

`renderer.js` global `Chart` ve `Chart`'ın finansal plugin'ini (`candlestick`, `ohlc`) kullanır. Tooltip renkleri `COLORS` sabitinden gelir.

---

## Sık Karşılaşılan Sorunlar

**DevTools açılmıyor** → Sandbox modunda Electron eski sürümlerde otomatik açmaz. `Ctrl+Shift+I` manuel aç.

**WebSocket bağlanmıyor** → Aynı-origin koşulu: Python sunucusunun `ELECTRON_DIR`'i mount ettiğinden emin ol. `server.py` sonunda `app.mount("/", StaticFiles(directory=ELECTRON_DIR, html=True))` var.

**Tema kaybolmuyor** → `localStorage.clear()` → sayfayı yeniden yükle. (Ayarlar panelindeki "Tüm Yerel Verileri Temizle" daha güvenli.)

**Alarmlar tetiklenmiyor** → WebSocket bağlı olmalı. Alerts Only "tetiklenmiş" bayrağını DB'ye yazar, tetiklenmiş tekrar bildirmez. Sıfırlamak için alarmı sil-ekle.

**IndexedDB quota dolu** → DevTools → Application → Storage → "Clear site data".

---

## Yasal Uyarı

Bu uygulama **yatırım tavsiyesi değildir**. Sinyaller, simülasyonlar, AI yorumları yalnızca eğitim/araştırma amaçlıdır. Yatırım kararlarınızı kendi araştırmanıza dayanarak verin.

## Lisans

MIT
