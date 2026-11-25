import fs from "node:fs/promises";
// 視窗守門：l1stw 視窗被最小化＝遊戲迴圈整個暫停（rAF 停），掛機白跑。
// 這裡每 20 秒巡一次，發現 minimized 就用 CDP 還原成 normal 並記一行。
const LOG = process.argv[2] + "\\window-guard.log";
const PORT = process.env.CDP_PORT || "9222";
function cdp(wsUrl, method, params) {
  return new Promise((res) => {
    const ws = new WebSocket(wsUrl);
    const t = setTimeout(() => { try { ws.close(); } catch (e) {} res({ err: "timeout" }); }, 10000);
    ws.onopen = () => ws.send(JSON.stringify({ id: 1, method, params: params || {} }));
    ws.onmessage = (m) => { const x = JSON.parse(m.data); if (x.id === 1) { clearTimeout(t); try { ws.close(); } catch (e) {} res(x.result || x.error || {}); } };
    ws.onerror = () => { clearTimeout(t); res({ err: "wserr" }); };
  });
}
async function sweep() {
  const list = await (await fetch("http://127.0.0.1:" + PORT + "/json/list")).json();
  for (const p of list.filter((t) => t.type === "page" && t.url.includes("l1stw.com"))) {
    const w = await cdp(p.webSocketDebuggerUrl, "Browser.getWindowForTarget");
    if (!w.windowId) continue;
    if (w.bounds && w.bounds.windowState !== "normal") {
      const r = await cdp(p.webSocketDebuggerUrl, "Browser.setWindowBounds", { windowId: w.windowId, bounds: { windowState: "normal" } });
      await fs.appendFile(LOG, new Date().toISOString().slice(11, 19) + " 還原 " + p.id.slice(0, 8) + " 原=" + w.bounds.windowState + " → " + JSON.stringify((r.bounds || {}).windowState || r) + "\n");
    }
  }
}
for (;;) {
  try { await sweep(); } catch (e) { await fs.appendFile(LOG, new Date().toISOString().slice(11, 19) + " ERR " + e.message + "\n"); }
  await new Promise((r) => setTimeout(r, 20000));
}
