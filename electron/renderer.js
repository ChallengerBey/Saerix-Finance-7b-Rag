/**
 * BORSA BOT v4.0 — Renderer
 * WebSocket live fiyat, IndexedDB, Backtest, Risk, Heatmap, AI Portföy
 */
"use strict";

import { IDB } from "./db.js";

const API = {
  analyze: (t) => `/api/analyze?ticker=${encodeURIComponent(t)}`,
  simulate: (t, a) => `/api/simulate?ticker=${encodeURIComponent(t)}&amount=${encodeURIComponent(a)}`,
  quote: (tickers) => `/api/quote?tickers=${encodeURIComponent(tickers.join(","))}`,
  heatmap: () => "/api/heatmap",
  risk: (t) => `/api/risk?ticker=${encodeURIComponent(t)}`,
  backtest: (t, s, from, to) => `/api/backtest?ticker=${encodeURIComponent(t)}&strategy=${encodeURIComponent(s)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  portfolio_suggest: (budget, risk, count) => `/api/ai/portfolio?budget=${budget}&risk=${risk}&count=${count}`,
  earnings: () => "/api/earnings",
  strategies: () => "/api/strategies",
};

const COLORS = {
  bg: "#0b0e15", card: "#141925", border: "#232b3b",
  accent: "#5b8cff", up: "#25c26e", down: "#f0506e",
  warn: "#f0a830", gold: "#e7c14a", purple: "#9d8cff",
  text: "#e7ebf3", textDim: "#9aa3b8", textFaint: "#5e6678",
  grid: "#232b3b",
};

const TF_LABEL = { "1d": "1G", "1w": "1H", "1m": "1A", "3m": "3A", "6m": "6A", "ytd": "YTD", "1y": "1Y", "max": "MAX" };
const TF_DAYS = { "1d": 2, "1w": 7, "1m": 30, "3m": 90, "6m": 180, "ytd": 252, "1y": 365, "max": 9999 };
const CHART_TYPES = ["candlestick", "line", "heikinashi"];

let charts = [];
let currentTicker = null;
let currentData = null;
let currentCurrency = "TL";
let watchlist = [];
let portfolio = [];
let alerts = [];
let settings = {};
let autoRefreshTimer = null;
let splitMode = false;
let splitTicker = null;
let isOnline = navigator.onLine;
let tourStep = 0;
let tourActive = false;
let ws = null;
let priceCache = {};

/* ------------------------------------------------------------
   DOM REFERANSLARI
   ------------------------------------------------------------ */
const el = {
  tickerInput: document.getElementById("tickerInput"),
  tickerSuffix: document.getElementById("tickerSuffix"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  tabBackBtn: document.getElementById("tabBackBtn"),
  tabForwardBtn: document.getElementById("tabForwardBtn"),
  splitViewBtn: document.getElementById("splitViewBtn"),
  themeToggle: document.getElementById("themeToggle"),
  cmdPaletteBtn: document.getElementById("cmdPaletteBtn"),
  helpBtn: document.getElementById("helpBtn"),
  toggleSidebar: document.getElementById("toggleSidebar"),
  currentTicker: document.getElementById("currentTicker"),

  globalProgress: document.getElementById("globalProgress"),
  progressFill: document.getElementById("progressFill"),
  offlineBanner: document.getElementById("offlineBanner"),
  retryOnline: document.getElementById("retryOnline"),
  toastContainer: document.getElementById("toastContainer"),
  loadingOverlay: document.getElementById("loadingOverlay"),
  loadingText: document.getElementById("loadingText"),
  loadingSteps: document.getElementById("loadingSteps"),
  alertBanner: document.getElementById("alertBanner"),
  placeholder: document.getElementById("placeholder"),
  content: document.getElementById("content"),
  contentWrapper: document.getElementById("contentWrapper"),

  signalCard: document.getElementById("signalCard"),
  signalBadge: document.getElementById("signalBadge"),
  signalEmoji: document.getElementById("signalEmoji"),
  signalText: document.getElementById("signalText"),
  signalPrice: document.getElementById("signalPrice"),
  signalChange: document.getElementById("signalChange"),
  signalScore: document.getElementById("signalScore"),
  signalProgress: document.getElementById("signalProgress"),
  signalDetailsGrid: document.getElementById("signalDetailsGrid"),

  mainTabs: document.getElementById("mainTabs"),
  tabPanels: document.querySelectorAll(".tab-panel"),

  timeframeBtns: document.querySelectorAll("[data-timeframe]"),
  chartTypeBtns: document.querySelectorAll("[data-chart-type]"),
  indSMA20: document.getElementById("indSMA20"),
  indSMA50: document.getElementById("indSMA50"),
  indBB: document.getElementById("indBB"),
  indVWAP: document.getElementById("indVWAP"),
  indVolume: document.getElementById("indVolume"),
  fullscreenChart: document.getElementById("fullscreenChart"),
  exportChart: document.getElementById("exportChart"),

  chartPrice: document.getElementById("chartPrice"),
  chartRSI: document.getElementById("chartRSI"),
  chartMACD: document.getElementById("chartMACD"),
  chartVolume: document.getElementById("chartVolume"),

  companyHeader: document.getElementById("companyHeader"),
  financialBody: document.getElementById("financialBody"),
  companyDesc: document.getElementById("companyDesc"),

  newsList: document.getElementById("newsList"),

  targetBody: document.getElementById("targetBody"),

  amountInput: document.getElementById("amountInput"),
  amountSuffix: document.getElementById("amountSuffix"),
  simulateBtn: document.getElementById("simulateBtn"),
  simResults: document.getElementById("simResults"),

  aiVerdict: document.getElementById("aiVerdict"),
  aiAdvice: document.getElementById("aiAdvice"),

  // Portfolio tab
  portfolioSummary2: document.getElementById("portfolioSummary2"),
  portfolioSectors2: document.getElementById("portfolioSectors2"),
  portfolioBody2: document.getElementById("portfolioBody2"),
  exportPortfolio2: document.getElementById("exportPortfolio2"),
  importPortfolioBtn2: document.getElementById("importPortfolioBtn2"),
  importPortfolioFile2: document.getElementById("importPortfolioFile2"),
  addPortfolioBtn2: document.getElementById("addPortfolioBtn2"),

  // Sidebar
  sidebar: document.getElementById("sidebar"),
  sidebarResize: document.getElementById("sidebarResize"),
  tabWatchlist: document.getElementById("tab-watchlist"),
  tabPortfolio: document.getElementById("tab-portfolio"),
  tabAlerts: document.getElementById("tab-alerts"),
  tabSettings: document.getElementById("tab-settings"),
  watchlist: document.getElementById("watchlist"),
  watchlistCount: document.getElementById("watchlistCount"),
  watchlistEmpty: document.getElementById("watchlistEmpty"),
  addFirstWatchlist: document.getElementById("addFirstWatchlist"),
  addWatchlistBtn: document.getElementById("addWatchlistBtn"),
  portfolioSummary: document.getElementById("portfolioSummary"),
  portfolioSectors: document.getElementById("portfolioSectors"),
  portfolioBody: document.getElementById("portfolioBody"),
  portfolioTable: document.getElementById("portfolioTable"),
  portfolioEmpty: document.getElementById("portfolioEmpty"),
  addFirstPortfolio: document.getElementById("addFirstPortfolio"),
  addPortfolioBtn: document.getElementById("addPortfolioBtn"),
  exportPortfolio: document.getElementById("exportPortfolio"),
  importPortfolioBtn: document.getElementById("importPortfolioBtn"),
  importPortfolioFile: document.getElementById("importPortfolioFile"),
  alertsList: document.getElementById("alertsList"),
  alertsEmpty: document.getElementById("alertsEmpty"),
  addFirstAlert: document.getElementById("addFirstAlert"),
  addAlertBtn: document.getElementById("addAlertBtn"),
  alertsCount: document.getElementById("alertsCount"),
  portfolioCount: document.getElementById("portfolioCount"),

  // Settings
  autoRefreshSelect: document.getElementById("autoRefreshSelect"),
  showVolume: document.getElementById("showVolume"),
  showGrid: document.getElementById("showGrid"),
  animationsEnabled: document.getElementById("animationsEnabled"),
  highContrast: document.getElementById("highContrast"),
  reduceMotion: document.getElementById("reduceMotion"),
  colorBlindMode: document.getElementById("colorBlindMode"),
  dataSourceSelect: document.getElementById("dataSourceSelect"),
  themeRadios: document.querySelectorAll('input[name="theme"]'),
  clearAllData: document.getElementById("clearAllData"),

  // Modals
  addWatchlistModal: document.getElementById("addWatchlistModal"),
  wlTicker: document.getElementById("wlTicker"),
  confirmWatchlistAdd: document.getElementById("confirmWatchlistAdd"),
  addPortfolioModal: document.getElementById("addPortfolioModal"),
  portfolioForm: document.getElementById("portfolioForm"),
  portTicker: document.getElementById("portTicker"),
  portQty: document.getElementById("portQty"),
  portBuyPrice: document.getElementById("portBuyPrice"),
  portBuyDate: document.getElementById("portBuyDate"),
  confirmPortfolioAdd: document.getElementById("confirmPortfolioAdd"),
  addAlertModal: document.getElementById("addAlertModal"),
  alertForm: document.getElementById("alertForm"),
  alertTicker: document.getElementById("alertTicker"),
  alertCondition: document.getElementById("alertCondition"),
  alertValue: document.getElementById("alertValue"),
  confirmAlertAdd: document.getElementById("confirmAlertAdd"),
  cmdPalette: document.getElementById("cmdPalette"),
  cmdInput: document.getElementById("cmdInput"),
  cmdResults: document.getElementById("cmdResults"),
  helpModal: document.getElementById("helpModal"),
  helpCategories: document.getElementById("helpCategories"),
  tourOverlay: document.getElementById("tourOverlay"),
  tourStep: document.getElementById("tourStep"),
  tourTitle: document.getElementById("tourTitle"),
  tourProgress: document.getElementById("tourProgress"),
  tourDesc: document.getElementById("tourDesc"),
  tourSkip: document.getElementById("tourSkip"),
  tourNext: document.getElementById("tourNext"),

  // New panels
  panelHeatmap: document.getElementById("panel-heatmap"),
  panelBacktest: document.getElementById("panel-backtest"),
  panelRisk: document.getElementById("panel-risk"),
  panelAIPortfolio: document.getElementById("panel-ai-portfolio"),

  // Main content tab panels (unique IDs)
  panelHeatmapMain: document.getElementById("heatmapContent-main"),
  panelBacktestMain: document.getElementById("backtestContent-main"),
  panelRiskMain: document.getElementById("riskContent-main"),
  panelAIPortfolioMain: document.getElementById("aiPortfolioContent-main"),
};

/* ------------------------------------------------------------
   UTILITY
   ------------------------------------------------------------ */
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function formatMoney(n, cur = currentCurrency) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const c = cur ? ` ${cur}` : "";
  const a = Math.abs(n);
  if (a >= 1e12) return (n / 1e12).toFixed(2) + "T" + c;
  if (a >= 1e9) return (n / 1e9).toFixed(2) + "B" + c;
  if (a >= 1e6) return (n / 1e6).toFixed(2) + "M" + c;
  if (a >= 1e3) return (n / 1e3).toFixed(2) + "K" + c;
  return n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + c;
}
function formatNum(n, d = 2) { if (n === null || n === undefined || isNaN(n)) return "—"; return Number(n).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }); }
function formatPct(n) { if (n === null || n === undefined || isNaN(n)) return "—"; const s = n >= 0 ? "+" : ""; return s + Number(n).toFixed(2) + "%"; }
function cls(n) { if (n === null || n === undefined || isNaN(n)) return ""; return n > 0 ? "pos" : n < 0 ? "neg" : "neu"; }
function escapeHtml(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function throttle(fn, ms) { let last = 0; return (...a) => { const now = Date.now(); if (now - last >= ms) { last = now; fn(...a); } }; }
function save(key, val) { localStorage.setItem(key, JSON.stringify(val)); }
function load(key, def) { try { return JSON.parse(localStorage.getItem(key)) ?? def; } catch { return def; } }
function setTheme(t) { document.documentElement.dataset.theme = t; save("bl_theme", t); updateThemeIcons(t); }
function getTheme() { return document.documentElement.dataset.theme || "dark"; }
function updateThemeIcons(t) { const sun = $(".icon-sun", el.themeToggle); const moon = $(".icon-moon", el.themeToggle); if (t === "light") { sun.style.display = "none"; moon.style.display = "block"; } else { sun.style.display = "block"; moon.style.display = "none"; } }
function applyColorBlind(mode) { document.documentElement.dataset.colorblind = mode || ""; save("bl_colorblind", mode || ""); }
function applyHighContrast(on) { document.documentElement.dataset.highcontrast = on ? "true" : ""; }
function applyReduceMotion(on) { document.documentElement.dataset.reducemotion = on ? "true" : ""; }

/* ------------------------------------------------------------
   TOAST / NOTIFICATION
   ------------------------------------------------------------ */
function toast(msg, type = "info", title = "", duration = 5000) {
  const icons = { success: "✓", error: "✕", warning: "⚠", info: "ℹ" };
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.innerHTML = `<div class="toast-icon">${icons[type]}</div><div class="toast-content"><div class="toast-title">${escapeHtml(title)}</div><div class="toast-message">${escapeHtml(msg)}</div></div><button class="toast-close" aria-label="Kapat">✕</button><div class="toast-progress" style="background: var(--${type === "success" ? "up" : type === "error" ? "down" : type === "warning" ? "warn" : "accent"})"></div>`;
  t.querySelector(".toast-close").onclick = () => t.classList.add("closing"), setTimeout(() => t.remove(), 200);
  t.querySelector(".toast-progress").style.animationDuration = duration + "ms";
  el.toastContainer.appendChild(t);
  setTimeout(() => { if (t.parentNode) t.classList.add("closing"); setTimeout(() => t.remove(), 200); }, duration);
  return t;
}
function notifySystem(title, body) {
  if (Notification.permission === "granted") new Notification(title, { body, icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📈</text></svg>" });
  else if (Notification.permission !== "denied") Notification.requestPermission();
}

/* ------------------------------------------------------------
   LOADING / PROGRESS
   ------------------------------------------------------------ */
const LOAD_STAGES = ["Veriler çekiliyor", "Göstergeler hesaplanıyor", "Şirket bilgileri alınıyor", "Haberler taranıyor", "AI yorumu bekleniyor", "Risk metrikleri hesaplanıyor", "Backtest hazırlanıyor"];
function showLoading(text = "Veriler çekiliyor...") { el.loadingOverlay.classList.remove("hidden"); el.loadingText.textContent = text; el.loadingSteps.innerHTML = LOAD_STAGES.map((s, i) => `<div class="step" data-step="${i}">${s}</div>`).join(""); setStep(0); }
function setStep(i) { $$(".step", el.loadingSteps).forEach((s, idx) => { s.classList.toggle("active", idx === i); s.classList.toggle("done", idx < i); }); }
function hideLoading() { el.loadingOverlay.classList.add("hidden"); }
function setGlobalProgress(p) { el.progressFill.style.width = p + "%"; if (p >= 100) setTimeout(() => el.globalProgress.hidden = true, 500); else el.globalProgress.hidden = false; }

/* ------------------------------------------------------------
   OFFLINE / ONLINE
   ------------------------------------------------------------ */
window.addEventListener("online", () => { isOnline = true; el.offlineBanner.classList.add("hidden"); toast("İnternet bağlantısı geri geldi", "success", "Çevrimiçi"); refreshCurrent(); });
window.addEventListener("offline", () => { isOnline = false; el.offlineBanner.classList.remove("hidden"); toast("İnternet bağlantısı kesildi — önbellekli veri gösteriliyor", "warning", "Çevrimdışı"); });
el.retryOnline.onclick = () => { if (navigator.onLine) { isOnline = true; el.offlineBanner.classList.add("hidden"); toast("Bağlantı tekrar sağlandı", "success"); refreshCurrent(); } else toast("Hâlâ çevrimdışı", "warning"); };

/* ------------------------------------------------------------
   SIDEBAR TABS & RESIZE
   ------------------------------------------------------------ */
function switchSidebarPanel(name) {
  $$(".sidebar-tab").forEach(t => t.classList.toggle("active", t.dataset.panel === name));
  $$(".sidebar-panel").forEach(p => p.classList.toggle("active", p.id === "panel-" + name));
  $$(".sidebar-tab").forEach(t => t.setAttribute("aria-selected", t.dataset.panel === name));
  // Also switch main content tab (use -main suffix for panels that have it)
  const mainTabNames = { heatmap: "heatmap", backtest: "backtest", risk: "risk", "ai-portfolio": "ai-portfolio" };
  const tabName = mainTabNames[name] || name;
  switchTab(tabName);
}
$$(".sidebar-tab").forEach(t => t.onclick = () => switchSidebarPanel(t.dataset.panel));

let resizeStartX = 0, resizeStartW = 0;
el.sidebarResize.addEventListener("mousedown", e => { e.preventDefault(); resizeStartX = e.clientX; resizeStartW = el.sidebar.offsetWidth; document.body.style.cursor = "col-resize"; el.sidebarResize.classList.add("dragging"); window.addEventListener("mousemove", onResizeMove); window.addEventListener("mouseup", onResizeUp); });
function onResizeMove(e) { const w = Math.min(Math.max(el.sidebarResize.getBoundingClientRect().left + (e.clientX - resizeStartX), 240), 480); el.sidebar.style.width = w + "px"; document.documentElement.style.setProperty("--sidebar-w", w + "px"); }
function onResizeUp() { window.removeEventListener("mousemove", onResizeMove); window.removeEventListener("mouseup", onResizeUp); document.body.style.cursor = ""; el.sidebarResize.classList.remove("dragging"); }

/* ------------------------------------------------------------
   MAIN TABS
   ------------------------------------------------------------ */
let tabHistory = [];
let tabHistoryIndex = -1;
let currentTab = "teknik";

function switchTab(name, pushHistory = true) {
  if (name === currentTab) return;

  // Push old tab to history before switching
  if (pushHistory) {
    // Trim forward history if we're not at the end
    if (tabHistoryIndex < tabHistory.length - 1) {
      tabHistory = tabHistory.slice(0, tabHistoryIndex + 1);
    }
    tabHistory.push(currentTab);
    tabHistoryIndex = tabHistory.length - 1;
  }

  currentTab = name;
  $$("#mainTabs [role=tab]").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  // Match panel IDs: some have -main suffix (heatmap, backtest, risk, ai-portfolio), others don't
  $$(".tab-panel").forEach(p => {
    const match = p.id === "panel-" + name || p.id === "panel-" + name + "-main";
    p.classList.toggle("active", match);
  });
  $$("#mainTabs [role=tab]").forEach(t => t.setAttribute("aria-selected", t.dataset.tab === name));
  setTimeout(() => charts.forEach(c => c.resize()), 50);
}

function goBackTab() {
  if (tabHistoryIndex <= 0) return;
  // Save current tab into history
  tabHistory.push(currentTab);
  tabHistoryIndex++;
  const prevTab = tabHistory[tabHistoryIndex - 1];
  tabHistoryIndex--;
  switchTab(prevTab, false);
}

function goForwardTab() {
  if (tabHistoryIndex >= tabHistory.length - 1) return;
  tabHistoryIndex++;
  const nextTab = tabHistory[tabHistoryIndex];
  switchTab(nextTab, false);
}

$$("#mainTabs [role=tab]").forEach(t => t.onclick = () => switchTab(t.dataset.tab));

/* ------------------------------------------------------------
   CHART TOOLBAR
   ------------------------------------------------------------ */
let currentTimeframe = "1d";
let currentChartType = "candlestick";
function setTimeframe(tf) { currentTimeframe = tf; $$("[data-timeframe]").forEach(b => b.classList.toggle("active", b.dataset.timeframe === tf)); redrawCharts(); }
function setChartType(ct) { currentChartType = ct; $$("[data-chart-type]").forEach(b => b.classList.toggle("active", b.dataset.chartType === ct)); redrawCharts(); }
$$("[data-timeframe]").forEach(b => b.onclick = () => setTimeframe(b.dataset.timeframe));
$$("[data-chart-type]").forEach(b => b.onclick = () => setChartType(b.dataset.chartType));
["indSMA20", "indSMA50", "indBB", "indVWAP", "indVolume"].forEach(id => {
  const cb = document.getElementById(id);
  if (cb) cb.onchange = () => charts.forEach(ch => ch.update());
});
el.fullscreenChart.onclick = () => { const c = charts[0]; if (c.canvas.requestFullscreen) c.canvas.requestFullscreen(); };
el.exportChart.onclick = () => { const c = charts[0]; const link = document.createElement("a"); link.href = c.toBase64Image(); link.download = `${currentTicker}_${currentChartType}_${Date.now()}.png`; link.click(); };

/* ------------------------------------------------------------
   WATCHLIST
   ------------------------------------------------------------ */
async function renderWatchlist() {
  watchlist = await IDB.getWatchlist();
  el.watchlist.innerHTML = "";
  if (watchlist.length === 0) { el.watchlistEmpty.hidden = false; el.watchlist.hidden = true; el.watchlistCount.textContent = "0"; return; }
  el.watchlistEmpty.hidden = true; el.watchlist.hidden = false; el.watchlistCount.textContent = watchlist.length;
  watchlist.forEach((item, i) => {
    const li = document.createElement("li");
    li.className = "watchlist-item" + (item.symbol === currentTicker ? " selected" : "");
    li.innerHTML = `<span class="wl-symbol">${escapeHtml(item.symbol)}</span><span class="wl-price" id="wlPrice-${i}">—</span><span class="wl-change" id="wlChange-${i}">—</span><button class="icon-btn wl-remove" aria-label="Kaldır" data-index="${i}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
    li.querySelector(".wl-remove").onclick = (e) => { e.stopPropagation(); removeWatchlist(i); };
    li.onclick = () => analyze(item.symbol);
    el.watchlist.appendChild(li);
    if (item.symbol === currentTicker && currentData) updateWLRow(i, currentData);
  });
  el.watchlistCount.textContent = watchlist.length;
}
function updateWLRow(i, data) {
  const p = $(`#wlPrice-${i}`), c = $(`#wlChange-${i}`); if (!p || !c) return;
  p.textContent = formatMoney(data.price);
  c.textContent = formatPct(data.change_pct); c.className = "wl-change " + cls(data.change_pct);
}
async function addWatchlist(sym) { sym = sym.trim().toUpperCase(); if (!sym) return; if (watchlist.find(w => w.symbol === sym)) return toast("Zaten listede", "warning"); await IDB.addWatchlist(sym); watchlist.push({ symbol: sym, added: Date.now() }); renderWatchlist(); toast(`${sym} eklendi`, "success"); }
async function removeWatchlist(i) { const sym = watchlist[i].symbol; await IDB.removeWatchlist(sym); watchlist.splice(i, 1); renderWatchlist(); toast("Kaldırıldı", "info"); }
function toggleWatchlistSym(sym) { const idx = watchlist.findIndex(w => w.symbol === sym); if (idx >= 0) removeWatchlist(idx); else addWatchlist(sym); }
el.addWatchlistBtn.onclick = () => { el.wlTicker.value = ""; el.addWatchlistModal.showModal(); el.wlTicker.focus(); };
el.addFirstWatchlist.onclick = () => el.addWatchlistBtn.onclick();
el.confirmWatchlistAdd.onclick = () => { const v = el.wlTicker.value.trim().toUpperCase(); if (v) addWatchlist(v); el.addWatchlistModal.close(); };

