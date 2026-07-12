const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const PORT = 8765;
const HOST = "127.0.0.1";

let serverProc = null;
let mainWindow = null;

function isPyAvailable(cmd) {
  // Basit kontrol: sürüm bayrağı ile dene
  return new Promise((resolve) => {
    const p = spawn(cmd, ["--version"], { windowsHide: true });
    p.on("error", () => resolve(false));
    p.on("close", (code) => resolve(code === 0));
  });
}

function checkServerUp() {
  return new Promise((resolve) => {
    const req = http.get(`http://${HOST}:${PORT}/api/health`, (res) => {
      if (res.statusCode === 200) { res.resume(); resolve(true); }
      else { res.resume(); resolve(false); }
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => { req.destroy(); resolve(false); });
  });
}

function startPythonServer() {
  return new Promise(async (resolve, reject) => {
    // Önce port'ta zaten çalışan bir sunucu var mı?
    if (await checkServerUp()) {
      console.log("[server] Port " + PORT + " zaten yanıt veriyor, mevcut sunucu kullanılacak.");
      resolve();
      return;
    }

    const pyCmd = (await isPyAvailable("python")) ? "python"
               : (await isPyAvailable("python3")) ? "python3"
               : null;

    if (!pyCmd) {
      reject(new Error("Python bulunamadı. Lütfen Python 3.11+ yükleyin ve PATH'e ekleyin."));
      return;
    }

    const cwd = path.join(__dirname, "..");
    serverProc = spawn(pyCmd, ["server.py", "--host", HOST, "--port", String(PORT)], {
      cwd,
      windowsHide: true,
    });

    serverProc.stdout.on("data", (d) => console.log("[server]", d.toString().trim()));
    serverProc.stderr.on("data", (d) => console.error("[server-error]", d.toString().trim()));
    serverProc.on("exit", (code) => {
      if (code && code !== 0) console.error("[server] exited with code", code);
    });

    // Sunucu hazır olana kadar bekle
    const tryHealth = () => {
      http
        .get(`http://${HOST}:${PORT}/api/health`, (res) => {
          if (res.statusCode === 200) resolve();
          else setTimeout(tryHealth, 300);
        })
        .on("error", () => setTimeout(tryHealth, 300));
    };
    tryHealth();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    backgroundColor: "#0a0a1a",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.webContents.on("console-message", (event, level, message, line, sourceId) => {
    console.log(`[renderer-console] [Level:${level}] ${message} (Line:${line} in ${path.basename(sourceId)})`);
  });

  mainWindow.loadURL(`http://${HOST}:${PORT}/`);
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    mainWindow.webContents.openDevTools();
  });
  mainWindow.on("closed", () => (mainWindow = null));
}

app.whenReady().then(async () => {
  try {
    await startPythonServer();
    createWindow();
  } catch (err) {
    console.error(err);
    app.quit();
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (serverProc) serverProc.kill();
  if (process.platform !== "darwin") app.quit();
});
