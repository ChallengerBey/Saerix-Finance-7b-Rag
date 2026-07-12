/**
 * Service Worker - Offline-first PWA
 * Cache stratejisi: Network First (API), Cache First (Static)
 */
const CACHE_NAME = "borsabot-v6";
const STATIC_CACHE = "borsabot-static-v6";
const API_CACHE = "borsabot-api-v6";

const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/styles.css",
  "https://cdn.jsdelivr.net/npm/chart.js",
  "https://cdn.jsdelivr.net/npm/chartjs-chart-financial",
  "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap",
];

const API_PATTERNS = ["/api/analyze", "/api/simulate", "/api/health", "/api/quotes", "/api/heatmap", "/api/risk", "/api/backtest"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== STATIC_CACHE && k !== API_CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // API istekleri: Network First, fallback cache
  if (API_PATTERNS.some((p) => url.pathname.startsWith(p))) {
    e.respondWith(networkFirstAPI(e.request));
    return;
  }

  // Static assets: Cache First
  if (STATIC_ASSETS.some((a) => url.pathname === a || url.href === a) || e.request.destination === "script" || e.request.destination === "style" || e.request.destination === "font") {
    e.respondWith(cacheFirst(e.request));
    return;
  }

  // Diğer: Network First
  e.respondWith(networkFirst(e.request));
});

async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const resp = await fetch(request);
    if (resp.ok) cache.put(request, resp.clone());
    return resp;
  } catch {
    return new Response("Offline", { status: 503 });
  }
}

async function networkFirst(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const resp = await fetch(request);
    if (resp.ok) cache.put(request, resp.clone());
    return resp;
  } catch {
    const cached = await cache.match(request);
    return cached || new Response(JSON.stringify({ error: "Offline", cached: true }), { headers: { "Content-Type": "application/json" } });
  }
}

async function networkFirstAPI(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      const clone = resp.clone();
      cache.put(request, clone);
    }
    return resp;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: "Offline", cached: false }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

// Background Sync for pending mutations (portfolio/alerts adds when offline)
self.addEventListener("sync", (e) => {
  if (e.tag === "sync-mutations") {
    e.waitUntil(syncMutations());
  }
});

async function syncMutations() {
  // IndexedDB'den bekleyen mutation'ları al ve sunucuya gönder
  // Bu kısım renderer.js tarafında tetiklenir
  console.log("[SW] Sync mutations triggered");
}

// Push Notification
self.addEventListener("push", (e) => {
  if (!e.data) return;
  const data = e.data.json();
  const options = {
    body: data.body || "Yeni bildirim",
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📈</text></svg>",
    badge: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📈</text></svg>",
    vibrate: [100, 50, 100],
    data: data.url || "/",
    actions: [{ action: "open", title: "Aç" }, { action: "close", title: "Kapat" }],
  };
  e.waitUntil(self.registration.showNotification(data.title || "Borsa Bot", options));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  if (e.action === "close") return;
  e.waitUntil(clients.openWindow(e.notification.data || "/"));
});