/* ------------------------------------------------------------
   PORTFOLIO (Sidebar + Tab)
   ------------------------------------------------------------ */
async function renderPortfolio() {
  portfolio = await IDB.getPortfolio();
  const bodies = [el.portfolioBody, el.portfolioBody2];
  const summaries = [el.portfolioSummary, el.portfolioSummary2];
  const tables = [el.portfolioTable, document.getElementById("portfolioTable2")];
  const empties = [el.portfolioEmpty, document.getElementById("portfolioEmpty2") || el.portfolioEmpty];
  const sectors = [el.portfolioSectors, el.portfolioSectors2];
  const counts = [el.portfolioCount, document.getElementById("portfolioCount2") || el.portfolioCount];

  bodies.forEach(b => b.innerHTML = "");
  if (portfolio.length === 0) { summaries.forEach(s => s.hidden = true); tables.forEach(t => t.hidden = true); empties.forEach(e => e.hidden = false); counts.forEach(c => c.textContent = "0"); return; }
  summaries.forEach(s => s.hidden = false); tables.forEach(t => t.hidden = false); empties.forEach(e => e.hidden = true);
  counts.forEach(c => c.textContent = portfolio.length);

  let totalVal = 0, totalCost = 0, dailyPL = 0;
  portfolio.forEach((p, i) => {
    const row = document.createElement("tr");
    const currentPrice = p.currentPrice ?? p.buyPrice;
    const value = p.qty * currentPrice;
    const cost = p.qty * p.buyPrice;
    const pl = value - cost;
    const plPct = cost ? (pl / cost) * 100 : 0;
    const dailyChange = p.dailyChangePct ?? 0;
    dailyPL += p.qty * currentPrice * dailyChange / 100;
    totalVal += value; totalCost += cost;
    const plCls = cls(pl);
    row.innerHTML = `<td><strong>${escapeHtml(p.symbol)}</strong></td><td>${formatNum(p.qty, 0)}</td><td>${formatMoney(p.buyPrice)}</td><td>${formatMoney(currentPrice)}</td><td class="${plCls}">${formatMoney(pl)}</td><td class="${plCls}">${formatPct(plPct)}</td><td>${formatMoney(value)}</td><td><button class="icon-btn" data-del="${i}" aria-label="Sil"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></td>`;
    bodies.forEach(b => b.appendChild(row.cloneNode(true)));
  });
  const totalPL = totalVal - totalCost;
  const totalPLPct = totalCost ? (totalPL / totalCost) * 100 : 0;
  summaries.forEach(s => { if (s) s.innerHTML = `<div class="summary-row"><span>Toplam Değer</span><strong>${formatMoney(totalVal)}</strong></div><div class="summary-row"><span>Toplam K/Z</span><strong class="${cls(totalPL)}">${formatMoney(totalPL)}</strong></div><div class="summary-row"><span>Günlük Değişim</span><strong class="${cls(dailyPL)}">${formatMoney(dailyPL)}</strong></div>`; });
  const sectorData = {};
  portfolio.forEach(p => { const cur = p.currentPrice ?? p.buyPrice; const val = p.qty * cur; sectorData[p.sector || "Diğer"] = (sectorData[p.sector || "Diğer"] || 0) + val; });
  if (el.sectorChart) drawSectorChart(sectorData);
  if (el.sectorChart2) drawSectorChart(sectorData, el.sectorChart2);
  $$(".portfolio-table tbody button[data-del]").forEach(btn => btn.onclick = () => removePortfolio(+btn.dataset.del));
}
function drawSectorChart(data, canvas = el.sectorChart) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (canvas._chart) canvas._chart.destroy();
  const labels = Object.keys(data);
  const values = Object.values(data);
  const colors = labels.map((_, i) => [`var(--accent)`, `var(--up)`, `var(--down)`, `var(--warn)`, `var(--gold)`, `var(--purple)`][i % 6]);
  const cfg = { type: "doughnut", data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] }, options: { responsive: true, maintainAspectRatio: true, cutout: "70%", plugins: { legend: { position: "right", labels: { color: COLORS.textDim, font: { family: "Inter", size: 11 }, padding: 16, usePointStyle: true, pointStyle: "circle" } }, tooltip: { backgroundColor: "#1b2130", titleColor: COLORS.text, bodyColor: COLORS.textDim, borderColor: COLORS.border, borderWidth: 1, padding: 10, cornerRadius: 8, callbacks: { label: ctx => `${ctx.label}: ${formatMoney(ctx.parsed)}` } } } } };
  canvas._chart = new Chart(ctx, cfg);
}
async function addPortfolio(p) { await IDB.addPortfolio(p); portfolio.push(p); renderPortfolio(); toast(`${p.symbol} eklendi`, "success"); updatePortfolioPrices(); }
async function removePortfolio(i) { const id = portfolio[i].id; await IDB.removePortfolio(id); portfolio.splice(i, 1); renderPortfolio(); toast("Silindi", "info"); }
async function updatePortfolioPrices() { if (!portfolio.length) return; const symbols = [...new Set(portfolio.map(p => p.symbol))]; try { const res = await fetch(API.quote(symbols)); const data = await res.json(); portfolio.forEach(p => { const q = data[p.symbol] || data[p.symbol + ".IS"]; if (q) { p.currentPrice = q.price; p.dailyChangePct = q.change_pct; } }); renderPortfolio(); } catch (e) { console.error(e); } }
function exportPortfolio() { if (!portfolio.length) return toast("Boş", "warning"); const csv = ["Sembol,Adet,Alış Fiyatı,Alış Tarihi,Sektör"].concat(portfolio.map(p => `${p.symbol},${p.qty},${p.buyPrice},${p.buyDate},${p.sector || ""}`)).join("\n"); downloadCSV(csv, "portfoy.csv"); }
function downloadCSV(csv, name) { const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url); }
el.addPortfolioBtn.onclick = el.addPortfolioBtn2.onclick = () => { el.portTicker.value = currentTicker || ""; el.portQty.value = 1; el.portBuyPrice.value = ""; el.portBuyDate.value = new Date().toISOString().split("T")[0]; el.addPortfolioModal.showModal(); el.portTicker.focus(); };
el.addFirstPortfolio.onclick = () => el.addPortfolioBtn.onclick();
el.confirmPortfolioAdd.onclick = () => { const p = { symbol: el.portTicker.value.trim().toUpperCase(), qty: +el.portQty.value, buyPrice: +el.portBuyPrice.value, buyDate: el.portBuyDate.value, sector: "" }; if (!p.symbol || !p.qty || !p.buyPrice) return toast("Eksik", "warning"); addPortfolio(p); el.addPortfolioModal.close(); };
el.portfolioForm.addEventListener("submit", e => e.preventDefault());
el.exportPortfolio.onclick = el.exportPortfolio2.onclick = exportPortfolio;
el.importPortfolioBtn.onclick = el.importPortfolioBtn2.onclick = () => el.importPortfolioFile.click();
el.importPortfolioFile.onchange = el.importPortfolioFile2.onchange = e => { const f = e.target.files[0]; if (!f) return; const reader = new FileReader(); reader.onload = ev => { const lines = ev.target.result.split(/\r?\n/).slice(1); lines.forEach(l => { const [sym, qty, price, date, sector] = l.split(","); if (sym) addPortfolio({ symbol: sym.trim(), qty: +qty, buyPrice: +price, buyDate: date.trim(), sector: (sector || "").trim() }); }); renderPortfolio(); }; reader.readAsText(f); e.target.value = ""; };

