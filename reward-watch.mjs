// 背景記錄結算/獎勵格時序：每 3 秒查兩席，只在狀態變化時寫一行。
import fs from "node:fs/promises";
const LOG = process.argv[2] + "\\reward-watch.log";
const probe = '(function(){var C=window.__CHEAT;if(!C)return "無";return JSON.stringify({w:C.dbg.who().slice(2),rwGot:C.dbg.rwGot(),rwUp:C.dbg.rewardUp(),pick:C.lastPick,done:C.farm.done,phase:C.farm.phase,vil:C.dbg.inVillage()})})()';
async function evalp(port, id) {
  return new Promise((res) => {
    const ws = new WebSocket("ws://127.0.0.1:" + port + "/devtools/page/" + id);
    const t = setTimeout(() => { try { ws.close(); } catch (e) {} res("timeout"); }, 12000);
    ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: probe, returnByValue: true } }));
    ws.onmessage = (m) => { const x = JSON.parse(m.data); if (x.id === 1) { clearTimeout(t); try { ws.close(); } catch (e) {} res(x.exceptionDetails ? "EXC" : String(x.result?.result?.value)); } };
    ws.onerror = () => { clearTimeout(t); res("wserr"); };
  });
}
const prev = {};
const END = Date.now() + 40 * 60 * 1000;
while (Date.now() < END) {
  try {
    const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
    for (const p of list.filter((t) => t.type === "page" && t.url.includes("l1stw.com"))) {
      const s = await evalp(9222, p.id);
      let o; try { o = JSON.parse(s); } catch (e) { continue; }
      const sig = [o.phase, o.pick, o.rwGot, o.done].join("|");
      if (prev[o.w] !== sig) {
        prev[o.w] = sig;
        const line = new Date().toISOString().slice(11, 19) + " " + o.w + " phase=" + o.phase + " done=" + o.done + " rwGot=" + o.rwGot + " rwUp=" + o.rwUp + " " + (o.vil ? "村" : "圖") + " | " + o.pick + "\n";
        await fs.appendFile(LOG, line);
      }
    }
  } catch (e) { await fs.appendFile(LOG, "ERR " + e.message + "\n"); }
  await new Promise((r) => setTimeout(r, 3000));
}
await fs.appendFile(LOG, "=== 錄製結束\n");
