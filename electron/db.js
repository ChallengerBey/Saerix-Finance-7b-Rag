/**
 * IndexedDB Wrapper - Offline-first veri katmanı
 * Watchlist, Portföy, Alarmlar, Ayarlar, Cache, Backtest sonuçları
 */
const DB_NAME = "BorsaBotDB";
const DB_VERSION = 3;

const STORES = {
  watchlist: { keyPath: "symbol" },
  portfolio: { keyPath: "id", autoIncrement: true },
  alerts: { keyPath: "id", autoIncrement: true },
  settings: { keyPath: "key" },
  cache: { keyPath: "key" },
  backtest: { keyPath: "id", autoIncrement: true, indexes: [{ name: "ts", keyPath: "ts" }] },
  quotes: { keyPath: "symbol" },
};

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      Object.entries(STORES).forEach(([name, opts]) => {
        if (!db.objectStoreNames.contains(name)) {
          const store = db.createObjectStore(name, { keyPath: opts.keyPath, autoIncrement: opts.autoIncrement });
          (opts.indexes || []).forEach(idx => store.createIndex(idx.name, idx.keyPath));
        }
      });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx(storeName, mode, fn) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    let result;
    try {
      result = fn(store);
    } catch (err) {
      tx.abort();
      reject(err);
      return;
    }
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error("Transaction aborted"));
  });
}

export const IDB = {
  // --- Watchlist ---
  async getWatchlist() {
    return tx("watchlist", "readonly", (store) => {
      return new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    });
  },
  async addWatchlist(symbol) {
    return tx("watchlist", "readwrite", (store) => {
      store.put({ symbol: symbol.toUpperCase(), added: Date.now() });
    });
  },
  async removeWatchlist(symbol) {
    return tx("watchlist", "readwrite", (store) => store.delete(symbol.toUpperCase()));
  },

  // --- Portfolio ---
  async getPortfolio() {
    return tx("portfolio", "readonly", (store) => {
      return new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    });
  },
  async addPortfolio(item) {
    return tx("portfolio", "readwrite", (store) => {
      store.add({ ...item, added: Date.now() });
    });
  },
  async updatePortfolio(id, data) {
    return tx("portfolio", "readwrite", (store) => {
      store.put({ ...data, id });
    });
  },
  async removePortfolio(id) {
    return tx("portfolio", "readwrite", (store) => store.delete(id));
  },
  async clearPortfolio() {
    return tx("portfolio", "readwrite", (store) => store.clear());
  },

  // --- Alerts ---
  async getAlerts() {
    return tx("alerts", "readonly", (store) => {
      return new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    });
  },
  async addAlert(alert) {
    return tx("alerts", "readwrite", (store) => {
      store.add({ ...alert, created: Date.now(), triggered: false });
    });
  },
  async removeAlert(id) {
    return tx("alerts", "readwrite", (store) => store.delete(id));
  },
  async updateAlert(id, data) {
    return tx("alerts", "readwrite", (store) => store.put({ ...data, id }));
  },

  // --- Settings ---
  async getSettings() {
    return tx("settings", "readonly", (store) => {
      return new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () => {
          const obj = {};
          (req.result || []).forEach((r) => (obj[r.key] = r.value));
          resolve(obj);
        };
        req.onerror = () => reject(req.error);
      });
    });
  },
  async setSetting(key, value) {
    return tx("settings", "readwrite", (store) => store.put({ key, value }));
  },

  // --- Cache (API responses) ---
  async getCache(key, maxAge = 300000) {
    return tx("cache", "readonly", (store) => {
      return new Promise((resolve) => {
        const req = store.get(key);
        req.onsuccess = () => {
          const item = req.result;
          if (item && Date.now() - item.ts < maxAge) resolve(item.data);
          else resolve(null);
        };
        req.onerror = () => reject(req.error);
      });
    });
  },
  async setCache(key, data) {
    return tx("cache", "readwrite", (store) => store.put({ key, data, ts: Date.now() }));
  },
  async clearCache() {
    return tx("cache", "readwrite", (store) => store.clear());
  },

  // --- Backtest Results ---
  async saveBacktest(result) {
    return tx("backtest", "readwrite", (store) => {
      store.add({ ...result, ts: Date.now() });
    });
  },
  async getBacktests(limit = 50) {
    return tx("backtest", "readonly", (store) => {
      return new Promise((resolve) => {
        const idx = store.index("ts");
        const req = idx.openCursor(null, "prev");
        const results = [];
        req.onsuccess = (e) => {
          const cursor = e.target.result;
          if (cursor && results.length < limit) {
            results.push(cursor.value);
            cursor.continue();
          } else resolve(results);
        };
        req.onerror = () => reject(req.error);
      });
    });
  },

  // --- Quotes (live price cache) ---
  async getQuote(symbol) {
    return tx("quotes", "readonly", (store) => {
      return new Promise((resolve) => {
        const req = store.get(symbol.toUpperCase());
        req.onsuccess = () => resolve(req.result?.data || null);
        req.onerror = () => reject(req.error);
      });
    });
  },
  async setQuote(symbol, data) {
    return tx("quotes", "readwrite", (store) => {
      store.put({ symbol: symbol.toUpperCase(), data, ts: Date.now() });
    });
  },
  async getAllQuotes() {
    return tx("quotes", "readonly", (store) => {
      return new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    });
  },

  // --- Bulk Operations ---
  async exportAll() {
    const db = await openDB();
    const data = {};
    for (const name of Object.keys(STORES)) {
      data[name] = await new Promise((resolve) => {
        const tx = db.transaction(name, "readonly");
        const store = tx.objectStore(name);
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    }
    return data;
  },
  async importAll(data) {
    const db = await openDB();
    for (const [name, items] of Object.entries(data)) {
      if (!STORES[name]) continue;
      await new Promise((resolve, reject) => {
        const tx = db.transaction(name, "readwrite");
        const store = tx.objectStore(name);
        store.clear();
        items.forEach((item) => store.put(item));
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    }
  },
};

export default IDB;