/* ------------------------------------------------------------
   ALERTS
   ------------------------------------------------------------ */
async function renderAlerts() {
  alerts = await IDB.getAlerts();
  el.alertsList.innerHTML = "";
  if (alerts.length === 0) { el.alertsEmpty.hidden = false; el.alertsList.hidden = true; el.alertsCount.textContent = "0"; return; }
  el.alertsEmpty.hidden = true; el.alertsList.hidden = false; el.alertsCount.textContent = alerts.length;
  alerts.forEach((a, i) => {
    const li = document.createElement("li"); li.className = "alert-item";
    li.innerHTML = `<span class="alert-symbol">${escapeHtml(a.symbol)}</span><span class="alert-condition">${escapeHtml(a.condition)}</span><span class="alert-value">${formatNum(a.value)}</span><span class="alert-triggered ${a.triggered ? "" : "hidden"}">⚡ Tetiklendi</span><button class="icon-btn" data-del="${i}" aria-label="Sil"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
    li.querySelector("button[data-del]").onclick = () => removeAlert(i);
    el.alertsList.appendChild(li);
  });
  el.alertsCount.textContent = alerts.length;
}
function checkAlerts(data) { if (!data) return; alerts.forEach(a => { if (a.symbol !== currentTicker) return; let val, ok = false; if (a.condition === "above") { val = data.price; ok = val >= a.value; } else if (a.condition === "below") { val = data.price; ok = val <= a.value; } else if (a.condition === "rsi_above") { val = data.rsi; ok = val >= a.value; } else if (a.condition === "rsi_below") { val = data.rsi; ok = val <= a.value; } else if (a.condition === "pct_change") { val = data.change_pct; ok = val >= a.value; } if (ok && !a.triggered) { a.triggered = true; a.triggeredAt = Date.now(); IDB.updateAlert(a.id, a); toast(`🚨 Alarm: ${a.symbol} ${a.condition} ${a.value} (güncel: ${val})`, "warning", "ALARM TETİKLENDİ"); notifySystem("Fiyat Alarmı", `${a.symbol} hedefe ulaştı`); renderAlerts(); } }); }
async function addAlert(a) { await IDB.addAlert(a); alerts.push({ ...a, triggered: false, created: Date.now() }); renderAlerts(); toast("Alarm kuruldu", "success"); }
async function removeAlert(i) { const id = alerts[i].id; await IDB.removeAlert(id); alerts.splice(i, 1); renderAlerts(); toast("Silindi", "info"); }
el.addAlertBtn.onclick = el.addFirstAlert.onclick = () => { el.alertTicker.value = currentTicker || ""; el.alertValue.value = ""; el.addAlertModal.showModal(); el.alertTicker.focus(); };
el.confirmAlertAdd.onclick = () => { const a = { symbol: el.alertTicker.value.trim().toUpperCase(), condition: el.alertCondition.value, value: +el.alertValue.value }; if (!a.symbol || isNaN(a.value)) return toast("Eksik", "warning"); addAlert(a); el.addAlertModal.close(); };
el.alertForm.addEventListener("submit", e => e.preventDefault());

/* ------------------------------------------------------------
   SETTINGS
   ------------------------------------------------------------ */
async function loadSettings() {
  settings = await IDB.getSettings();
  const s = settings;
  if (s.theme) setTheme(s.theme);
  if (s.autoRefresh) { el.autoRefreshSelect.value = s.autoRefresh; startAutoRefresh(s.autoRefresh); }
  if (s.showVolume !== undefined) el.showVolume.checked = s.showVolume;
  if (s.showGrid !== undefined) el.showGrid.checked = s.showGrid;
  if (s.animations !== undefined) el.animationsEnabled.checked = s.animations;
  if (s.highContrast) { el.highContrast.checked = s.highContrast; applyHighContrast(s.highContrast); }
  if (s.reduceMotion) { el.reduceMotion.checked = s.reduceMotion; applyReduceMotion(s.reduceMotion); }
  if (s.colorBlind) { el.colorBlindMode.checked = s.colorBlind; applyColorBlind(s.colorBlind); }
  if (s.dataSource) el.dataSourceSelect.value = s.dataSource;
}
function saveSettings() {
  settings = {
    theme: getTheme(),
    autoRefresh: +el.autoRefreshSelect.value,
    showVolume: el.showVolume.checked,
    showGrid: el.showGrid.checked,
    animations: el.animationsEnabled.checked,
    highContrast: el.highContrast.checked,
    reduceMotion: el.reduceMotion.checked,
    colorBlind: el.colorBlindMode.checked,
    dataSource: el.dataSourceSelect.value,
  };
  Object.entries(settings).forEach(([k, v]) => IDB.setSetting(k, v));
}
el.themeRadios.forEach(r => r.onchange = () => { setTheme(r.value); saveSettings(); });
el.autoRefreshSelect.onchange = () => { startAutoRefresh(+el.autoRefreshSelect.value); saveSettings(); };
[el.showVolume, el.showGrid, el.animationsEnabled, el.highContrast, el.reduceMotion, el.colorBlindMode].forEach(c => { if (!c) return; c.onchange = () => { if (c === el.highContrast) applyHighContrast(c.checked); else if (c === el.reduceMotion) applyReduceMotion(c.checked); else if (c === el.colorBlindMode) applyColorBlind(c.checked ? "protan" : ""); saveSettings(); }; });
el.dataSourceSelect.onchange = saveSettings;
el.clearAllData.onclick = () => { if (confirm("TÜM yerel veriler (watchlist, portföy, alarmlar, ayarlar) silinecek. Emin misin?")) { ["bl_watchlist","bl_portfolio","bl_alerts","bl_settings","bl_theme","bl_colorblind"].forEach(k => localStorage.removeItem(k)); IDB.clearCache(); location.reload(); } };

/* ------------------------------------------------------------
   AUTO REFRESH
   ------------------------------------------------------------ */
function startAutoRefresh(ms) { if (autoRefreshTimer) clearInterval(autoRefreshTimer); if (ms > 0) { autoRefreshTimer = setInterval(() => { if (currentTicker && document.visibilityState === "visible") refreshCurrent(); }, ms); } }
function refreshCurrent() { if (currentTicker) analyze(currentTicker, true); }

/* ------------------------------------------------------------
   WEBSOCKET - Live Prices
   ------------------------------------------------------------ */
function connectWS() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws/prices`);
  ws.onopen = () => { console.log("[WS] Connected"); subscribeWS(); };
  ws.onmessage = (e) => { try { const msg = JSON.parse(e.data); if (msg.type === "prices") handlePriceUpdate(msg.data); } catch (err) { console.error(err); } };
  ws.onclose = () => { console.log("[WS] Disconnected, retrying..."); setTimeout(connectWS, 3000); };
  ws.onerror = (err) => console.error("[WS] Error", err);
}
function subscribeWS() { if (!ws || ws.readyState !== WebSocket.OPEN) return; const symbols = [...new Set([currentTicker, ...watchlist.map(w => w.symbol), ...portfolio.map(p => p.symbol)])].filter(Boolean); if (symbols.length) ws.send(JSON.stringify({ action: "subscribe", tickers: symbols })); }
function handlePriceUpdate(data) { Object.entries(data).forEach(([sym, q]) => { priceCache[sym] = q; updateWLCache(sym, q); updatePortfolioCache(sym, q); checkAlertsCache(sym, q); if (sym === currentTicker) updateSignalPrice(q); }); }
function updateWLCache(sym, q) { const idx = watchlist.findIndex(w => w.symbol === sym); if (idx >= 0) updateWLRow(idx, { price: q.price, change_pct: q.change_pct }); }
function updatePortfolioCache(sym, q) { const idx = portfolio.findIndex(p => p.symbol === sym); if (idx >= 0) { portfolio[idx].currentPrice = q.price; portfolio[idx].dailyChangePct = q.change_pct; renderPortfolio(); } }
function checkAlertsCache(sym, q) { alerts.forEach(a => { if (a.symbol !== sym || a.triggered) return; let val, ok = false; if (a.condition === "above") { val = q.price; ok = val >= a.value; } else if (a.condition === "below") { val = q.price; ok = val <= a.value; } else if (a.condition === "pct_change") { val = q.change_pct; ok = val >= a.value; } if (ok) { a.triggered = true; a.triggeredAt = Date.now(); IDB.updateAlert(a.id, a); toast(`🚨 Alarm: ${a.symbol} ${a.condition} ${a.value} (güncel: ${val})`, "warning", "ALARM"); notifySystem("Fiyat Alarmı", `${a.symbol} hedefe ulaştı`); renderAlerts(); } }); }
function updateSignalPrice(q) { if (!q || !el.signalPrice) return; el.signalPrice.textContent = formatMoney(q.price, currentCurrency); el.signalChange.textContent = `${formatNum(q.change)} (${formatPct(q.change_pct)})`; el.signalChange.className = "change " + cls(q.change_pct); }

/* ------------------------------------------------------------
   CORE ANALYZE FLOW
   ------------------------------------------------------------ */
async function analyze(ticker, silent = false) {
  if (!ticker) return;
  ticker = ticker.trim().toUpperCase();
  if (!silent) { showLoading(); setGlobalProgress(10); }
  currentTicker = ticker;
  addWatchlist(ticker);

  try {
    const res = await fetch(API.analyze(ticker));
    const data = await res.json();
    if (!data.success) throw new Error(data.error || "Analiz başarısız");
    currentData = data;
    currentCurrency = data.company?.currency || "TL";

    if (!silent) { setGlobalProgress(50); setStep(1); }
    renderSignal(data);
    renderCompany(data.company);
    renderNews(data.news);
    renderTargets(data.targets);
    renderAI(data.ai_advice, data.signal);
    await renderCharts(data.chart);
    renderSimulation(data);
    renderRisk(data.risk);
    await updatePortfolioPrices();
    checkAlerts(data);
    updateWLRow(watchlist.findIndex(w => w.symbol === ticker), data);
    await renderWatchlist();

    // Subscribe WS
    subscribeWS();

    // Load extra panels
    loadHeatmap();
    loadBacktestPanel();
    loadRiskPanel();
    loadAIPortfolio();

    el.placeholder.classList.add("hidden");
    el.content.classList.remove("hidden");

    el.currentTicker.textContent = ticker;
    el.tickerSuffix.textContent = data.ticker.includes(".IS") ? ".IS" : "";
    el.tickerSuffix.style.display = ticker.includes(".") ? "none" : "inline";

    el.amountSuffix.textContent = currentCurrency === "TRY" ? "₺" : currentCurrency === "USD" ? "$" : currentCurrency === "EUR" ? "€" : currentCurrency;

    if (!silent) { setGlobalProgress(100); setStep(LOAD_STAGES.length - 1); }
    toast(`${ticker} analizi tamamlandı`, "success");
  } catch (err) {
    console.error(err);
    if (!silent) toast(err.message, "error", "Hata");
    el.alertBanner.textContent = "Hata: " + err.message; el.alertBanner.classList.remove("hidden");
  } finally { if (!silent) { hideLoading(); setTimeout(() => el.globalProgress.hidden = true, 500); } }
}


/* ------------------------------------------------------------
   RENDER FUNCTIONS
   ------------------------------------------------------------ */
function renderSignal(d) {
  const sg = d.signal || {};
  const chg = d.change_pct;
  el.signalBadge.style.setProperty("--vc", sg.color || COLORS.accent);
  el.signalEmoji.textContent = sg.emoji || "🤖";
  el.signalText.textContent = sg.text || "BEKLE";
  el.signalText.style.color = sg.color || COLORS.accent;
  el.signalPrice.textContent = formatMoney(d.price, d.company?.currency);
  el.signalChange.textContent = `${formatNum(d.change)} (${formatPct(chg)})`;
  el.signalChange.className = "change " + cls(chg);
  el.signalScore.textContent = sg.score ?? 0;
  el.signalProgress.style.width = (sg.score ?? 0) + "%";
  el.signalProgress.style.background = sg.color || COLORS.accent;

  el.signalDetailsGrid.innerHTML = "";
  (sg.details || []).forEach(d => {
    const div = document.createElement("div"); div.className = "detail-item";
    div.innerHTML = `<div class="detail-head"><span class="detail-name">${escapeHtml(d.name)}</span><span class="detail-signal" style="color:${d.color}">${escapeHtml(d.signal)}</span></div><div class="detail-points" style="color:var(--text-dim)">${escapeHtml(d.reason)} ${d.points !== undefined ? ` (${d.points > 0 ? "+" : ""}${d.points} puan)` : ""}</div>`;
    el.signalDetailsGrid.appendChild(div);
  });
}

function renderCompany(c) {
  if (!c) { el.companyHeader.innerHTML = `<div class="company-name">Veri yok</div>`; el.financialBody.innerHTML = ""; el.companyDesc.textContent = "—"; return; }
  el.companyHeader.innerHTML = `<div class="company-name">${escapeHtml(c.name)}</div><div class="company-tags"><span class="tag">${escapeHtml(c.sector)}</span><span class="tag">${escapeHtml(c.industry)}</span><span class="tag">${escapeHtml(c.exchange)}</span></div>${c.website ? `<div class="company-website"><a href="${c.website}" target="_blank" rel="noopener">🌐 ${c.website}</a></div>` : ""}`;
  const rows = [
    ["Piyasa Değeri", formatMoney(c.market_cap, c.currency)],
    ["F/K Oranı", c.pe_ratio ? formatNum(c.pe_ratio) : "—"],
    ["İleri F/K", c.forward_pe ? formatNum(c.forward_pe) : "—"],
    ["Temettü Verimi", c.dividend_yield ? formatPct(c.dividend_yield * 100) : "—"],
    ["52H Yüksek", c.week52_high ? formatMoney(c.week52_high, c.currency) : "—"],
    ["52H Düşük", c.week52_low ? formatMoney(c.week52_low, c.currency) : "—"],
    ["Ort. Hacim", c.avg_volume ? formatNum(c.avg_volume, 0) : "—"],
    ["Çalışan", c.employees ? formatNum(c.employees, 0) : "—"],
  ];
  el.financialBody.innerHTML = rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
  el.companyDesc.textContent = c.description || "Açıklama yok.";
}

function renderNews(news) {
  el.newsList.innerHTML = "";
  if (!news || !news.length) { el.newsList.innerHTML = '<div class="news-empty">Haber bulunamadı.</div>'; return; }
  news.forEach(n => {
    const div = document.createElement("div"); div.className = "news-item";
    div.innerHTML = `<div class="news-title">${escapeHtml(n.title)}</div><div class="news-meta">${escapeHtml(n.publisher)} · ${n.date ? new Date(n.date).toLocaleString("tr-TR") : ""}</div>`;
    if (n.link && n.link !== "#") div.onclick = () => window.open(n.link, "_blank", "noopener");
    el.newsList.appendChild(div);
  });
}

function renderTargets(t) {
  el.targetBody.innerHTML = "";
  if (!t || !t.available) { el.targetBody.innerHTML = '<div class="news-empty">📭 Bu hisse için analist hedef verisi bulunamadı.</div>'; return; }
  const grid = `<div class="target-grid">
    <div class="target-cell"><div class="label">En Düşük</div><div class="value">${formatNum(t.low)}</div></div>
    <div class="target-cell"><div class="label">Mevcut</div><div class="value">${formatNum(t.current)}</div></div>
    <div class="target-cell"><div class="label">Medyan</div><div class="value">${formatNum(t.median)}</div></div>
    <div class="target-cell"><div class="label">Ortalama</div><div class="value">${formatNum(t.mean)}</div></div>
    <div class="target-cell"><div class="label">En Yüksek</div><div class="value">${formatNum(t.high)}</div></div>
    <div class="target-cell"><div class="label">Analist</div><div class="value">${t.analyst_count || 0}</div></div>
  </div>`;
  const potCls = t.potential_pct >= 0 ? "pos" : "neg";
  const pot = `<div class="potential-box"><div class="label" style="color:var(--text-dim);font-size:12px;text-transform:uppercase;letter-spacing:.5px;">Potansiyel Getiri</div><div class="potential-big ${potCls}">${formatPct(t.potential_pct)}</div></div>`;
  const rec = t.recommendations || {};
  const recDefs = [["Güçlü Al", rec.strongBuy || 0, COLORS.up], ["Al", rec.buy || 0, COLORS.accent], ["Tut", rec.hold || 0, COLORS.warn], ["Sat", rec.sell || 0, COLORS.gold], ["Güçlü Sat", rec.strongSell || 0, COLORS.down]];
  const maxRec = Math.max(1, ...recDefs.map(r => r[1]));
  const recHtml = `<div class="rec-block"><div class="panel-title" style="margin-top:0;">Analist Tavsiye Dağılımı</div>${recDefs.map(([name, count, color]) => `<div class="rec-row"><div class="rec-label">${name}</div><div class="rec-track"><div class="rec-fill" style="width:${(count/maxRec)*100}%;background:${color}"></div></div><div class="rec-count" style="color:${color}">${count}</div></div>`).join("")}</div>`;
  el.targetBody.innerHTML = grid + pot + recHtml;
}

function renderSimulation(d) {
  el.simResults.innerHTML = "";
  const hist = d.historical || {};
  const mc = d.monte_carlo;
  const histDefs = [["1 Ay", hist["1_ay"]], ["3 Ay", hist["3_ay"]], ["6 Ay", hist["6_ay"]]];
  const summary = document.createElement("div"); summary.className = "sim-summary";
  histDefs.forEach(([label, h]) => {
    const cell = document.createElement("div"); cell.className = "sim-cell";
    if (h) { const cl = h.return_pct >= 0 ? "pos" : "neg"; cell.innerHTML = `<div class="label">${label} Getiri</div><div class="value ${cl}">${formatPct(h.return_pct)}</div><div class="label" style="margin-top:4px;">Sonuç: ${formatMoney(h.value, currentCurrency)}</div>`; }
    else cell.innerHTML = `<div class="label">${label}</div><div class="value">—</div><div class="label">veri yok</div>`;
    summary.appendChild(cell);
  });
  el.simResults.appendChild(summary);

  // Historical bar chart
  const histBox = document.createElement("div"); histBox.className = "hist-box";
  const histCanvas = document.createElement("canvas"); histBox.appendChild(histCanvas); el.simResults.appendChild(histBox);
  const histLabels = histDefs.map(([l]) => l);
  const histVals = histDefs.map(([, h]) => h ? h.return_pct : 0);
  const histCols = histVals.map(v => v >= 0 ? "rgba(37,194,110,0.8)" : "rgba(240,80,110,0.8)");
  new Chart(histCanvas.getContext("2d"), { type: "bar", data: { labels: histLabels, datasets: [{ label: "Geçmiş Getiri (%)", data: histVals, backgroundColor: histCols, borderWidth: 0, borderRadius: 4 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: COLORS.grid } } } } });

  if (!mc) { const n = document.createElement("div"); n.className = "news-empty"; n.textContent = "Monte Carlo verisi yok."; el.simResults.appendChild(n); return; }
  // MC Summary
  const mcSum = document.createElement("div"); mcSum.className = "sim-summary";
  const mcCells = [["Yatırım", formatMoney(mc.investment, currentCurrency)], ["Ortalama", formatMoney(mc.average, currentCurrency)], ["Medyan", formatMoney(mc.median, currentCurrency)], ["En İyi", formatMoney(mc.best, currentCurrency)], ["En Kötü", formatMoney(mc.worst, currentCurrency)], ["Kâr Olasılığı", formatPct(mc.prob_profit)], ["%25 Percentil", formatMoney(mc.percentile_25, currentCurrency)], ["%75 Percentil", formatMoney(mc.percentile_75, currentCurrency)]];
  mcCells.forEach(([l, v]) => { const c = document.createElement("div"); c.className = "sim-cell"; c.innerHTML = `<div class="label">${l}</div><div class="value">${v}</div>`; mcSum.appendChild(c); });
  el.simResults.appendChild(mcSum);
  // MC Chart
  const mcBox = document.createElement("div"); mcBox.className = "mc-box";
  const mcCanvas = document.createElement("canvas"); mcBox.appendChild(mcCanvas); el.simResults.appendChild(mcBox);
  const days = mc.days || 30;
  const mcLabels = Array.from({ length: days + 1 }, (_, i) => i);
  const datasets = [];
  (mc.paths || []).forEach(p => datasets.push({ label: null, data: p, borderColor: "rgba(91,140,255,0.08)", backgroundColor: "transparent", borderWidth: 1, pointRadius: 0, tension: 0.1, spanGaps: true, order: 10 }));
  const constLine = (val, color, label, dash) => ({ label, data: mcLabels.map(() => val), borderColor: color, borderWidth: 2, borderDash: dash || [], pointRadius: 0, fill: false, order: 1 });
  datasets.push(constLine(mc.median, COLORS.warn, "Medyan"));
  datasets.push(constLine(mc.best, COLORS.up, "En İyi"));
  datasets.push(constLine(mc.worst, COLORS.down, "En Kötü"));
  datasets.push(constLine(mc.investment, COLORS.textDim, "Yatırım", [6, 4]));
  new Chart(mcCanvas.getContext("2d"), { type: "line", data: { labels: mcLabels, datasets }, options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: COLORS.textDim, filter: item => item.text !== null } } }, scales: { x: { title: { display: true, text: "Gün", color: COLORS.textDim } }, y: { title: { display: true, text: "Değer (" + currentCurrency + ")", color: COLORS.textDim } } } } });
}

function renderRisk(risk) {
  if (!risk) return;
  const panel = el.panelRisk;
  if (!panel) return;
  panel.innerHTML = `
    <div class="risk-grid">
      <div class="risk-card"><div class="risk-label">VaR (95%)</div><div class="risk-value ${cls(-risk.var95)}">${formatPct(risk.var95)}</div><div class="risk-desc">Günlük maksimum beklenen kayıp</div></div>
      <div class="risk-card"><div class="risk-label">CVaR (95%)</div><div class="risk-value ${cls(-risk.cvar95)}">${formatPct(risk.cvar95)}</div><div class="risk-desc">Kuyruk riski (VaR'ın ötesi)</div></div>
      <div class="risk-card"><div class="risk-label">Sharpe</div><div class="risk-value ${cls(risk.sharpe)}">${formatNum(risk.sharpe, 3)}</div><div class="risk-desc">Risk 조정lu getiri</div></div>
      <div class="risk-card"><div class="risk-label">Sortino</div><div class="risk-value ${cls(risk.sortino)}">${formatNum(risk.sortino, 3)}</div><div class="risk-desc">Aşağı yönlü risk 조정lu</div></div>
      <div class="risk-card"><div class="risk-label">Max Drawdown</div><div class="risk-value neg">${formatPct(risk.max_dd)}</div><div class="risk-desc">En büyük tepeden dip düşüş</div></div>
      <div class="risk-card"><div class="risk-label">Volatilite (Yıllık)</div><div class="risk-value">${formatPct(risk.volatility)}</div><div class="risk-desc">Yıllık standart sapma</div></div>
    </div>
    <div class="correlation-section">
      <h4>Corelasyon Matrisi (Portföy)</h4>
      <canvas id="corrHeatmap" width="400" height="400"></canvas>
    </div>
  `;
  if (risk.correlation && el.panelRisk.querySelector("#corrHeatmap")) {
    drawCorrelationHeatmap(risk.correlation, el.panelRisk.querySelector("#corrHeatmap"));
  }
}

function drawCorrelationHeatmap(corr, canvas) {
  const ctx = canvas.getContext("2d");
  const size = Math.min(canvas.width, canvas.height);
  const n = corr.length;
  const cell = size / n;
  corr.forEach((row, i) => {
    row.forEach((val, j) => {
      const intensity = Math.abs(val);
      const hue = val >= 0 ? 120 : 0; // green for positive, red for negative
      ctx.fillStyle = `hsla(${hue}, 70%, 40%, ${intensity * 0.8 + 0.2})`;
      ctx.fillRect(j * cell, i * cell, cell, cell);
      ctx.fillStyle = intensity > 0.5 ? "#fff" : "#000";
      ctx.font = "10px Inter";
      ctx.textAlign = "center";
      ctx.fillText(val.toFixed(2), j * cell + cell/2, i * cell + cell/2 + 3);
    });
  });
  // Labels
  ctx.fillStyle = COLORS.textDim;
  ctx.font = "11px Inter";
  corr.forEach((_, i) => {
    ctx.fillText(`S${i+1}`, size + 5, i * cell + cell/2 + 4);
    ctx.fillText(`S${i+1}`, i * cell + cell/2 - 10, size + 20);
  });
}

function renderAI(text, signal) {
  const sg = signal || {};
  const verdictHtml = `<div class="verdict" style="--vc:${sg.color || COLORS.accent}">
    <div class="verdict-badge"><span class="verdict-emoji">${sg.emoji || "🤖"}</span></div>
    <div class="verdict-body">
      <div class="verdict-label">YAPAY ZEKA GÖRÜŞÜ</div>
      <div class="verdict-text">${sg.text || "BEKLE"}</div>
      <div class="verdict-score">
        <div class="verdict-track"><div class="verdict-fill" style="width:${sg.score || 0}%;background:${sg.color || COLORS.accent}"></div></div>
        <span>${sg.score || 0}/100</span>
      </div>
    </div></div>`;
  el.aiVerdict.innerHTML = verdictHtml;
  el.aiAdvice.innerHTML = renderMarkdown(text);
}

function renderMarkdown(text) {
  const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  const lines = (text || "").split("\n");
  let html = "", inList = false;
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  for (const raw of lines) {
    const line = esc(raw);
    if (!line.trim()) { closeList(); continue; }
    const h = line.match(/^#{2,3}\s+(.*)$/);
    if (h) { closeList(); html += `<h3 class="ai-h3">${h[1]}</h3>`; continue; }
    const b = line.match(/^[\*\-]\s+(.*)$/);
    if (b) { if (!inList) { html += '<ul class="ai-ul">'; inList = true; } html += `<li>${formatInline(b[1])}</li>`; continue; }
    closeList();
    html += `<p class="ai-p">${formatInline(line)}</p>`;
  }
  closeList();
  return html || '<p class="ai-p">AI yorumu bulunamadı.</p>';
}
function formatInline(s) { return s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>"); }

/* ------------------------------------------------------------
   CHARTS
   ------------------------------------------------------------ */
async function renderCharts(chartData) {
  if (!chartData) return;
  const labels = chartData.dates || [];
  const n = labels.length;
  const ref70 = Array(n).fill(70), ref30 = Array(n).fill(30);

  charts.forEach(c => c.destroy()); charts = [];

  const commonOpts = { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: COLORS.textDim } }, tooltip: { backgroundColor: "#1b2130", titleColor: COLORS.text, bodyColor: COLORS.textDim, borderColor: COLORS.border, borderWidth: 1, padding: 10, cornerRadius: 8, displayColors: true, titleFont: { family: "Inter", weight: "700", size: 12 }, bodyFont: { family: "JetBrains Mono", size: 11 } } }, scales: { x: { grid: { display: false }, ticks: { color: COLORS.textDim, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } }, y: { grid: { color: "rgba(35,43,59,0.5)" }, ticks: { color: COLORS.textDim }, border: { display: false } } } };

  // Price
  const priceCtx = el.chartPrice.getContext("2d");
  const priceGrad = priceCtx.createLinearGradient(0, 0, 0, el.chartPrice.height);
  priceGrad.addColorStop(0, "rgba(91,140,255,0.25)");
  priceGrad.addColorStop(1, "rgba(91,140,255,0)");
  const priceDatasets = [
    { label: "Kapanış", data: chartData.close || [], borderColor: COLORS.accent, backgroundColor: ctx => priceGrad, borderWidth: 2, pointRadius: 0, tension: 0.15, spanGaps: true, fill: "origin", order: 1 },
    { label: "SMA20", data: chartData.sma20 || [], borderColor: COLORS.gold, backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, tension: 0.15, spanGaps: true, hidden: !el.indSMA20.checked, order: 2 },
    { label: "SMA50", data: chartData.sma50 || [], borderColor: COLORS.down, backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, tension: 0.15, spanGaps: true, hidden: !el.indSMA50.checked, order: 3 },
    { label: "BB Üst", data: chartData.bb_upper || [], borderColor: "rgba(157,140,255,0.6)", backgroundColor: "rgba(157,140,255,0.1)", borderWidth: 1, pointRadius: 0, tension: 0.15, spanGaps: true, fill: "+1", hidden: !el.indBB.checked, order: 4 },
    { label: "BB Alt", data: chartData.bb_lower || [], borderColor: "rgba(157,140,255,0.6)", backgroundColor: "transparent", borderWidth: 1, pointRadius: 0, tension: 0.15, spanGaps: true, fill: false, hidden: !el.indBB.checked, order: 5 },
  ];
  const c1 = new Chart(priceCtx, { type: "line", data: { labels, datasets: priceDatasets }, options: { ...commonOpts, plugins: { ...commonOpts.plugins, tooltip: { ...commonOpts.plugins.tooltip, callbacks: { label: ctx => `${ctx.dataset.label}: ${formatMoney(ctx.parsed.y)}` } } } } });
  charts.push(c1);

  // Crosshair
  const crosshairPlugin = { id: "crosshair", afterDraw: chart => { if (!chart.tooltip._active?.length) return; const ctx = chart.ctx, active = chart.tooltip._active[0]; const x = active.element.x; ctx.save(); ctx.beginPath(); ctx.moveTo(x, chart.chartArea.top); ctx.lineTo(x, chart.chartArea.bottom); ctx.strokeStyle = "rgba(91,140,255,0.5)"; ctx.lineWidth = 1; ctx.setLineDash([4, 4]); ctx.stroke(); ctx.restore(); } };
  Chart.register(crosshairPlugin);

  // RSI
  const rsiCtx = el.chartRSI.getContext("2d");
  const c2 = new Chart(rsiCtx, { type: "line", data: { labels, datasets: [ { label: "RSI", data: chartData.rsi || [], borderColor: COLORS.purple, backgroundColor: "transparent", borderWidth: 2, pointRadius: 0, tension: 0.15, spanGaps: true }, { label: "70 (Aşırı Alım)", data: ref70, borderColor: COLORS.down, borderDash: [6, 4], borderWidth: 1, pointRadius: 0, fill: false }, { label: "30 (Aşırı Satım)", data: ref30, borderColor: COLORS.up, borderDash: [6, 4], borderWidth: 1, pointRadius: 0, fill: false } ] }, options: { ...commonOpts, scales: { ...commonOpts.scales, y: { ...commonOpts.scales.y, min: 0, max: 100 } } } });
  charts.push(c2);

  // MACD
  const macdCtx = el.chartMACD.getContext("2d");
  const histColors = (chartData.macd_hist || []).map(v => v >= 0 ? "rgba(37,194,110,0.7)" : "rgba(240,80,110,0.7)");
  const c3 = new Chart(macdCtx, { type: "bar", data: { labels, datasets: [ { label: "MACD Hist", data: chartData.macd_hist || [], backgroundColor: histColors, borderWidth: 0, borderRadius: 2, order: 3 }, { label: "MACD", data: chartData.macd || [], type: "line", borderColor: COLORS.accent, borderWidth: 2, pointRadius: 0, tension: 0.15, spanGaps: true, order: 1 }, { label: "Sinyal", data: chartData.macd_signal || [], type: "line", borderColor: COLORS.gold, borderWidth: 2, pointRadius: 0, tension: 0.15, spanGaps: true, order: 2 } ] }, options: commonOpts });
  charts.push(c3);

  // Volume
  const volCtx = el.chartVolume.getContext("2d");
  const volColors = (chartData.close || []).map((_, i) => (chartData.close[i] >= (chartData.open?.[i] || chartData.close[i])) ? "rgba(37,194,110,0.8)" : "rgba(240,80,110,0.8)");
  const c4 = new Chart(volCtx, { type: "bar", data: { labels, datasets: [{ label: "Hacim", data: chartData.volume || [], backgroundColor: volColors, borderWidth: 0, borderRadius: 2 }] }, options: { ...commonOpts, plugins: { ...commonOpts.plugins, legend: { display: false } }, scales: { ...commonOpts.scales, y: { ...commonOpts.scales.y, beginAtZero: true } } } });
  charts.push(c4);

  // Toggle visibility
  [el.indSMA20, el.indSMA50, el.indBB, el.indVolume].forEach((cb, idx) => { if (charts[idx]) cb.onchange = () => { charts[idx].data.datasets.forEach((ds, i) => { if (idx === 0 && i === 1) ds.hidden = !cb.checked; if (idx === 1 && i === 2) ds.hidden = !cb.checked; if (idx === 2 && (i === 3 || i === 4)) ds.hidden = !cb.checked; if (idx === 3 && i === 4) ds.hidden = !cb.checked; }); charts[idx].update(); }; });
}
function redrawCharts() { if (currentData?.chart) renderCharts(currentData.chart); }

/* ------------------------------------------------------------
   SPLIT VIEW
   ------------------------------------------------------------ */
el.splitViewBtn.onclick = () => {
  if (!splitMode) {
    const sym = prompt("Karşılaştırılacak hisse:", "");
    if (!sym) return;
    splitMode = true; splitTicker = sym.trim().toUpperCase();
    el.splitViewBtn.classList.add("active");
    toast(`${splitTicker} eklendi (bölünmüş)`, "info");
    // TODO: render second chart column
  } else {
    splitMode = false; splitTicker = null;
    el.splitViewBtn.classList.remove("active");
    toast("Bölünmüş görünüm kapatıldı", "info");
  }
};

/* ------------------------------------------------------------
   TABLE SORT / FILTER / EXPORT
   ------------------------------------------------------------ */
let sortCol = null, sortDir = 1;
function makeSortable(table) {
  $$("th", table).forEach((th, i) => { th.style.cursor = "pointer"; th.onclick = () => { sortDir = (sortCol === i) ? -sortDir : 1; sortCol = i; sortTable(table, i, sortDir); }; });
}
function sortTable(table, col, dir) {
  const tbody = table.tBodies[0];
  const rows = [...tbody.rows];
  rows.sort((a, b) => {
    const av = a.cells[col].textContent.trim();
    const bv = b.cells[col].textContent.trim();
    const an = parseFloat(av.replace(/[^\d.-]/g, ""));
    const bn = parseFloat(bv.replace(/[^\d.-]/g, ""));
    return (isNaN(an) || isNaN(bn) ? av.localeCompare(bv, "tr") : an - bn) * dir;
  });
  rows.forEach(r => tbody.appendChild(r));
  $$("th", table).forEach((th, i) => { th.classList.toggle("sorted", i === col); th.classList.toggle("asc", i === col && dir === 1); th.classList.toggle("desc", i === col && dir === -1); });
}
$$(".data-table, .portfolio-table").forEach(makeSortable);
function exportTableCSV(table, name) { const rows = [...table.rows].map(r => [...r.cells].map(c => `"${c.textContent.replace(/"/g, '""')}"`).join(",")); downloadCSV(rows.join("\n"), name); }
$$(".data-table, .portfolio-table").forEach(t => { const btn = document.createElement("button"); btn.className = "btn-ghost"; btn.textContent = "CSV"; btn.style.marginLeft = "auto"; btn.onclick = () => exportTableCSV(t, `${t.id || "tablo"}.csv`); t.parentElement.style.position = "relative"; t.parentElement.appendChild(btn); });

/* ------------------------------------------------------------
   KEYBOARD SHORTCUTS
   ------------------------------------------------------------ */
const shortcuts = {
  "ctrl+k": () => el.cmdPalette.showModal(),
  "ctrl+b": () => el.sidebar.classList.toggle("open"),
  "ctrl+t": () => el.themeToggle.click(),
  "ctrl+shift+s": () => el.splitViewBtn.click(),
  "ctrl+shift+e": () => exportPortfolio(),
  "ctrl+r": e => { e.preventDefault(); refreshCurrent(); },
  "f": () => el.fullscreenChart.click(),
  "alt+arrowleft": () => goBackTab(),
  "alt+arrowright": () => goForwardTab(),
  "1": () => switchTab("teknik"),
  "2": () => switchTab("sirket"),
  "3": () => switchTab("haberler"),
  "4": () => switchTab("hedef"),
  "5": () => switchTab("simulasyon"),
  "6": () => switchTab("ai"),
  "7": () => switchTab("portfolio"),
  "?": () => el.helpModal.showModal(),
  "escape": () => { if (el.cmdPalette.open) el.cmdPalette.close(); if (el.helpModal.open) el.helpModal.close(); if (el.addWatchlistModal.open) el.addWatchlistModal.close(); if (el.addPortfolioModal.open) el.addPortfolioModal.close(); if (el.addAlertModal.open) el.addAlertModal.close(); if (!el.tourOverlay.classList.contains("hidden")) { el.tourOverlay.classList.add("hidden"); tourActive = false; } },
};
document.addEventListener("keydown", e => {
  const key = (e.ctrlKey ? "ctrl+" : "") + (e.shiftKey ? "shift+" : "") + (e.altKey ? "alt+" : "") + e.key.toLowerCase();
  if (shortcuts[key]) { e.preventDefault(); shortcuts[key](e); }
  if (e.key === "Tab" && e.ctrlKey) { e.preventDefault(); const tabs = $$("#mainTabs [role=tab]"); const idx = tabs.findIndex(t => t.classList.contains("active")); tabs[(idx + (e.shiftKey ? -1 : 1) + tabs.length) % tabs.length].click(); }
});
["tickerInput", "amountInput", "wlTicker", "portTicker", "portQty", "portBuyPrice", "portBuyDate", "alertTicker", "alertValue", "cmdInput"].forEach(id => { const el_ = document.getElementById(id); if (el_) el_.addEventListener("keydown", e => e.stopPropagation()); });

/* ------------------------------------------------------------
   COMMAND PALETTE
   ------------------------------------------------------------ */
const commands = [
  { id: "analyze", name: "Hisse Analiz Et", desc: "Yeni hisse kodu girip analiz başlat", keys: "Ctrl+K", action: () => { el.cmdPalette.close(); el.tickerInput.focus(); } },
  { id: "refresh", name: "Yenile", desc: "Mevcut hisseyi yeniden analiz et", keys: "Ctrl+R", action: refreshCurrent },
  { id: "watchlist", name: "Watchlist Aç/Kapat", desc: "Yan panel watchlist sekmesi", keys: "Ctrl+B", action: () => switchSidebarPanel("watchlist") },
  { id: "portfolio", name: "Portföy", desc: "Portföy sekmesini aç", keys: "", action: () => { switchSidebarPanel("portfolio"); switchTab("portfolio"); } },
  { id: "theme", name: "Tema Değiştir", desc: "Koyu/Açık/Sistem", keys: "Ctrl+T", action: () => el.themeToggle.click() },
  { id: "split", name: "Bölünmüş Görünüm", desc: "İki hisse yan yana", keys: "Ctrl+Shift+S", action: () => el.splitViewBtn.click() },
  { id: "export", name: "Portföy CSV", desc: "Portföyü CSV olarak indir", keys: "Ctrl+Shift+E", action: exportPortfolio },
  { id: "fullscreen", name: "Grafik Tam Ekran", desc: "Fiyat grafiğini büyüt", keys: "F", action: () => el.fullscreenChart.click() },
  { id: "exportChart", name: "Grafik Kaydet (PNG)", desc: "Mevcut grafiği indir", keys: "", action: () => el.exportChart.click() },
  { id: "autoRefresh5", name: "Oto Yenile 5dk", desc: "Her 5 dakikada bir yenile", keys: "", action: () => { el.autoRefreshSelect.value = "300000"; startAutoRefresh(300000); saveSettings(); toast("5 dk", "info"); } },
  { id: "autoRefreshOff", name: "Oto Yenile Kapalı", desc: "Otomatik yenilemeyi kapat", keys: "", action: () => { el.autoRefreshSelect.value = "0"; startAutoRefresh(0); saveSettings(); toast("Kapalı", "info"); } },
  { id: "clearData", name: "Tüm Verileri Temizle", desc: "Yerel depolama tamamen silinir", keys: "", action: () => el.clearAllData.click() },
  { id: "help", name: "Yardım / Kısayollar", desc: "Klavye kısayolları listesini aç", keys: "?", action: () => el.helpModal.showModal() },
  { id: "tour", name: "Tur Yeniden Başlat", desc: "Onboarding turunu tekrar göster", keys: "", action: () => startTour() },
];
function filterCommands(q) { return commands.filter(c => c.name.toLowerCase().includes(q.toLowerCase()) || c.desc.toLowerCase().includes(q.toLowerCase()) || c.id.toLowerCase().includes(q.toLowerCase())); }
function renderCommands(list) { el.cmdResults.innerHTML = list.map(c => `<div class="cmd-item" role="option" data-id="${c.id}"><kbd class="cmd-keys">${c.keys || ""}</kbd><span class="cmd-name">${c.name}</span><span class="cmd-desc">${c.desc}</span></div>`).join(""); $$(".cmd-item", el.cmdResults).forEach(item => { item.onclick = () => { const cmd = commands.find(c => c.id === item.dataset.id); if (cmd) { cmd.action(); el.cmdPalette.close(); } }; }); }
el.cmdPalette.addEventListener("show", () => { renderCommands(commands); el.cmdInput.value = ""; el.cmdInput.focus(); });
el.cmdInput.addEventListener("input", e => renderCommands(filterCommands(e.target.value)));
el.cmdInput.addEventListener("keydown", e => {
  const items = $$(".cmd-item", el.cmdResults);
  const idx = items.findIndex(i => i.classList.contains("selected"));
  if (e.key === "ArrowDown") { e.preventDefault(); items[(idx + 1) % items.length].classList.add("selected"); if (idx >= 0) items[idx].classList.remove("selected"); }
  else if (e.key === "ArrowUp") { e.preventDefault(); items[(idx - 1 + items.length) % items.length].classList.add("selected"); if (idx >= 0) items[idx].classList.remove("selected"); }
  else if (e.key === "Enter") { items[idx]?.click(); }
});
el.cmdPalette.querySelector("footer").onclick = () => el.cmdPalette.close();

/* ------------------------------------------------------------
   HELP MODAL
   ------------------------------------------------------------ */
const helpData = [
  { cat: "Genel", items: [{ k: "Ctrl+K", d: "Komut paleti" }, { k: "Ctrl+B", d: "Yan panel aç/kapat" }, { k: "Ctrl+T", d: "Tema değiştir" }, { k: "?", d: "Yardım modalı" }, { k: "Esc", d: "Modal kapat / Tur atla" }] },
  { cat: "Navigasyon", items: [{ k: "1–7", d: "Sekme atla (Teknik, Şirket, Haberler, Hedef, Simülasyon, AI, Portföy)" }, { k: "Ctrl+Tab", d: "Sonraki sekme" }, { k: "Ctrl+Shift+Tab", d: "Önceki sekme" }, { k: "Alt+←", d: "Sekme gezinme: geri" }, { k: "Alt+→", d: "Sekme gezinme: ileri" }] },
  { cat: "Analiz", items: [{ k: "Ctrl+R", d: "Yeniden analiz et" }, { k: "F", d: "Grafik tam ekran" }, { k: "Ctrl+Shift+S", d: "Bölünmüş görünüm" }, { k: "Ctrl+Shift+E", d: "Portföy CSV dışa aktar" }] },
  { cat: "Grafik", items: [{ k: "1G/1H/1A/3A/6A/YTD/1Y/MAX", d: "Zaman aralığı (toolbar butonları)" }, { k: "Click toolbar", d: "Chart tipi / İndikatör toggle" }] },
  { cat: "Yan Panel", items: [{ k: "Click Watchlist", d: "Hisse analiz et" }, { k: "Portföy tab", d: "Pozisyon ekle/sil/CSV" }, { k: "Ayarlar tab", d: "Tema, yenileme, erişilebilirlik" }] },
];
function renderHelp() { el.helpCategories.innerHTML = helpData.map(c => `<div class="help-category"><h4>${c.cat}</h4>${c.items.map(i => `<div class="help-item"><kbd>${i.k}</kbd><span>${i.d}</span></div>`).join("")}</div>`).join(""); }
el.helpModal.addEventListener("show", renderHelp);

/* ------------------------------------------------------------
   ONBOARDING TOUR
   ------------------------------------------------------------ */
const tourSteps = [
  { el: ".search-bar", title: "Hisse Arama", desc: "Buraya hisse kodu yazın (THYAO, AAPL, TSLA...). Enter veya ⚡ Analiz Et ile başlayın.", pos: "bottom" },
  { el: ".signal-card", title: "Sinyal Kartı", desc: "AI + teknik skor, yön (AL/SAT/BEKLE), güven skoru ve fiyat değişimi tek bakışta.", pos: "bottom" },
  { el: ".tabs", title: "Sekme Geçişi", desc: "Teknik, Şirket, Haberler, Hedef, Simülasyon, AI Yorum, Portföy. 1-7 tuşlarıyla da atlayabilirsiniz.", pos: "bottom" },
  { el: ".chart-toolbar", title: "Grafik Kontrolleri", desc: "Zaman aralığı (1G–MAX), chart tipi (Mum/Çizgi/Heikin-Ashi), indikatör aç/kapa, tam ekran, PNG kaydet.", pos: "top" },
  { el: ".sidebar", title: "Yan Panel", desc: "Watchlist, Portföy, Alarmlar, Ayarlar. Ctrl+B ile gizle/göster.", pos: "right" },
  { el: "#panel-risk", title: "Risk Metrikleri", desc: "VaR, CVaR, Sharpe, Sortino, Max Drawdown, Corelasyon matrisi — profesyonel risk analizi.", pos: "left" },
  { el: "#panel-heatmap", title: "Isı Haritası", desc: "BIST100/Sektör anlık performans, hangi hisseler yeşil/kırmızı.", pos: "left" },
  { el: "#panel-backtest", title: "Backtest", desc: "Strateji yaz, geçmişte test et, performans metrikleri al.", pos: "left" },
  { el: "#panel-ai-portfolio", title: "AI Portföy Önerisi", desc: "Bütçe + risk profili → optimal 5-10 hisse dağılımı.", pos: "left" },
];
function startTour() { tourStep = 0; tourActive = true; el.tourOverlay.classList.remove("hidden"); showTourStep(); }
function showTourStep() { const s = tourSteps[tourStep]; const target = $(s.el); if (!target) return nextTour(); const rect = target.getBoundingClientRect(); el.tourTitle.textContent = s.title; el.tourDesc.textContent = s.desc; el.tourProgress.textContent = `${tourStep + 1} / ${tourSteps.length}`; el.tourStep.style.position = "fixed"; el.tourStep.style.left = `${Math.min(rect.right + 16, window.innerWidth - 440)}px`; el.tourStep.style.top = `${Math.max(rect.top - 20, 16)}px`; }
function nextTour() { tourStep++; if (tourStep >= tourSteps.length) endTour(); else showTourStep(); }
function endTour() { tourActive = false; el.tourOverlay.classList.add("hidden"); localStorage.setItem("bl_tour_done", "true"); }
el.tourNext.onclick = nextTour; el.tourSkip.onclick = endTour;
if (!localStorage.getItem("bl_tour_done")) { setTimeout(startTour, 800); }

/* ------------------------------------------------------------
   NEW PANELS: HEATMAP, BACKTEST, AI PORTFOLIO
   ------------------------------------------------------------ */
async function loadHeatmap() {
  const panel = el.panelHeatmap;
  const mainPanel = el.panelHeatmapMain;
  if (!panel) return;
  panel.innerHTML = '<div class="loading">Isı haritası yükleniyor...</div>';
  try {
    const res = await fetch(API.heatmap());
    const data = await res.json();
    renderHeatmap(data, panel);
    if (mainPanel) mainPanel.innerHTML = panel.innerHTML;
  } catch (e) { panel.innerHTML = '<div class="error">Isı haritası yüklenemedi</div>'; }
}

function renderHeatmap(data, container) {
  if (!data || !data.length) { container.innerHTML = '<div class="news-empty">Veri yok</div>'; return; }
  const bySector = {};
  data.forEach(d => { bySector[d.sector] = bySector[d.sector] || []; bySector[d.sector].push(d); });
  container.innerHTML = Object.entries(bySector).map(([sector, stocks]) => `
    <div class="heatmap-sector">
      <h4>${escapeHtml(sector)}</h4>
      <div class="heatmap-grid">
        ${stocks.map(s => `
          <div class="heatmap-cell ${s.change_pct >= 0 ? "up" : "down"}" title="${escapeHtml(s.name)}: ${formatPct(s.change_pct)}">
            <span class="cell-symbol">${escapeHtml(s.symbol)}</span>
            <span class="cell-pct">${formatPct(s.change_pct)}</span>
          </div>
        `).join("")}
      </div>
    </div>
  `).join("");
  // Click to analyze
  $$(".heatmap-cell", container).forEach(cell => {
    cell.onclick = () => { const sym = cell.querySelector(".cell-symbol").textContent; analyze(sym); switchTab("teknik"); };
  });
}

async function loadBacktestPanel() {
  const panel = el.panelBacktest;
  const mainPanel = el.panelBacktestMain;
  if (!panel) return;
  panel.innerHTML = `
    <div class="backtest-controls">
      <div class="form-row">
        <div class="form-group"><label>Strateji</label><select id="btStrategy"><option value="sma_cross">SMA Cross (20/50)</option><option value="rsi_mean_rev">RSI Mean Reversion (<30/>70)</option><option value="macd_cross">MACD Cross</option><option value="bb_squeeze">Bollinger Squeeze</option><option value="custom">Özel (DSL)</option></select></div>
        <div class="form-group"><label>Başlangıç</label><input type="date" id="btFrom" value="${new Date(Date.now() - 365*24*60*60*1000).toISOString().split("T")[0]}" /></div>
        <div class="form-group"><label>Bitiş</label><input type="date" id="btTo" value="${new Date().toISOString().split("T")[0]}" /></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Başlangıç Sermayesi</label><input type="number" id="btCapital" value="100000" min="1000" step="1000" /></div>
        <div class="form-group"><label>Komisyon %</label><input type="number" id="btCommission" value="0.2" min="0" max="2" step="0.01" /></div>
        <div class="form-group"><label>Slippage %</label><input type="number" id="btSlippage" value="0.1" min="0" max="1" step="0.01" /></div>
      </div>
      <button class="btn-primary" id="btRun">Backtest Çalıştır</button>
      <button class="btn-ghost" id="btSave">Sonuç Kaydet</button>
    </div>
    <div id="btResults"></div>
  `;
  if (mainPanel) mainPanel.innerHTML = panel.innerHTML;
  document.getElementById("btRun").onclick = runBacktest;
  document.getElementById("btSave").onclick = saveBacktest;
}

async function runBacktest() {
  if (!currentTicker) return toast("Önce bir hisse analiz edin", "warning");
  const strategy = document.getElementById("btStrategy").value;
  const from = document.getElementById("btFrom").value;
  const to = document.getElementById("btTo").value;
  const capital = +document.getElementById("btCapital").value;
  const commission = +document.getElementById("btCommission").value / 100;
  const slippage = +document.getElementById("btSlippage").value / 100;

  const resDiv = document.getElementById("btResults");
  resDiv.innerHTML = '<div class="loading">Backtest çalışıyor...</div>';

  try {
    const res = await fetch(API.backtest(currentTicker, strategy, from, to));
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    renderBacktestResults(data, resDiv, capital, commission, slippage);
    // Sync to main panel
    const sidebarPanel = el.panelBacktest;
    const mainPanel = el.panelBacktestMain;
    if (sidebarPanel && mainPanel) mainPanel.innerHTML = sidebarPanel.innerHTML;
  } catch (e) { resDiv.innerHTML = `<div class="error">${e.message}</div>`; }
}

function renderBacktestResults(data, container, capital, commission, slippage) {
  const { trades, equity, metrics } = data;
  const totalReturn = ((equity[equity.length - 1] - capital) / capital) * 100;
  const winRate = trades.length ? (trades.filter(t => t.pnl > 0).length / trades.length) * 100 : 0;
  const avgWin = trades.filter(t => t.pnl > 0).reduce((s, t) => s + t.pnl, 0) / Math.max(1, trades.filter(t => t.pnl > 0).length);
  const avgLoss = trades.filter(t => t.pnl < 0).reduce((s, t) => s + t.pnl, 0) / Math.max(1, trades.filter(t => t.pnl < 0).length);
  const profitFactor = avgLoss ? Math.abs(avgWin / avgLoss) : Infinity;

  container.innerHTML = `
    <div class="bt-summary">
      <div class="bt-metric"><span>Toplam Getiri</span><strong class="${cls(totalReturn)}">${formatPct(totalReturn)}</strong></div>
      <div class="bt-metric"><span>İşlem Sayısı</span><strong>${trades.length}</strong></div>
      <div class="bt-metric"><span>Win Rate</span><strong class="${cls(winRate - 50)}">${formatPct(winRate)}</strong></div>
      <div class="bt-metric"><span>Profit Factor</span><strong>${profitFactor === Infinity ? "∞" : profitFactor.toFixed(2)}</strong></div>
      <div class="bt-metric"><span>Max DD</span><strong class="neg">${formatPct(metrics.max_drawdown)}</strong></div>
      <div class="bt-metric"><span>Sharpe</span><strong class="${cls(metrics.sharpe)}">${metrics.sharpe.toFixed(2)}</strong></div>
    </div>
    <div class="bt-equity-chart"><canvas id="btEquityCanvas"></canvas></div>
    <div class="bt-trades-table">
      <table class="data-table"><thead><tr><th>Tarih</th><th>Tür</th><th>Fiyat</th><th>Adet</th><th>P&L</th><th>P&L%</th></tr></thead><tbody>
        ${trades.slice(-50).map(t => `<tr><td>${t.date}</td><td class="${t.type === "BUY" ? "pos" : "neg"}">${t.type}</td><td>${t.price.toFixed(2)}</td><td>${t.qty}</td><td class="${cls(t.pnl)}">${formatMoney(t.pnl)}</td><td class="${cls(t.pnl_pct)}">${formatPct(t.pnl_pct)}</td></tr>`).join("")}
      </tbody></table>
    </div>
  `;
  // Equity curve
  const ctx = document.getElementById("btEquityCanvas").getContext("2d");
  new Chart(ctx, { type: "line", data: { labels: equity.map((_, i) => i), datasets: [{ label: "Equity", data: equity, borderColor: COLORS.accent, backgroundColor: "rgba(91,140,255,0.1)", borderWidth: 2, pointRadius: 0, tension: 0.1, fill: true }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: COLORS.grid } } } } });
}

async function saveBacktest() {
  if (!currentTicker) return toast("Önce backtest çalıştırın", "warning");
  const strategy = document.getElementById("btStrategy").value;
  const from = document.getElementById("btFrom").value;
  const to = document.getElementById("btTo").value;
  const res = await fetch(API.backtest(currentTicker, strategy, from, to));
  const data = await res.json();
  if (data.success) { await IDB.saveBacktest({ ticker: currentTicker, strategy, from, to, ...data }); toast("Backtest kaydedildi", "success"); } else toast("Kaydetme başarısız", "error");
}

async function loadAIPortfolio() {
  const panel = el.panelAIPortfolio;
  const mainPanel = el.panelAIPortfolioMain;
  if (!panel) return;
  panel.innerHTML = `
    <div class="ai-portfolio-controls">
      <div class="form-row">
        <div class="form-group"><label>Bütçe (TL)</label><input type="number" id="aiBudget" value="100000" min="1000" step="1000" /></div>
        <div class="form-group"><label>Risk Profili</label><select id="aiRisk"><option value="conservative">Muhafazakar</option><option value="balanced" selected>Dengeli</option><option value="aggressive">Agresif</option></select></div>
        <div class="form-group"><label>Hisse Sayısı</label><input type="number" id="aiCount" value="8" min="3" max="15" /></div>
      </div>
      <button class="btn-primary" id="aiSuggest">Portföy Öner</button>
    </div>
    <div id="aiPortfolioResults"></div>
  `;
  document.getElementById("aiSuggest").onclick = suggestAIPortfolio;
  if (mainPanel) mainPanel.innerHTML = panel.innerHTML;
}

async function suggestAIPortfolio() {
  const budget = +document.getElementById("aiBudget").value;
  const risk = document.getElementById("aiRisk").value;
  const count = +document.getElementById("aiCount").value;
  const resDiv = document.getElementById("aiPortfolioResults");
  resDiv.innerHTML = '<div class="loading">AI portföy oluşturuluyor...</div>';
  try {
    const res = await fetch(API.portfolio_suggest(budget, risk, count));
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    renderAIPortfolio(data, resDiv, budget);
    // Sync to main panel
    const sidebarPanel = el.panelAIPortfolio;
    const mainPanel = el.panelAIPortfolioMain;
    if (sidebarPanel && mainPanel) mainPanel.innerHTML = sidebarPanel.innerHTML;
  } catch (e) { resDiv.innerHTML = `<div class="error">${e.message}</div>`; }
}

async function loadRiskPanel() {
  const panel = el.panelRisk;
  const mainPanel = el.panelRiskMain;
  if (!panel) return;
  if (!currentTicker) { panel.innerHTML = '<div class="news-empty">Önce bir hisse analiz edin</div>'; return; }
  panel.innerHTML = '<div class="loading">Risk metrikleri yükleniyor...</div>';
  try {
    const res = await fetch(API.risk(currentTicker));
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    renderRisk({ ...data, ticker: currentTicker });
    if (mainPanel) mainPanel.innerHTML = panel.innerHTML;
  } catch (e) { panel.innerHTML = `<div class="error">${e.message}</div>`; }
}

function renderAIPortfolio(data, container, budget) {
  const { allocations, reasoning, expected_return, expected_vol, sharpe } = data;
  container.innerHTML = `
    <div class="ai-portfolio-summary">
      <div class="metric"><span>Beklenti Getiri</span><strong class="${cls(expected_return)}">${formatPct(expected_return)}</strong></div>
      <div class="metric"><span>Beklenti Volatilite</span><strong>${formatPct(expected_vol)}</strong></div>
      <div class="metric"><span>Sharpe</span><strong class="${cls(sharpe)}">${sharpe.toFixed(2)}</strong></div>
    </div>
    <div class="ai-alloc-table">
      <table class="data-table"><thead><tr><th>Sembol</th><th>Ağırlık %</th><th>Tutar</th><th>Sektör</th><th>Neden</th></tr></thead><tbody>
        ${allocations.map(a => `<tr><td><strong>${a.symbol}</strong></td><td>${a.weight.toFixed(1)}%</td><td>${formatMoney(a.amount)}</td><td>${a.sector}</td><td>${a.reason}</td></tr>`).join("")}
      </tbody></table>
    </div>
    <div class="ai-reasoning"><h4>AI Gerekçesi</h4><p>${reasoning}</p></div>
    <button class="btn-primary" data-allocs="${encodeURIComponent(JSON.stringify(allocations))}" onclick="applyAIPortfolio(this)">Bu Portföyü Uygula</button>
  `;
}
window.applyAIPortfolio = async (btn) => { const allocs = JSON.parse(decodeURIComponent(btn.getAttribute("data-allocs")));
  for (const a of allocs) {
    await addPortfolio({ symbol: a.symbol, qty: Math.floor(a.amount / a.price), buyPrice: a.price, buyDate: new Date().toISOString().split("T")[0], sector: a.sector });
  }
  toast("Portföy uygulandı", "success");
  switchSidebarPanel("portfolio");
  switchTab("portfolio");
};

/* ------------------------------------------------------------
   INIT
   ------------------------------------------------------------ */
async function init() {
  // Unregister SW & Clear Cache
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.getRegistrations().then(registrations => {
      for (let r of registrations) {
        r.unregister().then(() => {
          console.log("[SW] Unregistered");
          if (window.caches) {
            caches.keys().then(keys => {
              keys.forEach(k => caches.delete(k));
            }).then(() => {
              window.location.reload();
            });
          }
        });
      }
    });
  }

  // Request notification permission
  if (Notification.permission === "default") Notification.requestPermission();

  // Load persisted data
  watchlist = await IDB.getWatchlist();
  portfolio = await IDB.getPortfolio();
  alerts = await IDB.getAlerts();
  settings = await IDB.getSettings();
  await loadSettings();
  await renderWatchlist();
  await renderPortfolio();
  await renderAlerts();
  setTheme(getTheme());
  updateThemeIcons(getTheme());

  // Event listeners
  el.analyzeBtn.onclick = () => analyze(el.tickerInput.value);
  el.tickerInput.addEventListener("keydown", e => { if (e.key === "Enter") analyze(el.tickerInput.value); });
  el.tickerInput.addEventListener("input", e => { const hasDot = e.target.value.includes("."); el.tickerSuffix.style.display = hasDot ? "none" : "inline"; });

  // Tab navigation back/forward buttons
  el.tabBackBtn.onclick = () => goBackTab();
  el.tabForwardBtn.onclick = () => goForwardTab();

  // Simulate
  el.simulateBtn.onclick = () => { const amt = +el.amountInput.value; if (!amt || amt <= 0) return toast("Geçerli tutar gir", "warning"); if (currentData) renderSimulation(currentData); else toast("Önce analiz et", "warning"); };
  el.amountInput.addEventListener("keydown", e => { if (e.key === "Enter") el.simulateBtn.click(); });

  // Offline retry
  el.retryOnline.onclick = () => window.location.reload();

  // Responsive sidebar toggle
  if (window.innerWidth <= 768) { const overlay = document.createElement("div"); overlay.className = "sidebar-overlay"; document.body.appendChild(overlay); el.toggleSidebar.onclick = () => { el.sidebar.classList.toggle("open"); overlay.classList.toggle("visible", el.sidebar.classList.contains("open")); }; overlay.onclick = () => { el.sidebar.classList.remove("open"); overlay.classList.remove("visible"); }; }

  // Connect WS
  connectWS();

  // Initial placeholder
  if (!currentTicker) { el.placeholder.classList.remove("hidden"); el.content.classList.add("hidden"); } else { el.placeholder.classList.add("hidden"); el.content.classList.remove("hidden"); }

  console.log("🚀 Borsa Bot v4.0 ready — Full stack loaded");
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();